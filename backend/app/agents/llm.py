"""
Multi-key Groq rotator — round-robins across up to 4 API keys.
On a 429 rate-limit it moves to the next key automatically.
All agents call small_llm() or large_llm() and use .invoke() — same interface as before.
No extra dependencies needed (uses langchain-groq already in requirements).
"""
import threading
from langchain_groq import ChatGroq
from ..config import get_settings

settings = get_settings()


class RotatingGroq:
    """
    Wraps multiple ChatGroq clients (one per API key).
    .invoke() round-robins and falls back to the next key on a 429.
    Thread-safe index increment so parallel agent calls don't collide.
    """

    def __init__(self, model: str, temperature: float, keys: list[str]):
        if not keys:
            raise ValueError("No Groq API keys provided — set GROQ_API_KEY_1 in .env")
        self._clients = [
            ChatGroq(model=model, api_key=k, temperature=temperature, max_retries=1)
            for k in keys
        ]
        self._idx = 0
        self._lock = threading.Lock()
        self._model = model

    def _next_client(self) -> ChatGroq:
        with self._lock:
            client = self._clients[self._idx % len(self._clients)]
            self._idx += 1
            return client

    def invoke(self, messages):
        last_err = None
        # Try every key before giving up
        for _ in range(len(self._clients)):
            client = self._next_client()
            try:
                return client.invoke(messages)
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate_limit" in err_str or "rate limit" in err_str:
                    last_err = e
                    continue   # rotate to next key
                raise          # non-rate-limit error — surface immediately
        raise Exception(
            f"All {len(self._clients)} Groq key(s) are rate-limited for model '{self._model}'. "
            f"Last error: {last_err}"
        )

    def __repr__(self):
        return f"RotatingGroq(model={self._model}, keys={len(self._clients)})"


# Module-level singletons — created once, reused across all agent calls
_small: RotatingGroq | None = None
_large: RotatingGroq | None = None


def small_llm() -> RotatingGroq:
    """Cheap fast model — used for routing, validation, mentor. Rotates all 4 keys."""
    global _small
    if _small is None:
        _small = RotatingGroq(settings.groq_model, 0.2, settings.groq_keys)
    return _small


def large_llm() -> RotatingGroq:
    """Larger model — used only for evaluation/grading. Rotates all 4 keys."""
    global _large
    if _large is None:
        _large = RotatingGroq(settings.groq_model_large, 0.1, settings.groq_keys)
    return _large
