"""
OCR service — tries Tesseract first, falls back to Groq vision LLM.
Uses the groq SDK directly (more reliable than langchain_groq for multimodal).
"""
import os
import re
import io
import base64
import logging

logger = logging.getLogger(__name__)

_WIN_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Groq vision models to try in order (llama-3.2 vision models were decommissioned June 2025)
_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

# Max dimension to send to Groq — resize large photos to stay under API limits
_MAX_PX = 1280


def extract_text_from_image(image_bytes: bytes) -> str:
    # Try Tesseract first (fast, offline)
    try:
        import pytesseract
        from PIL import Image

        if os.name == "nt" and os.path.exists(_WIN_PATH):
            pytesseract.pytesseract.tesseract_cmd = _WIN_PATH

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        text = _clean(pytesseract.image_to_string(image, config="--psm 6"))
        if text:
            return text
    except Exception as e:
        logger.debug(f"Tesseract unavailable: {e}")

    # Fallback: Groq vision LLM
    return _extract_via_vision_llm(image_bytes)


def _resize_image(image_bytes: bytes) -> bytes:
    """Resize image so its longest side is at most _MAX_PX, return as JPEG bytes."""
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if max(w, h) > _MAX_PX:
        scale = _MAX_PX / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _extract_via_vision_llm(image_bytes: bytes) -> str:
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed — run: pip install groq")

    from ..config import get_settings
    settings = get_settings()
    keys = settings.groq_keys
    if not keys:
        raise RuntimeError("No Groq API keys configured in .env")

    # Resize before encoding — large photos cause request failures
    try:
        image_bytes = _resize_image(image_bytes)
        img_type = "jpeg"
    except Exception:
        img_type = "jpeg"

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:image/{img_type};base64,{b64}"

    errors = []
    for key in keys:
        client = Groq(api_key=key)
        for model in _VISION_MODELS:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extract all handwritten or printed text from this image. "
                                    "Return only the extracted text, preserving line breaks. "
                                    "No commentary, no explanations."
                                ),
                            },
                        ],
                    }],
                    temperature=0,
                    max_tokens=2048,
                )
                result = resp.choices[0].message.content
                if result and result.strip():
                    logger.info(f"OCR succeeded: model={model}")
                    return _clean(result)
            except Exception as e:
                err = f"key=...{key[-4:]}, model={model}: {e}"
                errors.append(err)
                logger.warning(f"Vision attempt failed — {err}")
                # Rate limit → skip remaining models for this key
                if "rate" in str(e).lower() or "429" in str(e):
                    break

    # Return a user-visible error that includes the real reason
    short = errors[-1] if errors else "unknown error"
    return f"OCR failed ({short}). Please type your answer manually."


def get_ocr_debug_info(image_bytes: bytes) -> dict:
    """Diagnostic function — returns per-model results. Used by /debug/ocr endpoint."""
    try:
        from groq import Groq
    except ImportError:
        return {"error": "groq package not installed"}

    from ..config import get_settings
    settings = get_settings()
    keys = settings.groq_keys

    try:
        resized = _resize_image(image_bytes)
    except Exception as e:
        return {"error": f"image resize failed: {e}"}

    b64 = base64.b64encode(resized).decode()
    data_url = f"data:image/jpeg;base64,{b64}"
    results = []

    key = keys[0] if keys else None
    if not key:
        return {"error": "no API keys"}

    client = Groq(api_key=key)
    for model in _VISION_MODELS:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "What text do you see in this image?"},
                ]}],
                temperature=0,
                max_tokens=512,
            )
            results.append({"model": model, "ok": True, "text": resp.choices[0].message.content[:200]})
        except Exception as e:
            results.append({"model": model, "ok": False, "error": str(e)})

    return {"image_bytes": len(image_bytes), "resized_bytes": len(resized), "models": results}


def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()
