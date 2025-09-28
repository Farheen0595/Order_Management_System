from fastapi import FastAPI
from app.config.settings import settings, ensure_dirs_writable
from app.config.loggings import setup_logging
from app.routers import agents_apis
import logging


# Initialize logging and directories

# ensure_dirs_writable()  
setup_logging(level=logging.INFO)  

logger = logging.getLogger(__name__)



def create_app() -> FastAPI:
    
    app = FastAPI(title="Agentic Order Management System", version="1.0.0")
    app.include_router(agents_apis.router)
    return app

app = create_app()