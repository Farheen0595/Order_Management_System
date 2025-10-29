import asyncio
from pathlib import Path
from app.rag_services.pdf_service import PdfService  





async def test_pdf_rag():

    pdf_directory = Path("/home/farheens/Desktop/Order_Management_System/app/documents")  

    if not pdf_directory.exists():
        print(f"Directory does not exist: {pdf_directory}")
        return

    
    pdf_service = PdfService(chunk_size=500, chunk_overlap=50)

    # Load and chunk PDFs
    docs = await pdf_service.load_and_chunk_pdfs_from_dir(str(pdf_directory))

    # Print summary
    print(f"Total chunks created: {len(docs)}\n")

    for i, doc in enumerate(docs, start=1):
        file_name = doc.metadata.get("file", "Unknown")
        snippet = doc.page_content[:100].replace("\n", " ")
        print(f"Chunk {i} | File: {file_name} | Content snippet: {snippet}...\n")

if __name__ == "__main__":
    asyncio.run(test_pdf_rag())
