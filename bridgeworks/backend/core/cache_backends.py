import os
import logging
from django.core.cache.backends.filebased import FileBasedCache
from django.core.cache.backends.base import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

class SafeFileBasedCache(FileBasedCache):
    """
    A file-based cache backend that catches PermissionError and other file lock errors.
    This is extremely useful on Windows where concurrent reads/writes/deletes on the same
    cache file raise PermissionError (WinError 32).
    """

    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default, version)
        except (PermissionError, FileNotFoundError):
            return default
        except Exception as e:
            logger.warning("SafeFileBasedCache.get failed: %s", e)
            return default

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            super().set(key, value, timeout, version)
        except (PermissionError, FileNotFoundError):
            pass
        except Exception as e:
            logger.warning("SafeFileBasedCache.set failed: %s", e)

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().touch(key, timeout, version)
        except (PermissionError, FileNotFoundError):
            return False
        except Exception as e:
            logger.warning("SafeFileBasedCache.touch failed: %s", e)
            return False

    def delete(self, key, version=None):
        try:
            return super().delete(key, version)
        except (PermissionError, FileNotFoundError):
            return False
        except Exception as e:
            logger.warning("SafeFileBasedCache.delete failed: %s", e)
            return False

    def has_key(self, key, version=None):
        try:
            return super().has_key(key, version)
        except (PermissionError, FileNotFoundError):
            return False
        except Exception as e:
            logger.warning("SafeFileBasedCache.has_key failed: %s", e)
            return False

    def _delete(self, fname):
        try:
            return super()._delete(fname)
        except (PermissionError, FileNotFoundError):
            return False
        except Exception as e:
            logger.warning("SafeFileBasedCache._delete failed: %s", e)
            return False

    def clear(self):
        try:
            super().clear()
        except (PermissionError, FileNotFoundError):
            pass
        except Exception as e:
            logger.warning("SafeFileBasedCache.clear failed: %s", e)
