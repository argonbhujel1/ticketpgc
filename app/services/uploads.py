"""Image upload: Cloudinary when configured, else local static/uploads."""
import uuid
from pathlib import Path
from flask import current_app

ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


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


def save_upload(file_storage, folder='general', clear_bg=False):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else ''
    if ext not in ALLOWED:
        return None

    # Cloudinary first (required on Vercel for persistence)
    try:
        from app.services.cloudinary_store import cloudinary_enabled, upload_file_storage
        if cloudinary_enabled():
            url = upload_file_storage(file_storage, folder=f'pgc/{folder}')
            if url:
                return url
            try:
                file_storage.stream.seek(0)
            except Exception:
                pass
    except Exception as e:
        current_app.logger.warning('Cloudinary path error: %s', e)

    root = Path(current_app.config['UPLOAD_FOLDER'])
    dest_dir = root / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f'{uuid.uuid4().hex[:12]}.{ext}'
    path = dest_dir / name
    file_storage.save(str(path))
    if clear_bg or folder == 'logos':
        path = _clear_white_bg(path)
        name = path.name
    return f'{folder}/{name}'
