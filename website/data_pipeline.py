"""Data discovery and image processing helpers for the static site generator."""

import os
import re
import multiprocessing

from settings import OUT_DIR

try:  # pragma: no cover - install at runtime if missing
    from PIL import Image
except ImportError:
    import subprocess
    import sys

    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image


def get_available_dates():
    """Return sorted list of available forecast dates from OUT."""
    dates = []
    if os.path.exists(OUT_DIR):
        for item in sorted(os.listdir(OUT_DIR)):
            if os.path.isdir(os.path.join(OUT_DIR, item)) and re.match(r"\d{4}-\d{2}-\d{2}", item):
                dates.append(item)
    return dates


def get_available_data(date):
    """Return available parameters, times, domains, and soundings for a date."""
    date_dir = os.path.join(OUT_DIR, date)
    if not os.path.exists(date_dir):
        return {"parameters": [], "times": [], "domains": [], "soundings": []}

    parameters = set()
    times = set()
    domains = set()
    soundings = set()

    pattern = re.compile(r"(\w+)\.curr\.(\d{4})lst\.d(\d)\.body\.png")
    sounding_pattern = re.compile(r"sounding(\d+)\.curr\.\d{4}lst\.d\d\.png")

    for filename in os.listdir(date_dir):
        match = pattern.match(filename)
        if match:
            parameters.add(match.group(1))
            times.add(match.group(2))
            domains.add(f"d{match.group(3)}")

        sounding_match = sounding_pattern.match(filename)
        if sounding_match:
            soundings.add(sounding_match.group(1))

    if os.path.exists(os.path.join(date_dir, "pfd_tot.body.webp")):
        parameters.add("pfd_tot")

    return {
        "parameters": sorted(parameters),
        "times": sorted(times),
        "domains": sorted(domains),
        "soundings": sorted(soundings),
    }


def process_image(args):
    """Open PNG and save as WebP. Returns 1 on success, 0 on failure."""
    src_path, dest_path = args
    try:
        img = Image.open(src_path)
        img.save(dest_path, "WEBP", quality=90)
        return 1
    except Exception as exc:  # pragma: no cover - runtime logging only
        print(f"Error processing {src_path}: {exc}")
        return 0


def copy_images(date, dest_dir):
    """Copy all PNGs for a date to dest_dir as WebP, using multiprocessing."""
    src_dir = os.path.join(OUT_DIR, date)
    if not os.path.exists(src_dir):
        return 0

    os.makedirs(dest_dir, exist_ok=True)

    files_to_process = []
    for filename in os.listdir(src_dir):
        if filename.endswith(".png") and (
            ".body." in filename
            or ".head." in filename
            or ".foot." in filename
            or ".side." in filename
            or filename.startswith("sounding")
        ):
            src_path = os.path.join(src_dir, filename)
            dest_filename = filename.replace(".png", ".webp")
            dest_path = os.path.join(dest_dir, dest_filename)
            files_to_process.append((src_path, dest_path))

    if not files_to_process:
        return 0

    with multiprocessing.Pool() as pool:
        results = pool.map(process_image, files_to_process)

    return sum(results)
