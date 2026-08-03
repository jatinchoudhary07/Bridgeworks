import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_SEQUENCE = [
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.0-flash',
]

def generate_content_with_fallback(client, model: str, contents, config=None, fallback_models: Optional[List[str]] = None):
    """
    Executes generate_content using the given model. If it fails, falls back sequentially
    to other models to ensure high availability and prevent single-model timeouts/busy errors.
    """
    if fallback_models is None:
        fallback_models = DEFAULT_FALLBACK_SEQUENCE

    # Build sequence of models to try: initially requested, then fallbacks.
    candidates = [model]
    for fallback in fallback_models:
        if fallback not in candidates:
            candidates.append(fallback)

    last_error = None
    for idx, current_model in enumerate(candidates):
        try:
            logger.info(f"[GEMINI-FALLBACK] generate_content using model '{current_model}' (Attempt {idx+1}/{len(candidates)})")
            
            # Make the API call
            response = client.models.generate_content(
                model=current_model,
                contents=contents,
                config=config
            )
            
            # Log success
            logger.info(f"[GEMINI-FALLBACK] generate_content SUCCESS using model '{current_model}'")
            return response
            
        except Exception as e:
            logger.warning(f"[GEMINI-FALLBACK] generate_content FAILED with model '{current_model}' on attempt {idx+1}: {e}")
            last_error = e

    logger.error(f"[GEMINI-FALLBACK] generate_content all models failed. Last error: {last_error}")
    raise last_error


def generate_content_stream_with_fallback(client, model: str, contents, config=None, fallback_models: Optional[List[str]] = None):
    """
    Executes generate_content_stream using the given model, with sequential fallbacks.
    """
    if fallback_models is None:
        fallback_models = DEFAULT_FALLBACK_SEQUENCE

    candidates = [model]
    for fallback in fallback_models:
        if fallback not in candidates:
            candidates.append(fallback)

    last_error = None
    for idx, current_model in enumerate(candidates):
        try:
            logger.info(f"[GEMINI-FALLBACK] generate_content_stream using model '{current_model}' (Attempt {idx+1}/{len(candidates)})")
            
            stream = client.models.generate_content_stream(
                model=current_model,
                contents=contents,
                config=config
            )
            return stream
            
        except Exception as e:
            logger.warning(f"[GEMINI-FALLBACK] generate_content_stream FAILED to initialize with model '{current_model}': {e}")
            last_error = e

    logger.error(f"[GEMINI-FALLBACK] generate_content_stream all models failed. Last error: {last_error}")
    raise last_error
