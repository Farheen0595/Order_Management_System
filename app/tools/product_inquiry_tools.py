from pydantic import BaseModel
from typing import Type
import json
from langchain.tools import BaseTool
from app.schemas.product_inquiry_schema import ProductQueryInput,ProductQueryOutput
import asyncio
import logging
from app.rag_services.build_store_vectors import RAGVectorStoreBuilder
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from app.config.settings import settings
from app.config.loggings import setup_logging



setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)



# ----------------------------
#  ProductVectorSearchTool

# ----------------------------
class ProductVectorSearchTool(BaseTool):

    name: str = "Product_Vector_Search_Tool"
    description: str = (
        "Search pre-built FAISS vectors for product information. "
        "Input should be a user query string. "
        "Returns relevant product text chunks in JSON format.")

    args_schema: Type[BaseModel] = ProductQueryInput
    return_direct: bool = False


    def __init__(self, 
                 vector_store_dir: str,
                embed_model: HuggingFaceEmbeddings,
                default_top_k:int):
        

        self.vector_store_dir = vector_store_dir
        self.embed_model = embed_model
        self.default_top_k = settings.DEFAULT_TOP_K
        self.builder = RAGVectorStoreBuilder(
            pdf_dir=None,  # not used for loading
            vector_store_dir=vector_store_dir
        )



    async def _arun(self, query: str, top_k: int = None, **kwargs) -> str:

        """
        Async execution of FAISS search.
        Returns JSON string matching ProductQueryOutput schema.
        """

        top_k = top_k or self.default_top_k

        try:
            slug = self.builder.embed_slug or "all-minilm-l6-v2"

            # Load vector store
            store = await self.builder.load(
                embedder=self.embed_model,
                db="faiss",
                embed_slug=slug,
                collection="product_catalog"
            )

            # Search top-k relevant chunks
            results = await self.builder.search(store, db="faiss", query=query, k=top_k)

            if not results:
                output_data = ProductQueryOutput(output="❌ Product not found.", success=False, retrieved_chunks=[])
                return json.dumps(output_data.dict())

            chunks = [chunk.page_content.strip() for chunk, _ in results]
            output_data = ProductQueryOutput(output="\n---\n".join(chunks), success=True, retrieved_chunks=chunks)
            return json.dumps(output_data.dict())

        except Exception as e:
            logger.error("Error in ProductVectorSearchTool: %s", e)
            output_data = ProductQueryOutput(output=f"❌ Error querying vector store: {e}", success=False, retrieved_chunks=[])
            return json.dumps(output_data.dict())

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Sync execution not supported, use _arun.")



