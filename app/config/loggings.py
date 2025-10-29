import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.config.constants import constants

_logger_initialized = False

class AppOnlyFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith("app")

def setup_logging(level=logging.DEBUG,
                  log_dir=constants.LOG_DIRECTORY,
                  log_file_name=constants.LOG_FILE_NAME,
                  filter_app_only=True):
    global _logger_initialized
    if _logger_initialized:
        return logging.getLogger()
    _logger_initialized = True

    # Ensure log directory exists
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_path_file = log_path / log_file_name

    fmt = "[%(asctime)s] [PID:%(process)d] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.hasHandlers():
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        if filter_app_only:
            console_handler.addFilter(AppOnlyFilter())
        root_logger.addHandler(console_handler)

        # File handler
        file_handler = RotatingFileHandler(
            log_path_file,
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        if filter_app_only:
            file_handler.addFilter(AppOnlyFilter())
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for logger_name in ['watchdog', 'urllib3', 'google', 'charset_normalizer', 'asyncio', 'aiosqlite']:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
        logging.getLogger(logger_name).propagate = False

    # Startup message
    app_logger = logging.getLogger("app")
    app_logger.debug("Logging system initialized")
    app_logger.info(f"Log level set to {logging.getLevelName(level)}")
    app_logger.info(f"Log file: {log_path_file}")
    app_logger.info(f"App-only filter: {filter_app_only}")

    return root_logger
