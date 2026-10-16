import os
from pydantic import BaseModel

class Settings(BaseModel):
    HOST: str = os.getenv("GATEWAY_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("GATEWAY_PORT", "8000"))
    OLLAYA_URL: str = os.getenv("OLLAYA_URL", "http://127.0.0.1:11435")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    DEFAULT_DECISION_MODEL: str = os.getenv("DEFAULT_DECISION_MODEL", "laya:en")
    FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "nemotron-3-nano:4b")
    FALLBACK_ENABLED: bool = os.getenv("FALLBACK_ENABLED", "true").lower() in ("true", "1", "yes")
    TIMEOUT_SECONDS: float = float(os.getenv("TIMEOUT_SECONDS", "15.0"))
    MAX_REQUEST_SIZE_BYTES: int = int(os.getenv("MAX_REQUEST_SIZE_BYTES", str(2 * 1024 * 1024))) # 2MB

settings = Settings()
