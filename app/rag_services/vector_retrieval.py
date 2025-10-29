import json
import logging
import re
from pathlib import Path
from typing import List, Dict
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from app.config.settings import settings
from app.config.constants import constants

# Setup logging
logger = logging.getLogger(__name__)
VECTOR_STORE_DIR = Path(settings.VECTOR_DATABASE_DIR) / "faiss"


class VectorRetriever:
    """
    Handles semantic product retrieval from FAISS vector store.
    """

    def __init__(self, embedding_model: str = constants.DEFAULT_EMBEDDING_MODEL):
        logger.info(f"Initializing VectorRetriever with model: {embedding_model}")
        self.embedding_model_name = embedding_model

        logger.debug("Setting up HuggingFace embeddings")
        self.embedder = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={"device": "cpu"}
        )

        self.vector_store_dir = VECTOR_STORE_DIR / self._slug(self.embedding_model_name)
        logger.debug(f"Vector store directory: {self.vector_store_dir}")
        self.loaded_stores: Dict[str, FAISS] = {}
        logger.info("VectorRetriever initialized successfully")

    @staticmethod
    def _slug(name: str) -> str:
        logger.debug(f"Creating slug for: {name}")
        base = name.split("/")[-1]
        slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
        logger.debug(f"Generated slug: {slug}")
        return slug

    def _load_vector_store(self, collection_name: str) -> FAISS:
        logger.debug(f"Loading vector store for collection: {collection_name}")

        if collection_name in self.loaded_stores:
            logger.debug(f"Using cached vector store for {collection_name}")
            return self.loaded_stores[collection_name]

        folder = self.vector_store_dir
        if not folder.exists():
            logger.error(f"Vector store not found at: {folder}")
            raise ValueError(f"Vector store not found: {folder}")

        logger.info(f"Loading FAISS index from: {folder}")
        vs = FAISS.load_local(folder, self.embedder, index_name=collection_name, allow_dangerous_deserialization=True)
        self.loaded_stores[collection_name] = vs
        logger.info(f"Successfully loaded vector store: {collection_name}")
        return vs

    # --- 1️⃣ Semantic search for arbitrary query (details intent) ---
    async def search(self, collection_name: str, query: str, k: int = 1) -> str:
        logger.info(f"Performing semantic search - Collection: {collection_name}, Query: {query}, k={k}")

        try:
            vs = self._load_vector_store(collection_name)
            logger.debug("Executing similarity search")
            results = vs.similarity_search(query, k=k)
            logger.debug(f"Found {len(results)} results")

            structured_results = [{
                "title": doc.metadata.get("title", "N/A"),
                "brand": doc.metadata.get("brand", "N/A"),
                "price": doc.metadata.get("price", "N/A"),
                "content": doc.page_content
            } for doc in results]

            logger.info(f"Successfully structured {len(structured_results)} results")
            return json.dumps({"success": True, "output": structured_results})

        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    # --- 2️⃣ Fetch by known product names (top products intent) ---
    async def fetch_by_product_names(self, collection_name: str, product_names: List[str], k: int = 5) -> str:
        logger.info(f"Fetching products by names - Collection: {collection_name}")
        logger.debug(f"Product names to fetch: {product_names}")

        try:
            vs = self._load_vector_store(collection_name)
            structured_results = []

            for name in product_names:
                logger.debug(f"Searching for product: {name}")
                results = vs.similarity_search(name, k=1)
                logger.debug(f"Found {len(results)} results for {name}")

                for doc in results:
                    structured_results.append({
                        "title": doc.metadata.get("title", "N/A"),
                        "brand": doc.metadata.get("brand", "N/A"),
                        "price": doc.metadata.get("price", "N/A"),
                        "content": doc.page_content
                    })
                    logger.debug(f"Added product to results: {doc.metadata.get('title', 'N/A')}")

            logger.info(f"Successfully retrieved {len(structured_results)} products")
            return json.dumps({"success": True, "output": structured_results})

        except Exception as e:
            logger.error(f"Product fetch failed: {str(e)}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
