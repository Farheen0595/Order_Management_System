# app/rag_services/build_store_vectors.py
import os
import logging
import anyio
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from app.config.settings import settings
from app.config.loggings import setup_logging
import re

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
PDF_PATH = f'{BASE_DIR}/{settings.PDF_PATH}'


class RAGVectorStoreBuilder:
    """
    Service for building FAISS vector stores from PDFs.
    Only handles: PDF loading → Chunking → Embedding → Saving
    """

    def __init__(self, 
                 pdf_dir: str = PDF_PATH,
                 vector_store_dir: str = f"{settings.VECTOR_DATABASE_DIR}/faiss",
                 chunk_size: int = settings.CHUNK_SIZE,
                 chunk_overlap: int = settings.CHUNCK_OVERLAP,
                 embedding_model: str = settings.DEFAULT_EMBEDDING_MODEL):
        
        self.pdf_dir = Path(pdf_dir)
        self.vector_store_dir = Path(vector_store_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model_name = embedding_model



        # Create embedding instance
        self.embedder = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={"device": "cpu"})
        

        self.embed_slug = self._slug(self.embedding_model_name)

        # Ensure directories exist
        os.makedirs(self.vector_store_dir, exist_ok=True)



    @staticmethod
    def _slug(name: str) -> str:
        """Safe slug for directory naming"""
        base = name.split("/")[-1]
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")



    async def build_vector_store(self):

        """Process all PDFs in directory and build FAISS stores"""

        if not self.pdf_dir.exists() or not self.pdf_dir.is_dir():
            raise ValueError(f"PDF directory does not exist: {self.pdf_dir}")

        pdf_files = list(self.pdf_dir.glob("*.pdf"))

        if not pdf_files:
            logger.warning("No PDFs found in directory: %s", self.pdf_dir)
            return

        for pdf_path in pdf_files:
            logger.info("Processing PDF: %s", pdf_path.name)
            try:
                # Load and chunk PDF
                chunks = await self._load_and_chunk_pdf(pdf_path)
                
                # Build FAISS vector store
                await self._build_faiss_store(chunks, pdf_path.stem)
                
            except Exception as e:
                logger.error("Failed to process %s: %s", pdf_path.name, e)



    async def _load_and_chunk_pdf(self, pdf_path: Path):
        """Load a single PDF and split into chunks asynchronously"""
        return await anyio.to_thread.run_sync(self._load_and_chunk_sync, pdf_path)



    def _load_and_chunk_sync(self, pdf_path: Path):

        """Synchronous PDF loading and chunking"""
        
        loader = PyMuPDFLoader(str(pdf_path))
        pages = loader.load()

        # Add metadata
        for d in pages: 
            d.metadata = d.metadata or {}
            d.metadata["file"] = pdf_path.name

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "Brand:", "Price:", "Technical Details", "What's in the Box"]
        )

        docs = splitter.split_documents(pages)

        if not docs:
            logger.warning("No text extracted from %s", pdf_path.name)
        
        return docs



    async def _build_faiss_store(self, docs, collection_name: str):
        """Build and save FAISS vector store asynchronously"""
        return await anyio.to_thread.run_sync(self._build_faiss_sync, docs, collection_name)



    def _build_faiss_sync(self, docs, collection_name: str):
        """Synchronous FAISS store creation"""
        folder = self.vector_store_dir / self.embed_slug
        os.makedirs(folder, exist_ok=True)

        vs = FAISS.from_documents(docs, self.embedder)
        vs.save_local(folder, index_name=collection_name)
        
        logger.info("FAISS vector store built: %s/%s", self.embed_slug, collection_name)
        
        return vs