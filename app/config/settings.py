from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


# Resolve .env at project root
BASE_DIR = Path(__file__).parent.parent.parent
ENV_PATH = f'{BASE_DIR}/.env'



class Settings(BaseSettings):


    """
    App settings loader.
    Loads configuration values from `.env` file and environment variables.
    """
    model_config = SettingsConfigDict(env_file=ENV_PATH,
                                    env_file_encoding="utf-8",
                                    extra="ignore")
    
    # App Environment
    APP_ENV: str
    
    # API Keys
    GEMINI_API_KEY: str
    SENDGRID_API_KEY: str
    COOKIE_SECRET: str

    # URLs
    SESSION_ID_URL: str
    MASTER_AGENT_URL: str
    
    # Paths
    PDF_PATH: str
    VECTOR_DATABASE_DIR: str
    
    # Database Configuration
    DB_HOSTNAME: str
    DB_PORT: int
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_POOL_SIZE: int
    DB_POOL_OVERFLOW: int

settings = Settings()


# Directory validation
def ensure_dirs_writable():
    """
    Make sure VECTOR_DATABASE_DIR exists and can be written to.
    Creates the folder if missing and checks write permission.
    """
    p = Path(settings.VECTOR_DATABASE_DIR).resolve()
    p.mkdir(parents=True, exist_ok=True)

    test_file = p / "checking"
    try:
        with open(test_file, "w") as f:
            f.write("ok")
        test_file.unlink(missing_ok=True)
    except PermissionError as e:
        raise PermissionError(
            f"Cannot write to INDEX_DIR={p}. "
            f"Fix directory VECTOR_DATABASE_DIR permissions or set to a user-writable path."
        ) from e

ensure_dirs_writable()









