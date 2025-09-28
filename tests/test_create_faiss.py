import asyncio
from app.rag_services.build_store_vectors import RAGVectorStoreBuilder





async def main():

    builder = RAGVectorStoreBuilder(
        pdf_dir="/home/farheens/Desktop/Order_Management_System/app/documents")


    # Build vector store from PDFs (uncomment if not built yet)
    await builder.build_vector_store()

    # Search the FAISS store by collection name (PDF stem name)
    results = await builder.search("product-inquriy", "smart tv", k=3)
    
    for r, score in results:
        print(r.page_content[:200].replace("\n", " "), score)

asyncio.run(main())
