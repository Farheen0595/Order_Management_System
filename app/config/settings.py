from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


# Resolve .env at project root (3 level up at the config)
BASE_DIR = Path(__file__).parent.parent.parent
ENV_PATH = f'{BASE_DIR}/.env'

class Settings(BaseSettings):


    """
        App settings loader.
        Loads configuration values from `.env` file and environment variables.
        Keeps all API keys, defaults, and paths in one place.
    """

    model_config = SettingsConfigDict(env_file=ENV_PATH,
                                      env_file_encoding="utf-8",
                                      extra="ignore")
    


    # APP ENV
    APP_ENV: str
    
    # GEMINI APU KEY
    GEMINI_API_KEY: str

    # GEMINI MODEL
    DEFAULT_MODEL: str


    # EMAIL API KEY
    EMAIL_API_KEY:str
 

    # MYSQL CREDENTIALS
    DB_HOSTNAME: str
    DB_PORT: int
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_POOL_SIZE: int
    DB_POOL_OVERFLOW: int

    # MYSQL TABLE NAMES
    DB_INVENTORY: str
    DB_INVENTORY_AUDIT: str
    DB_ORDER: str
    DB_ORDER_AUDIT: str

    # VECTOR INDEX
    VECTOR_DATABASE_DIR: str


    # LOG DIR & FILE NAME
    LOG_DIRECTORY: str  = "logs"
    LOG_FILE_NAME: str = "app.log"


settings =  Settings()

def ensure_dirs_writable():

    """
        Make sure VECTOR_DATABASE_DIR exists and can be written to.
        Creates the folder if missing and checks write permission
        by writing a small test file.
    """
    p = Path(settings.VECTOR_DATABASE_DIR).resolve()
    p.mkdir(parents=True, exist_ok=True)

    test_file = p / "checking"

    try:
        with open(test_file, "w") as f:
            f.write("ok")
        test_file.unlink(missing_ok=True)

    except PermissionError as e:

        raise PermissionError(f"Cannot write to INDEX_DIR={p}." f"Fix directory VECTOR_DATABASE_DIR permissions or set  to a user-writable path.") from e
    

ensure_dirs_writable()









