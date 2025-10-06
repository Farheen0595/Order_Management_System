import asyncio
from app.rag_services.build_vector_stores import RAGVectorStoreBuilder
from app.rag_services.vector_retrieval import VectorRetriever
import json

async def main():
    builder = RAGVectorStoreBuilder()
    retriever = VectorRetriever()

    # Step 1: Build vector store (uncomment if not already built)
    # await builder.build_vector_store()

    # # Step 2: Search in FAISS
    query = "smart tv with Wi-Fi"
    collection_name = "product-inquiry"   # must match your PDF stem name (without .pdf)

    results = await retriever.search(collection_name, query, k=3)

    

    final_result = json.loads(results)
    print("\n🔎 Query:", query)
    print("\n Results:",final_result["output"])
    print("📌 Top Results:")
    for i, r in enumerate(final_result["output"], 1):
        print(f"\nResult {i}:")
        print(f" Title: {r.get('title', 'N/A')}")
        print(f" Brand: {r.get('brand', 'N/A')}")
        print(f" Price: {r.get('price', 'N/A')}")
        print(f" Preview: {len(r["content"])}...")

if __name__ == "__main__":
    asyncio.run(main())
