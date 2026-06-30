from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
import json
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "CareerPilot AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    LOG_LEVEL: str = "INFO"

    # Parser settings
    SPACY_MODEL: str = "en_core_web_sm"
    PARSER_VERSION: str = "v2"
    MAX_PAGES: int = 10
    MAX_TEXT_LENGTH: int = 200000

    # ATS settings
    ATS_MIN_SKILLS_FOR_FULL_SCORE: int = 8
    ATS_MIN_EXPERIENCE_ENTRIES: int = 2
    ATS_RECOMMENDATION_LIMIT: int = 8

    STORAGE_PROVIDER: str = "LOCAL"
    LOCAL_STORAGE_PATH: str = "storage/resumes"
    MAX_FILE_SIZE_MB: int = 5
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "docx"]
    ALLOWED_MIME_TYPES: dict = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                # Try parsing as JSON array
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
            # Fallback to comma-separated list
            return [x.strip() for x in v.split(",") if x.strip()]
        elif isinstance(v, list):
            return [str(item) for item in v]
        return []

settings = Settings()
