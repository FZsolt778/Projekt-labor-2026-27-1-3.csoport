#it reads the .env file and determines the types of variables it contains
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

MAIN_FOLDER = Path(__file__).resolve().parents[2]
print(MAIN_FOLDER)
class ENV_CONFIG(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=MAIN_FOLDER / ".env",
        env_file_encoding="utf-8",
        extra="ignore")

    # --- Adatbazis -----------
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    DATABASE_URL: str

    # --- JWT -------------------------------------------------------
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    MAX_FAILED_DELIVERIES: int = 3
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: SecretStr | None = None


settings = ENV_CONFIG()
