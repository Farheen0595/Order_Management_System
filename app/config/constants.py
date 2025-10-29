"""Constants configuration for the application"""

from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class AppConstants:
    """Application-wide constants"""
    
    # Model Configuration
    DEFAULT_MODEL: str = "gemini-2.5-flash"
    DEFAULT_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Logging Configuration
    LOG_DIRECTORY: str = "logs"
    LOG_FILE_NAME: str = "app.log"

    # Collection Settings
    COLLECTION_NAME: str = "product-inquiry"
    
    # FROM EMAIL
    DEFAULT_EMAIL_SENDER: str = "sdfarheen05@gmail.com"

# Create a singleton instance
constants = AppConstants()