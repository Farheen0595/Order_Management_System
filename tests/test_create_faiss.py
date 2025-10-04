import asyncio
from app.rag_services.build_store_vectors import RAGVectorStoreBuilder
from app.rag_services.vector_retrieval import VectorRetriever




async def main():

    builder = RAGVectorStoreBuilder()
    retrieval = VectorRetriever()


    # Build vector store from PDFs (uncomment if not built yet)
    # await builder.build_vector_store()

    # # # Search the FAISS store by collection name (PDF stem name)
    results = await retrieval.search("product-inquriy", "smart tv", k=3)

    print(results)
    
asyncio.run(main())
