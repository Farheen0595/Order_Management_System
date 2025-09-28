# corrected_schemas.py
from pydantic import BaseModel, Field, EmailStr
from typing import List




class ProductQueryInput(BaseModel):

    query: str = Field(..., description="User's product query string")
    top_k: int = Field(default=3, description="Number of top relevant chunks to retrieve")



class ProductQueryOutput(BaseModel):
    output: str = Field(..., description="Concatenated top-k relevant product chunks or error message")
    success: bool = Field(..., description="Indicates if query returned results successfully")
    retrieved_chunks: List[str] = Field(default=[], description="List of individual chunks retrieved from FAISS")
