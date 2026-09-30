"""Image/video upload: Cloudinary when configured, else local static/uploads."""
import os
import uuid
from pathlib import Path
from flask import current_app

ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO = {'mp4', 'webm', 'mov', 'm4v'}
ALLOWED = ALLOWED_IMAGES | ALLOWED_VIDEO


def _clear_white_bg(path: Path):
    try:
        from PIL import Image
        img = Image.open(path).convert('RGBA')
        pixels = img.getdata()
        new = []
        for r, g, b, a in pixels:
            if r > 240 and g > 240 and b > 240:
                new.append((255, 255, 255, 0))
            elif r > 230 and g > 230 and b > 230 and abs(r - g) < 12 and abs(g - b) < 12:
                new.append((r, g, b, max(0, 255 - int((r + g + b) / 3 - 200) * 8)))
            else:
                new.append((r, g, b, a))
        img.putdata(new)
        out = path.with_suffix('.png')
        img.save(out, 'PNG')
        if out != path and path.exists():
            path.unlink(missing_ok=True)
        return out
    except Exception:
        return path


def save_upload(file_storage, folder='general', clear_bg=False, resource_type=None):
    """Save upload. Returns Cloudinary URL or relative path 'folder/name.ext'.

    On Vercel, Cloudinary is strongly preferred (local /tmp is ephemeral).
    """
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else ''
    if ext not in ALLOWED:
        return None

    if resource_type is None:
        resource_type = 'video' if ext in ALLOWED_VIDEO else 'image'

    # Cloudinary first
    try:
        from app.services.cloudinary_store import cloudinary_enabled, upload_file_storage
        if cloudinary_enabled():
            url = upload_file_storage(
                file_storage,
                folder=f'pgc/{folder}',
                resource_type=resource_type if resource_type in ('image', 'video', 'auto') else 'auto',
            )
            if url:
                return url
            try:
                file_storage.stream.seek(0)
            except Exception:
                pass
        elif os.environ.get('VERCEL'):
            current_app.logger.error(
                'Cloudinary not configured on Vercel — set CLOUDINARY_CLOUD_NAME, '
                'CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET'
            )
            return None
    except Exception as e:
        current_app.logger.warning('Cloudinary path error: %s', e)

    # Local disk (dev)
    root = Path(current_app.config['UPLOAD_FOLDER'])
    dest_dir = root / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f'{uuid.uuid4().hex[:12]}.{ext}'
    path = dest_dir / name
    file_storage.save(str(path))
    if clear_bg or folder == 'logos':
        if ext in ALLOWED_IMAGES:
            path = _clear_white_bg(path)
            name = path.name
    return f'{folder}/{name}'
