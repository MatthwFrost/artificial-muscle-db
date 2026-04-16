import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "muscle_db")
    postgres_user: str = os.getenv("POSTGRES_USER", "muscle")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "")

    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "")
    firecrawl_api_url: str = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
    spark_model: str = os.getenv("SPARK_MODEL", "spark-1-pro")

    extractor_max_concurrency: int = int(os.getenv("EXTRACTOR_MAX_CONCURRENCY", "2"))
    extractor_timeout_seconds: int = int(os.getenv("EXTRACTOR_TIMEOUT_SECONDS", "120"))
    extractor_retry_max: int = int(os.getenv("EXTRACTOR_RETRY_MAX", "3"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


CONFIG = Config()
