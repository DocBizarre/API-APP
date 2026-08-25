#!/usr/bin/env python3
"""Move the source folders that were successfully copied into a "traité" subfolder.

Reads the archiving log, keeps only the lines that report an actual copy
("... : copied -> ..."), then moves each matching folder out of SOURCE_DIR
into SOURCE_DIR/traité (override with --dest).

Moves use os.rename ONLY (atomic, same volume). shutil.move is deliberately not
used: on failure it falls back to copy-then-delete, which can leave partial
copies in the destination and the originals in place.

Modes:
    (default)   dry run: what would be moved
    --apply     rename the folders
    --check     compare SOURCE and DEST trees (file count + total size) to
                audit the state left by a previous copy-then-delete run

Usage:
    python move_traites.py archive.log "O:\\PARC CLIENTS.LC" --check --report audit.csv
    python move_traites.py archive.log "O:\\PARC CLIENTS.LC"
    python move_traites.py archive.log "O:\\PARC CLIENTS.LC" --apply --report rapport.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

COPIED_RE = re.compile(
    r"\[row\s+(\d+)\]\s+(.+?)\s+->\s+(\S+)\s+:\s+copied\s+->\s+(.+?)\s*$"
)
FAILED_RE = re.compile(r"ERROR\s+\[row\s+(\d+)\]\s+(.+?)\s+->\s+(\S+)\s*:")

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
FIELDS = ["key", "folder", "status", "detail"]


def read_lines(path: Path) -> list[str]:
    for enc in ENCODINGS:
        try:
            return path.read_text(encoding=enc).splitlines()
        except UnicodeDecodeError:
            continue
    sys.exit(f"Cannot decode log file: {path}")


def basename(win_path: str) -> str:
    return win_path.replace("/", "\\").rstrip("\\").rsplit("\\", 1)[-1].strip()


def parse_log(path: Path) -> tuple[dict[str, str], set[str]]:
    copied: dict[str, str] = {}
    failed: set[str] = set()
    for line in read_lines(path):
        m = COPIED_RE.search(line)
        if m and " ERROR " not in line:
            name = basename(m.group(4))
            if name:
                copied[name] = m.group(2).strip()
            continue
        m = FAILED_RE.search(line)
        if m:
            failed.add(m.group(2).strip())
    return copied, failed


def iter_dirs(root: Path, depth: int, exclude: Path):
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, level = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError as exc:
            print(f"  ! cannot list {current}: {exc}", file=sys.stderr)
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            try:
                if entry.resolve() == exclude:
                    continue
            except OSError:
                continue
            yield entry
            if level + 1 < depth:
                stack.append((entry, level + 1))


def index_source(source_dir: Path, exclude: Path, depth: int):
    exact: dict[str, Path] = {}
    lower: dict[str, Path] = {}
    by_key: dict[str, list[Path]] = {}
    for entry in iter_dirs(source_dir, depth, exclude):
        exact.setdefault(entry.name, entry)
        lower.setdefault(entry.name.lower(), entry)
        by_key.setdefault(entry.name.split("_", 1)[0].strip(), []).append(entry)
    return exact, lower, by_key


def resolve(name: str, key: str, exact: dict, lower: dict, by_key: dict):
    if name in exact:
        return exact[name], "exact"
    if name.lower() in lower:
        return lower[name.lower()], "case-insensitive"
    candidates = by_key.get(key, [])
    if len(candidates) == 1:
        return candidates[0], f"prefix '{key}'"
    if len(candidates) > 1:
        return None, f"ambiguous: {len(candidates)} folders start with '{key}'"
    return None, "not found"


def scan_tree(root: Path) -> tuple[dict[str, int], list[str]]:
    """Return ({relative file path: size}, [errors]) for a whole tree."""
    files: dict[str, int] = {}
    errors: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda e: errors.append(str(e))):
        for filename in filenames:
            full = Path(dirpath) / filename
            try:
                files[str(full.relative_to(root)).lower()] = full.stat().st_size
            except OSError as exc:
                errors.append(str(exc))
    return files, errors


def compare(src: Path, dst: Path) -> tuple[str, str]:
    """Compare two trees. Returns (status, detail)."""
    src_files, src_err = scan_tree(src)
    dst_files, dst_err = scan_tree(dst)
    missing = [rel for rel in src_files if rel not in dst_files]
    differing = [rel for rel, size in src_files.items() if rel in dst_files and dst_files[rel] != size]
    extra = [rel for rel in dst_files if rel not in src_files]
    detail = (
        f"src={len(src_files)} files/{sum(src_files.values())} B | "
        f"dst={len(dst_files)} files/{sum(dst_files.values())} B | "
        f"missing={len(missing)} differing={len(differing)} extra={len(extra)}"
    )
    if src_err or dst_err:
        detail += f" | scan errors={len(src_err) + len(dst_err)}"
    if missing or differing:
        return "DUP_PARTIAL", detail
    return "DUP_COMPLETE", detail


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("log", type=Path)
    ap.add_argument("source", type=Path)
    ap.add_argument("--dest", type=Path, default=None, help="destination folder (default: SOURCE/traité)")
    ap.add_argument("--depth", type=int, default=1, help="levels below SOURCE to search (default: 1)")
    ap.add_argument("--apply", action="store_true", help="rename the folders (default: dry run)")
    ap.add_argument("--check", action="store_true", help="audit SOURCE vs DEST instead of moving")
    ap.add_argument("--report", type=Path, default=None, help="write a CSV report")
    args = ap.parse_args()

    source_dir = args.source.resolve()
    if not source_dir.is_dir():
        sys.exit(f"Not a directory: {source_dir}")
    dest_dir = args.dest.resolve() if args.dest else source_dir / "traité"

    copied, failed = parse_log(args.log)
    if not copied:
        sys.exit("No 'copied ->' line found in the log.")

    exact, lower, by_key = index_source(source_dir, dest_dir.resolve(), max(1, args.depth))
    rows: list[dict[str, str]] = []

    # ---- audit mode -------------------------------------------------------
    if args.check:
        counts: dict[str, int] = {}
        for name, key in sorted(copied.items(), key=lambda kv: kv[1]):
            src, _ = resolve(name, key, exact, lower, by_key)
            dst = dest_dir / name
            if src is None and not dst.exists():
                status, detail = "ABSENT", "neither in source nor in dest"
            elif src is None:
                status, detail = "MOVED_OK", "only in dest"
            elif not dst.exists():
                status, detail = "SOURCE_ONLY", "not moved, no copy in dest"
            else:
                status, detail = compare(src, dst)
            counts[status] = counts.get(status, 0) + 1
            rows.append({"key": key, "folder": name, "status": status, "detail": detail})
            print(f"{status:12} {name}  {detail}")
        print("\nSummary:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print("DUP_COMPLETE = full copy in dest + original still in source (safe to delete the original)")
        print("DUP_PARTIAL  = incomplete copy in dest — delete the DEST copy, keep the original")

    # ---- move mode --------------------------------------------------------
    else:
        to_move: list[tuple[Path, Path]] = []
        for name, key in sorted(copied.items(), key=lambda kv: kv[1]):
            src, reason = resolve(name, key, exact, lower, by_key)
            if src is None:
                rows.append({"key": key, "folder": name, "status": "MISSING", "detail": reason})
                continue
            target = dest_dir / src.name
            if target.exists():
                rows.append({"key": key, "folder": src.name, "status": "CONFLICT", "detail": str(target)})
                continue
            to_move.append((src, target))
            rows.append({"key": key, "folder": src.name, "status": "MOVE", "detail": f"{reason} | {src.parent}"})

        if args.apply:
            dest_dir.mkdir(parents=True, exist_ok=True)
            moved = 0
            for src, target in to_move:
                try:
                    os.rename(src, target)  # never copies; fails cleanly if not permitted
                    moved += 1
                except OSError as exc:
                    for row in rows:
                        if row["folder"] == src.name and row["status"] == "MOVE":
                            row["status"], row["detail"] = "ERROR", f"{exc} (nothing copied, source untouched)"
            print(f"Renamed {moved}/{len(to_move)} folder(s) -> {dest_dir}")
        else:
            for src, _ in to_move:
                print(f"[dry run] {src}  ->  {dest_dir}")
            print(f"\n[dry run] {len(to_move)} folder(s) would be moved to {dest_dir}")

        print(f"\nLog: {len(copied)} copied folder(s), {len(failed)} failed row(s) left in place")
        for status in ("MISSING", "CONFLICT", "ERROR"):
            batch = [r for r in rows if r["status"] == status]
            if batch:
                print(f"\n{status}: {len(batch)}")
                for row in batch[:20]:
                    print(f"  {row['folder']}  ({row['detail']})")
                if len(batch) > 20:
                    print(f"  ... and {len(batch) - 20} more (see --report)")

    if args.report:
        with args.report.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nReport written to {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())