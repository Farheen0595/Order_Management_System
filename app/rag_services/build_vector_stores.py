# app/rag_services/build_store_vectors.py

import os
import logging
import anyio
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain_community.vectorstores import FAISS
from app.config.settings import settings
import re
import json
import pdfplumber

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
PDF_PATH = f'{BASE_DIR}/{settings.PDF_PATH}'


class RAGVectorStoreBuilder:

    def __init__(self, 
                 pdf_dir: str = PDF_PATH,
                 vector_store_dir: str = f"{settings.VECTOR_DATABASE_DIR}/faiss",
                 embedding_model: str = settings.DEFAULT_EMBEDDING_MODEL):
        
        logger.info(f"Initializing RAGVectorStoreBuilder")
        logger.debug(f"PDF Directory: {pdf_dir}")
        logger.debug(f"Vector Store Directory: {vector_store_dir}")
        logger.debug(f"Embedding Model: {embedding_model}")

        self.pdf_dir = Path(pdf_dir)
        self.vector_store_dir = Path(vector_store_dir)
        self.embedding_model_name = embedding_model

        # Create embedding instance
        logger.debug("Initializing HuggingFace embeddings")
        self.embedder = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={"device": "cpu"}
            )
        logger.info("Embeddings initialized successfully")

        self.embed_slug = self._slug(self.embedding_model_name)
        logger.debug(f"Generated embedding slug: {self.embed_slug}")

        # Ensure directories exist
        os.makedirs(self.vector_store_dir, exist_ok=True)

    @staticmethod
    def _slug(name: str) -> str:
        """Safe slug for directory naming"""
        base = name.split("/")[-1]
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")

    async def build_vector_store(self):

        logger.info("Starting vector store build process")

        if not self.pdf_dir.exists() or not self.pdf_dir.is_dir():

            logger.error(f"PDF directory not found: {self.pdf_dir}")
            raise ValueError(f"PDF directory does not exist: {self.pdf_dir}")

        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files to process")

        if not pdf_files:
            logger.warning(f"No PDFs found in directory: {self.pdf_dir}")
            return

        for pdf_path in pdf_files:
            logger.info(f"Processing PDF: {pdf_path.name}")

            try:
                logger.debug(f"Loading and chunking PDF: {pdf_path.name}")
                docs = await self._load_and_chunk_pdf(pdf_path)
                logger.info(f"Generated {len(docs)} document chunks from {pdf_path.name}")
                
                logger.debug(f"Building FAISS store for {pdf_path.stem}")
                await self._build_faiss_store(docs, pdf_path.stem)
                logger.info(f"Completed processing {pdf_path.name}")
                
            except Exception as e:
                logger.error("Failed to process %s: %s", pdf_path.name, e)

    async def _load_and_chunk_pdf(self, pdf_path: Path):
        """Load a single PDF and split into chunks asynchronously"""
        return await anyio.to_thread.run_sync(self._load_and_chunk_sync, pdf_path)

    def _load_and_chunk_sync(self, pdf_path: Path):
        logger.debug(f"Starting synchronous PDF loading: {pdf_path.name}")

        with pdfplumber.open(pdf_path) as pdf:
            logger.debug(f"PDF opened successfully: {len(pdf.pages)} pages")
            text = ""
            for page_num, page in enumerate(pdf.pages, 1):
                logger.debug(f"Extracting text from page {page_num}")
                text += page.extract_text() + "\n"

        logger.debug("Cleaning and processing text")
        text = text.replace("(cid:127)", "•")

        logger.debug("Splitting into product blocks")
        products = re.split(r"\n(?=[^ \n].+?\nBrand:)", text)
        list_of_products = [p.strip() for p in products if p.strip()]
        logger.info(f"Extracted {len(list_of_products)} product blocks")

        structured_data = []
        for idx, item in enumerate(list_of_products, 1):
            logger.debug(f"Processing product {idx}/{len(list_of_products)}")
            lines = [l.strip() for l in item.split("\n") if l.strip()]
            if not lines:
                logger.warning(f"Empty product block found at index {idx}")
                continue

            title = lines[0]
            brand = next((l.split(":")[1].strip() for l in lines if l.startswith("Brand:")), "")
            price = next((l.split(":")[1].strip() for l in lines if l.startswith("Price:")), "")
            
            logger.debug(f"Extracted product - Title: {title[:30]}...")
            structured_data.append({
                "title": title,
                "brand": brand,
                "price": price,
                "content": " ".join(lines)
            })

        logger.debug("Converting to LangChain Documents")
        docs = [
            Document(
                page_content=item["content"],
                metadata={
                    "title": item["title"],
                    "brand": item["brand"],
                    "price": item["price"]
                }
            ) for item in structured_data
        ]
        
        logger.info(f"Created {len(docs)} LangChain documents")
        return docs

    async def _build_faiss_store(self, docs, collection_name: str):
        """Build and save FAISS vector store asynchronously"""
        return await anyio.to_thread.run_sync(self._build_faiss_sync, docs, collection_name)

    def _build_faiss_sync(self, docs, collection_name: str):
        logger.debug(f"Starting FAISS store creation for {collection_name}")
        folder = self.vector_store_dir / self.embed_slug
        os.makedirs(folder, exist_ok=True)
        logger.debug(f"Created FAISS directory: {folder}")

        logger.info("Building FAISS index")
        vs = FAISS.from_documents(docs, self.embedder)
        
        logger.debug(f"Saving FAISS index: {collection_name}")
        vs.save_local(folder, index_name=collection_name)
        
        logger.info(f"FAISS vector store built successfully: {self.embed_slug}/{collection_name}")
        return vs
