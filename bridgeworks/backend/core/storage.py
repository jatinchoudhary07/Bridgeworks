import mimetypes
import os
from django.core.files.storage import FileSystemStorage

# Only import Cloudinary storage if credentials are configured
_USE_CLOUDINARY = all([
    os.getenv('CLOUDINARY_CLOUD_NAME'),
    os.getenv('CLOUDINARY_API_KEY'),
    os.getenv('CLOUDINARY_API_SECRET'),
])

if _USE_CLOUDINARY:
    from cloudinary_storage.storage import MediaCloudinaryStorage, RESOURCE_TYPES

    # MIME type → extension map for common types not covered well by mimetypes stdlib
    _MIME_EXT_MAP = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/bmp': '.bmp',
        'image/svg+xml': '.svg',
        'image/heic': '.heic',
        'image/heif': '.heif',
        'image/tiff': '.tiff',
        'image/avif': '.avif',
        'video/mp4': '.mp4',
        'video/quicktime': '.mov',
        'video/webm': '.webm',
        'video/x-msvideo': '.avi',
        'video/x-matroska': '.mkv',
        'application/pdf': '.pdf',
    }

    class AutoResourceCloudinaryStorage(MediaCloudinaryStorage):
        """Choose Cloudinary resource type by file extension.

        When the uploaded filename has no extension, sniff the MIME type from the
        file object (content_type attribute set by Django's upload handler) and
        inject the correct extension so images are always stored as image/upload
        instead of raw/upload.  Without this, screenshots sent from browsers often
        arrive without an extension and end up in Cloudinary as raw files whose
        URLs don't resolve correctly.
        """

        IMAGE_EXTENSIONS = {
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'heic', 'heif', 'tif', 'tiff', 'avif'
        }
        VIDEO_EXTENSIONS = {
            'mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', '3gp', 'wmv', 'flv', 'mpeg', 'mpg'
        }

        def _get_resource_type(self, name):
            extension = self._get_file_extension(name)
            if extension in self.IMAGE_EXTENSIONS:
                return RESOURCE_TYPES['IMAGE']
            if extension in self.VIDEO_EXTENSIONS:
                return RESOURCE_TYPES['VIDEO']

            if not extension:
                return RESOURCE_TYPES['IMAGE']

            name_lower = name.lower()
            if 'shop_logos' in name_lower or 'profile_pictures' in name_lower:
                return RESOURCE_TYPES['IMAGE']

            return RESOURCE_TYPES['RAW']

        @staticmethod
        def _get_file_extension(name):
            """Extract a *real* file extension from the very end of *name*."""
            if not name:
                return ''
            normalized = str(name).rsplit('/', 1)[-1]
            parts = normalized.rsplit('.', 1)
            if len(parts) != 2:
                return ''
            candidate = parts[1].strip().lower()
            if len(candidate) > 5 or not candidate.isalnum():
                return ''
            return candidate

        def _fix_name_extension(self, name, file):
            """If *name* has no recognised extension, derive one from content_type."""
            ext = self._get_file_extension(name)
            if ext and (ext in self.IMAGE_EXTENSIONS or ext in self.VIDEO_EXTENSIONS
                        or ext == 'pdf'):
                return name

            content_type = getattr(file, 'content_type', None)
            if content_type:
                new_ext = _MIME_EXT_MAP.get(content_type.split(';')[0].strip().lower())
                if not new_ext:
                    new_ext = mimetypes.guess_extension(content_type.split(';')[0].strip())
                    if new_ext in ('.jpe', '.jpeg'):
                        new_ext = '.jpg'
                if new_ext:
                    return name + new_ext

            return name

        def _save(self, name, content):
            name = self._fix_name_extension(name, content)
            return super()._save(name, content)

else:
    # Local dev fallback: plain filesystem storage
    # Models that reference AutoResourceCloudinaryStorage still work — files
    # just get saved to MEDIA_ROOT on disk instead of Cloudinary.
    class AutoResourceCloudinaryStorage(FileSystemStorage):
        """Local dev stub — stores files on local disk instead of Cloudinary."""
        pass
