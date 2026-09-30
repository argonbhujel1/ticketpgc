"""Optional Cloudinary storage for Vercel (ephemeral filesystem)."""
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


def upload_file_storage(file_storage, folder='pgc'):
    """Upload Werkzeug FileStorage to Cloudinary. Returns secure_url or None."""
    if not file_storage or not file_storage.filename:
        return None
    if not cloudinary_enabled():
        return None
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'],
            api_key=os.environ['CLOUDINARY_API_KEY'],
            api_secret=os.environ['CLOUDINARY_API_SECRET'],
            secure=True,
        )
        result = cloudinary.uploader.upload(
            file_storage,
            folder=folder,
            resource_type='auto',
        )
        return result.get('secure_url')
    except Exception as e:
        current_app.logger.warning('Cloudinary upload failed: %s', e)
        return None


def youtube_id_from_url(url: str) -> str:
    """Extract 11-char YouTube video id from URL, embed code, or raw id."""
    if not url:
        return ''
    text = url.strip()
    # raw 11-char id
    if re.fullmatch(r'[\w-]{11}', text):
        return text
    # full iframe embed HTML or any string containing youtube URLs
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
