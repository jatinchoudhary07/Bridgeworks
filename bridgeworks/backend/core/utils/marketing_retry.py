import time
import random
import logging
from facebook_business.exceptions import FacebookRequestError

logger = logging.getLogger(__name__)

def execute_meta_api_with_retry(api_func, *args, max_retries=5, initial_delay=2, backoff_factor=2, **kwargs):
    """
    Executes a Meta (Facebook) API call with exponential backoff and jitter.
    Specifically handles Facebook rate limits (error codes 17, 32, 613)
    and transient server errors (error codes 1, 2, or general connection/timeout errors).
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return api_func(*args, **kwargs)
        except FacebookRequestError as e:
            error_code = e.api_error_code()
            is_transient = error_code in [1, 2, 17, 32, 613] or e.api_transient_error()
            
            # If not transient (e.g. 190 OAuth token expired, permission errors), raise immediately
            if not is_transient:
                logger.error(f"Meta API non-transient error (code {error_code}): {e}")
                raise e
            
            if attempt == max_retries - 1:
                logger.error(f"Meta API request failed after {max_retries} attempts: {e}")
                raise e
            
            # Calculate sleep time with jitter: (delay to delay + 1s)
            sleep_time = delay + random.uniform(0.1, 1.0)
            logger.warning(
                f"Meta API rate limit/transient error (code {error_code}). "
                f"Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(sleep_time)
            delay *= backoff_factor
            
        except Exception as e:
            # Handle connection timeouts, network issues
            if attempt == max_retries - 1:
                logger.error(f"Meta API request failed with exception after {max_retries} attempts: {e}")
                raise e
                
            sleep_time = delay + random.uniform(0.1, 1.0)
            logger.warning(
                f"Transient connection error {type(e).__name__}: {e}. "
                f"Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(sleep_time)
            delay *= backoff_factor
