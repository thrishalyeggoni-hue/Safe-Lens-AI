"""Content-validated, bounded decoding. Never keep user image files in history."""
import hashlib
import io
import re
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from ..config import settings

FORMATS = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}


def safe_filename(name):
    return re.sub(r'[^\w.() -]', '_', (name or 'screenshot').replace('\\', '/').rsplit('/', 1)[-1])[:120] or 'screenshot'


def decode_image(raw, filename):
    if not raw or len(raw) > settings.SCREENSHOT_MAX_BYTES:
        raise ValueError('Screenshot must be nonempty and at most 10 MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                fmt = image.format
                if fmt not in FORMATS:
                    raise ValueError('Decoded image format is unsupported; use PNG, JPEG or WEBP')
                width, height = image.size
                if width < 16 or height < 16 or max(width, height) > settings.SCREENSHOT_MAX_SIDE or width * height > settings.SCREENSHOT_MAX_PIXELS:
                    raise ValueError('Screenshot dimensions must be 16–6000 pixels per side and at most 12 million pixels')
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Animated/multi-frame images are unsupported; upload one screenshot')
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                orientation = image.getexif().get(274, 1)
                oriented = ImageOps.exif_transpose(image)
                if oriented.mode in ('RGBA', 'LA') or 'transparency' in oriented.info:
                    rgba = oriented.convert('RGBA')
                    rgb = Image.new('RGB', rgba.size, 'white')
                    rgb.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    rgb = oriented.convert('RGB')
                rgb.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Screenshot could not be safely decoded; it may be corrupt or oversized') from None
    meta = {'original_filename': safe_filename(filename), 'validated_format': fmt, 'validated_mime': FORMATS[fmt],
            'upload_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'encoded_width': width, 'encoded_height': height,
            'width': rgb.width, 'height': rgb.height, 'exif_orientation': orientation,
            'coordinate_space': 'EXIF-oriented original image; same orientation used by the browser preview',
            'preprocessing': ['Content validation', 'EXIF orientation correction' if orientation != 1 else 'EXIF orientation unchanged', 'RGB conversion with transparent pixels composited on white'],
            'authenticity': 'Container metadata does not verify image authenticity or sender identity'}
    return rgb, meta
