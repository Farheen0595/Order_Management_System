# app/rag_services/vector_retrieval.py

import logging
import anyio
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from app.config.settings import settings
from app.config.loggings import setup_logging
import re
import json


logger = logging.getLogger(__name__)


class VectorRetriever:
    """
    Service for retrieving chunks from existing FAISS vector stores.
    Only handles: Loading vector store → Searching
    """

    def __init__(self,
                 vector_store_dir: str = "/home/farheens/Desktop/Order_Management_System/vector_store/faiss",
                 embedding_model: str = settings.DEFAULT_EMBEDDING_MODEL):

        self.vector_store_dir = Path(vector_store_dir)
        self.embedding_model_name = embedding_model

        # Create embedding instance
        self.embedder = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={"device": "cpu"}
        )
        self.embed_slug = self._slug(self.embedding_model_name)

    @staticmethod
    def _slug(name: str) -> str:
        """Safe slug for directory naming"""
        base = name.split("/")[-1]
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")

    async def search(self,
                     collection_name: str,
                     query: str,
                     k: int = 5):
        """
        Load vector store and perform similarity search.
        """

        vs = await anyio.to_thread.run_sync(self._load_faiss_sync, collection_name)

        try:
            result = await anyio.to_thread.run_sync(
                vs.similarity_search_with_score, query, k
            )

            if not result:
                output_data = {"output": "Product not found", "success": False}
                return json.dumps(output_data)

            else:
                chunks = []
                for doc, _ in result:
                    text = doc.page_content
                    text = text.replace("\n", " ").replace("\u2022", "-").strip()
                    text = " ".join(text.split())
                    chunks.append(text)

                output_data = {"output": "\n\n".join(chunks), "success": True}
                return json.dumps(output_data)

        except Exception as e:
            logger.error("Error in ProductVectorSearchTool: %s", e)
            output_data = {
                "output": f" Error querying vector store: {e}",
                "success": False,
            }
            return json.dumps(output_data)

    def _load_faiss_sync(self, collection_name: str):
        """Synchronous FAISS loading with debug logging"""

        folder = self.vector_store_dir / self.embed_slug
        faiss_path = folder / f"{collection_name}.faiss"
        pkl_path = folder / f"{collection_name}.pkl"

        logger.info(f"🔍 Attempting to load FAISS index for collection '{collection_name}'")
        logger.info(f"📂 Folder: {folder}")
        logger.info(f"📄 Expecting FAISS file: {faiss_path}")
        logger.info(f"📄 Expecting PKL file:   {pkl_path}")

        if not faiss_path.exists():
            logger.error(f"❌ FAISS file missing: {faiss_path}")
        if not pkl_path.exists():
            logger.error(f"❌ PKL file missing: {pkl_path}")

        return FAISS.load_local(
            folder,
            self.embedder,
            index_name=collection_name,
            allow_dangerous_deserialization=True,
        )
