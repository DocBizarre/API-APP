#!/usr/bin/env python3
"""
Recursively compress all photos in a directory, in place.

- Resumable: processed files are recorded in a state file (JSON) stored
  at the root of the target directory (.compress_state.json). If the
  script is interrupted (Ctrl+C, crash, shutdown), re-running it skips
  everything already done.
- Progress counter: prints processed / total, plus bytes saved.
- Safe: writes to a temp file, then atomically replaces the original.
  Only replaces if the compressed version is actually smaller.

Requirements: pip install Pillow

Usage:
    python compress_photos.py /path/to/folder
    python compress_photos.py /path/to/folder --quality 80 --max-dim 2560
"""

import argparse
import json
import os
import signal
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
STATE_FILENAME = ".compress_state.json"


def load_state(state_path: Path) -> dict:
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print(f"[warn] Corrupt state file, starting fresh: {state_path}")
    return {"processed": {}}


def save_state(state: dict, state_path: Path) -> None:
    # Atomic write: temp file + replace, so a crash never corrupts state.
    fd, tmp = tempfile.mkstemp(dir=str(state_path.parent), prefix=".state_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, state_path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def file_key(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def already_done(state: dict, path: Path, root: Path) -> bool:
    entry = state["processed"].get(file_key(path, root))
    if entry is None:
        return False
    # If the file changed since we processed it (size or mtime), redo it.
    st = path.stat()
    return entry.get("size") == st.st_size and entry.get("mtime") == int(st.st_mtime)


def mark_done(state: dict, path: Path, root: Path) -> None:
    st = path.stat()
    state["processed"][file_key(path, root)] = {
        "size": st.st_size,
        "mtime": int(st.st_mtime),
    }


def compress_image(path: Path, quality: int, max_dim: int | None) -> tuple[bool, int]:
    """
    Compress one image in place.
    Returns (replaced, bytes_saved).
    """
    original_size = path.stat().st_size
    ext = path.suffix.lower()

    with Image.open(path) as img:
        # Apply EXIF orientation so the pixels match what the user sees,
        # then drop the orientation tag implicitly.
        img = ImageOps.exif_transpose(img)

        if max_dim and max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        save_kwargs: dict = {}
        if ext in (".jpg", ".jpeg"):
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            save_kwargs = {
                "format": "JPEG",
                "quality": quality,
                "optimize": True,
                "progressive": True,
            }
            exif = img.info.get("exif")
            if exif:
                save_kwargs["exif"] = exif
        elif ext == ".png":
            save_kwargs = {"format": "PNG", "optimize": True}
        elif ext == ".webp":
            save_kwargs = {"format": "WEBP", "quality": quality, "method": 6}

        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=ext, prefix=".cmp_tmp_")
        os.close(fd)
        try:
            img.save(tmp, **save_kwargs)
            new_size = os.path.getsize(tmp)
            if new_size < original_size:
                os.replace(tmp, path)
                return True, original_size - new_size
            os.remove(tmp)
            return False, 0
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Recursively compress photos, resumable.")
    parser.add_argument("folder", type=Path, help="Root folder to scan")
    parser.add_argument("--quality", type=int, default=85, help="JPEG/WebP quality (default 85)")
    parser.add_argument(
        "--max-dim",
        type=int,
        default=None,
        help="Optional: downscale so the longest side is at most this many pixels",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=10,
        help="Write the state file every N images (default 10)",
    )
    args = parser.parse_args()

    root: Path = args.folder.resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {root}")
        return 1

    state_path = root / STATE_FILENAME
    state = load_state(state_path)

    # Collect all candidate files first so we can show x/total.
    all_photos = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        and not p.name.startswith(".cmp_tmp_")
    )
    total = len(all_photos)
    todo = [p for p in all_photos if not already_done(state, p, root)]
    skipped = total - len(todo)

    print(f"Found {total} photos ({skipped} already processed, {len(todo)} to do)")

    # Save state on SIGTERM too (e.g. system shutdown), not just Ctrl+C.
    def on_sigterm(signum, frame):
        save_state(state, state_path)
        print("\n[interrupted] State saved, re-run to resume.")
        sys.exit(130)

    signal.signal(signal.SIGTERM, on_sigterm)

    processed_this_run = 0
    replaced_count = 0
    total_saved = 0

    try:
        for i, path in enumerate(todo, start=1):
            try:
                replaced, saved = compress_image(path, args.quality, args.max_dim)
                if replaced:
                    replaced_count += 1
                    total_saved += saved
            except Exception as e:
                print(f"[error] {path}: {e}")
                # Do not mark as done: it will be retried next run.
                continue

            mark_done(state, path, root)
            processed_this_run += 1

            done_total = skipped + processed_this_run
            print(
                f"\r[{done_total}/{total}] {path.name[:50]:<50} "
                f"saved {total_saved / 1024 / 1024:.1f} MB",
                end="",
                flush=True,
            )

            if processed_this_run % args.save_every == 0:
                save_state(state, state_path)
    except KeyboardInterrupt:
        print("\n[interrupted] State saved, re-run to resume.")
    finally:
        save_state(state, state_path)

    print(
        f"\nDone. Processed this run: {processed_this_run}, "
        f"compressed (smaller): {replaced_count}, "
        f"total saved: {total_saved / 1024 / 1024:.1f} MB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())