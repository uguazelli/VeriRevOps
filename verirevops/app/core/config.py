from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field

class Settings(BaseSettings):
    # This configuration tells Pydantic to automatically look for a ".env" file
    # in the root of your project directory.
    model_config = SettingsConfigDict(
        env_file=".env",              # The name of the file to load
        env_file_encoding="utf-8",    # Encoding of the file
        extra="ignore"                # Ignore extra variables in the environment
    )

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"

    @computed_field
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # AI Models
    GOOGLE_API_KEY: str
    MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    TEMPERATURE: float = 0.0

    # Chatwoot (Global defaults if not in DB)
    CHATWOOT_API_URL: str = ""
    CHATWOOT_API_TOKEN: str = ""

    # Application
    APP_PORT: int = 8000

# Instantiate the settings object to be used across the application.
# When this is called, Pydantic reads the environment variables and the .env file.
settings = Settings()
