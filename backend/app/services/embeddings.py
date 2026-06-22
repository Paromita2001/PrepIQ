from sentence_transformers import SentenceTransformer
from functools import lru_cache
from ..config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_embed_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embed_model)


def embed(text: str) -> list[float]:
    model = get_embed_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_embed_model()
    return model.encode(texts, normalize_embeddings=True).tolist()
