"""Cloudinary storage for images & video (Vercel-safe persistence)."""
from __future__ import annotations
import os
import re
from flask import current_app


def cloudinary_enabled() -> bool:
    return bool(
        os.environ.get('CLOUDINARY_CLOUD_NAME')
        and os.environ.get('CLOUDINARY_API_KEY')
        and os.environ.get('CLOUDINARY_API_SECRET')
    )


def _config():
    import cloudinary
    cloudinary.config(
        cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'],
        api_key=os.environ['CLOUDINARY_API_KEY'],
        api_secret=os.environ['CLOUDINARY_API_SECRET'],
        secure=True,
    )


def upload_file_storage(file_storage, folder='pgc', resource_type='auto'):
    """Upload Werkzeug FileStorage. Returns secure_url or None.

    resource_type: 'image' | 'video' | 'raw' | 'auto'
    """
    if not file_storage or not file_storage.filename:
        return None
    if not cloudinary_enabled():
        return None
    try:
        import cloudinary.uploader
        _config()
        # stream may need rewind
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
        result = cloudinary.uploader.upload(
            file_storage,
            folder=folder,
            resource_type=resource_type,
            overwrite=False,
            unique_filename=True,
        )
        return result.get('secure_url')
    except Exception as e:
        current_app.logger.warning('Cloudinary upload failed: %s', e)
        return None


def upload_image(file_storage, folder='pgc/images'):
    return upload_file_storage(file_storage, folder=folder, resource_type='image')


def upload_video(file_storage, folder='pgc/videos'):
    return upload_file_storage(file_storage, folder=folder, resource_type='video')


def is_cloudinary_url(url: str) -> bool:
    if not url:
        return False
    return 'res.cloudinary.com' in url or url.startswith('https://cloudinary.com')


def youtube_id_from_url(url: str) -> str:
    """Extract 11-char YouTube video id from URL, embed code, or raw id."""
    if not url:
        return ''
    text = url.strip()
    if re.fullmatch(r'[\w-]{11}', text):
        return text
    patterns = [
        r'(?:youtube\.com/embed/|youtube-nocookie\.com/embed/)([\w-]{11})',
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})',
        r'[?&]v=([\w-]{11})',
        r'youtube\.com/live/([\w-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1)
    return ''
