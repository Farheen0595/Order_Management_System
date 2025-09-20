import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .settings import settings   

class AppOnlyFilter(logging.Filter):

    """Allow only logs from the 'app' package."""
    def filter(self, record):
        return record.name.startswith("app")
    

def setup_logging(
    level: int,
    log_dir: str = settings.LOG_DIRECTORY,
    log_file: str = settings.LOG_FILE_NAME
):
    # Ensure log directory exists
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_path_file = log_path / log_file

    # Formatter
    fmt = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(AppOnlyFilter())   

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_path_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(AppOnlyFilter())      

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("app").info(
        f"Logging initialized. Level={logging.getLevelName(level)}, File={log_path_file}"
    )

setup_logging(level=logging.INFO)