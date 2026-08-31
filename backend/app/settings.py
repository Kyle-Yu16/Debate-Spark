from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


class Settings:
    # Any provider implementing OpenAI's /chat/completions schema can be used.
    # Provider branding deliberately stays out of the application contract.
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    model = os.getenv("LLM_MODEL", "")
    database_path = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "spark.db")))
    request_timeout = float(os.getenv("REQUEST_TIMEOUT", "90"))

    @property
    def demo_mode(self) -> bool:
        placeholder_keys = {"your_api_key", "your_deepseek_api_key", "changeme", "sk-xxx"}
        placeholder_models = {"your_model_name", "changeme"}
        return (
            not bool(self.api_key)
            or not bool(self.base_url)
            or not bool(self.model)
            or self.api_key.strip().lower() in placeholder_keys
            or self.model.strip().lower() in placeholder_models
        )


settings = Settings()
