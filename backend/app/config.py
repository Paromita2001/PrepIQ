from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 4 Groq keys — key 1 is required, 2-4 are optional (leave blank if you only have fewer)
    groq_api_key_1: str 
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""
    groq_api_key_4: str = ""

    database_url: str
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    groq_model: str = "llama-3.1-8b-instant"
    groq_model_large: str = "llama-3.3-70b-versatile"

    @property
    def groq_keys(self) -> list[str]:
        """Returns all non-empty Groq keys."""
        return [k for k in [
            self.groq_api_key_1,
            self.groq_api_key_2,
            self.groq_api_key_3,
            self.groq_api_key_4,
        ] if k.strip()]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
