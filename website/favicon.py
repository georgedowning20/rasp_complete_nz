"""Favicon generation helpers for the static site generator."""

import os

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - runtime install if missing
    print("Installing Pillow...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw


def create_favicon(dest_dir: str, filename: str = 'favicon.png') -> str:
    """Create the skew-T style favicon and write it to dest_dir.

    Returns the full path to the generated favicon.
    """
    print("📸 Creating favicon...")

    icon_size = 256
    img = Image.new('RGBA', (icon_size, icon_size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Background rectangle with red border
    draw.rectangle(
        [21, 21, icon_size - 21, icon_size - 21],
        fill=(255, 255, 255, 255),
        outline=(233, 69, 96),
        width=5,
    )

    # Skewed isotherms
    for i in range(4):
        draw.line(
            [35 + i * 48, icon_size - 42, 78 + i * 48, 42],
            fill=(233, 69, 96, 64),
            width=5,
        )

    # Horizontal pressure lines (light grey)
    for y in [64, 107, 149, 192]:
        draw.line([35, y, icon_size - 35, y], fill=(200, 200, 200), width=4)

    # Temperature profile
    temp_points = [(196, 213), (158, 171), (196, 139), (147, 96), (126, 53)]
    draw.line(temp_points, fill=(233, 69, 96), width=10, joint='curve')

    # Dewpoint profile
    dew_points = [(126, 213), (126, 171), (99, 149), (94, 96), (84, 53)]
    for i in range(len(dew_points) - 1):
        x1, y1 = dew_points[i]
        x2, y2 = dew_points[i + 1]
        draw.line([x1, y1, x2, y2], fill=(11, 0, 212), width=8)

    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, filename)
    img.save(dest_path)
    print("📸 Favicon created")
    return dest_path
