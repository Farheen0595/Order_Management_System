from fastapi import FastAPI
from app.routers import agents_apis
from app.config.settings import ensure_dirs_writable
from app.config.loggings import setup_logging   
import logging

setup_logging()

# Initialize logger
logger = logging.getLogger("app.main")

# Create FastAPI app
app = FastAPI(title="Agentic Order Management System", version="1.0.0")

# Setup app at startup
@app.on_event("startup")
async def startup_event():
    try:
        ensure_dirs_writable()
        app.include_router(agents_apis.router)
        logger.info("App started successfully")
    except Exception as e:
        logger.exception("Failed to start the app")


