"""
Copy client folders (O:\\PARC CLIENTS.LC) into a MACHINE subfolder of their
target archive folder (O:\\AFFAIRES.LC\\ARCHIVES AFFAIRE), driven by an Excel mapping.

Source folder names look like : 74_ARMEMENT LE SHANGAIE_SHANGAIE 2   -> number = 74
Target folder names contain   : AMOT20260074                        -> key    = AMOT20260074

Processed pairs are recorded in a "Traite" workbook and skipped on later runs.

Usage:
    python copy_dossiers.py --dry-run --report rapport.csv
    python copy_dossiers.py --duplicates all --report rapport.csv --log-file copie.log
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

# --------------------------------------------------------------------------- #
# Defaults (override with CLI arguments)
# --------------------------------------------------------------------------- #
DEFAULT_EXCEL = Path(r"C:\Users\Stagiaire.be\Downloads\SOURCES CEGID PARC MOTEURS EMS 2026.xlsx")
DEFAULT_SOURCE_ROOT = Path(r"O:\PARC CLIENTS.LC")
DEFAULT_TARGET_ROOT = Path(r"O:\AFFAIRES.LC\ARCHIVES AFFAIRE")
DEFAULT_TRAITE_NAME = "Traite.xlsx"

MACHINE_DIRNAME = "MACHINE"
TRAITE_HEADER = ["Numero", "Affaire cible", "Dossier source", "Destination", "Date"]

SOURCE_RE = re.compile(r"^\s*(\d{1,5})(?!\d)")        # leading number of a name / cell
TARGET_RE = re.compile(r"AMOT\s*(\d{4})\s*(\d{4})", re.IGNORECASE)

logger = logging.getLogger("copy_dossiers")


# --------------------------------------------------------------------------- #
# Key normalisation
# --------------------------------------------------------------------------- #
def source_key(value) -> str | None:
    """'74', 74, 74.0, '0074', '74_ARMEMENT LE SHANGAIE' -> '74'."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    match = SOURCE_RE.match(str(value).strip())
    return str(int(match.group(1))) if match else None


def target_key(value) -> str | None:
    """'AMOT20260074', 'AMOT20260074   00_CLIENT_BATEAU' -> 'AMOT20260074'."""
    if value is None:
        return None
    match = TARGET_RE.search(str(value).strip())
    return f"AMOT{match.group(1)}{match.group(2)}".upper() if match else None


# --------------------------------------------------------------------------- #
# Excel reading
# --------------------------------------------------------------------------- #
def detect_columns(rows: list[tuple]) -> tuple[int, int]:
    """Pick the column with the most source-like values and the most target-like ones."""
    width = max((len(row) for row in rows), default=0)
    source_hits = [0] * width
    target_hits = [0] * width

    for row in rows:
        for index, cell in enumerate(row):
            if target_key(cell):
                target_hits[index] += 1
            elif source_key(cell):
                source_hits[index] += 1

    if not width or max(target_hits, default=0) == 0 or max(source_hits, default=0) == 0:
        raise ValueError("could not detect the source and target columns in the sheet")

    target_col = target_hits.index(max(target_hits))
    source_hits[target_col] = -1
    source_col = source_hits.index(max(source_hits))
    logger.info("Detected columns: source = %s, target = %s (0-based)", source_col, target_col)
    return source_col, target_col


def read_mapping(excel_path: Path, sheet: str | None,
                 source_col: int | None, target_col: int | None
                 ) -> tuple[list[tuple[str, str, int]], list[tuple[int, str]]]:
    """Return ([(source_key, target_key, excel_row), ...], [(excel_row, reason), ...])."""
    workbook = load_workbook(excel_path, read_only=True, data_only=True)
    worksheet = workbook[sheet] if sheet else workbook.active
    rows = list(worksheet.iter_rows(values_only=True))
    workbook.close()
    logger.info("Sheet '%s': %d row(s)", worksheet.title, len(rows))

    if source_col is None or target_col is None:
        source_col, target_col = detect_columns(rows)

    pairs: list[tuple[str, str, int]] = []
    ignored: list[tuple[int, str]] = []
    for row_index, row in enumerate(rows, start=1):
        if len(row) <= max(source_col, target_col):
            continue
        source = source_key(row[source_col])
        target = target_key(row[target_col])
        if source and target:
            pairs.append((source, target, row_index))
        elif source or target:
            reason = f"unusable row: source={row[source_col]!r} target={row[target_col]!r}"
            logger.warning("Row %d ignored: %s", row_index, reason)
            ignored.append((row_index, reason))
    return pairs, ignored


# --------------------------------------------------------------------------- #
# "Traite" workbook
# --------------------------------------------------------------------------- #
def read_traite(traite_path: Path) -> set[tuple[str, str]]:
    """Return the {(source_key, target_key)} pairs already processed."""
    if not traite_path.exists():
        return set()
    workbook = load_workbook(traite_path, read_only=True, data_only=True)
    worksheet = workbook.active
    done: set[tuple[str, str]] = set()
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        if len(row) >= 2:
            source, target = source_key(row[0]), target_key(row[1])
            if source and target:
                done.add((source, target))
    workbook.close()
    return done


def append_traite(traite_path: Path, entries: list[tuple[str, str, str, str]]) -> None:
    """entries = [(source_key, target_key, source_folder_name, destination), ...]"""
    if not entries:
        return
    if traite_path.exists():
        workbook = load_workbook(traite_path)
        worksheet = workbook.active
    else:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Traite"
        worksheet.append(TRAITE_HEADER)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    for source, target, folder_name, destination in entries:
        worksheet.append([source, target, folder_name, destination, stamp])
    workbook.save(traite_path)
    logger.info("%d entry/entries appended to %s", len(entries), traite_path)


def remove_rows_from_excel(excel_path: Path, row_indexes: set[int]) -> None:
    """Delete the given 1-based rows from the mapping workbook, after a .bak backup."""
    if not row_indexes:
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = excel_path.with_name(f"{excel_path.stem}_backup_{stamp}{excel_path.suffix}")
    shutil.copy2(excel_path, backup)
    logger.info("Backup written to %s", backup)

    workbook = load_workbook(excel_path)
    worksheet = workbook.active
    for row_index in sorted(row_indexes, reverse=True):
        worksheet.delete_rows(row_index)
    workbook.save(excel_path)
    logger.info("%d row(s) removed from %s", len(row_indexes), excel_path)


# --------------------------------------------------------------------------- #
# Folder indexing
# --------------------------------------------------------------------------- #
def index_folders(root: Path, key_func) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    for path in root.iterdir():
        if path.is_dir():
            key = key_func(path.name)
            if key:
                index[key].append(path)
    return index


def resolve_all(index: dict[str, list[Path]], key: str, label: str,
                allow_multiple: bool) -> list[Path]:
    matches = sorted(index.get(key, []), key=lambda path: path.name)
    if not matches:
        raise LookupError(f"no {label} folder for '{key}'")
    if len(matches) > 1 and not allow_multiple:
        raise LookupError(
            f"{len(matches)} {label} folders for '{key}': "
            + ", ".join(path.name for path in matches)
        )
    return matches


# --------------------------------------------------------------------------- #
# Copy
# --------------------------------------------------------------------------- #
def long_path(path: Path) -> str:
    """Bypass the 260-char limit on Windows."""
    text = str(path)
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        absolute = os.path.abspath(text)
        return "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute
    return text


def copy_one(source_dir: Path, target_dir: Path, dry_run: bool, overwrite: bool) -> tuple[str, Path]:
    """Return (status, destination)."""
    destination = target_dir / MACHINE_DIRNAME / source_dir.name

    if destination.exists():
        if not overwrite:
            return "skipped", destination
        if not dry_run:
            shutil.rmtree(long_path(destination))

    if dry_run:
        return "would copy", destination

    os.makedirs(long_path(target_dir / MACHINE_DIRNAME), exist_ok=True)
    shutil.copytree(long_path(source_dir), long_path(destination))
    return "copied", destination


def run(excel_path: Path, source_root: Path, target_root: Path, sheet: str | None,
        source_col: int | None, target_col: int | None,
        dry_run: bool, overwrite: bool, duplicates: str,
        report_path: Path | None, traite_path: Path, remove_from_excel: bool) -> int:
    for path, label in ((excel_path, "Excel file"), (source_root, "source root"), (target_root, "target root")):
        if not path.exists():
            logger.error("%s not found: %s", label, path)
            return 2

    pairs, ignored = read_mapping(excel_path, sheet, source_col, target_col)
    logger.info("%d usable mapping row(s), %d ignored", len(pairs), len(ignored))

    already_done = read_traite(traite_path)
    if already_done:
        before = len(pairs)
        pairs = [item for item in pairs if (item[0], item[1]) not in already_done]
        logger.info("%d row(s) already listed in %s, skipped", before - len(pairs), traite_path.name)

    source_index = index_folders(source_root, source_key)
    target_index = index_folders(target_root, target_key)
    logger.info("%d source folder(s), %d target folder(s) indexed", len(source_index), len(target_index))

    report: list[dict[str, str]] = [
        {"row": str(row_index), "source": "", "target": "", "status": "ignored", "detail": reason}
        for row_index, reason in ignored
    ]
    traite_entries: list[tuple[str, str, str, str]] = []
    processed_rows: set[int] = set()
    done = skipped = failed = 0

    for source, target, row_index in pairs:
        prefix = f"[row {row_index}] {source} -> {target}"
        try:
            source_dirs = resolve_all(source_index, source, "source", duplicates == "all")
            target_dir = resolve_all(target_index, target, "target", False)[0]
        except LookupError as error:
            logger.error("%s : %s", prefix, error)
            report.append({"row": str(row_index), "source": source, "target": target,
                           "status": "failed", "detail": str(error)})
            failed += 1
            continue

        if len(source_dirs) > 1:
            logger.warning("%s : %d source folders, all copied", prefix, len(source_dirs))

        row_ok = True
        for source_dir in source_dirs:
            try:
                status, destination = copy_one(source_dir, target_dir, dry_run, overwrite)
            except (OSError, shutil.Error) as error:
                logger.error("%s : %s : %s", prefix, source_dir.name, error)
                report.append({"row": str(row_index), "source": source_dir.name, "target": target,
                               "status": "failed", "detail": str(error)})
                failed += 1
                row_ok = False
                continue

            logger.info("%s : %s -> %s", prefix, status, destination)
            report.append({"row": str(row_index), "source": source_dir.name, "target": target,
                           "status": status, "detail": str(destination)})
            if status == "skipped":
                skipped += 1
            else:
                done += 1
            traite_entries.append((source, target, source_dir.name, str(destination)))

        if row_ok:
            processed_rows.add(row_index)

    if report_path:
        with open(report_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["row", "source", "target", "status", "detail"], delimiter=";")
            writer.writeheader()
            writer.writerows(report)
        logger.info("Report written to %s", report_path)

    if dry_run:
        logger.info("Dry run: %s left untouched", traite_path.name)
    else:
        append_traite(traite_path, traite_entries)
        if remove_from_excel:
            remove_rows_from_excel(excel_path, processed_rows)

    logger.info("Done: %d processed, %d skipped, %d failed, %d ignored rows", done, skipped, failed, len(ignored))
    return 1 if failed else 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--target-root", type=Path, default=DEFAULT_TARGET_ROOT)
    parser.add_argument("--sheet", default=None, help="Sheet name (default: active sheet)")
    parser.add_argument("--source-col", type=int, default=None, help="0-based column index (default: auto-detect)")
    parser.add_argument("--target-col", type=int, default=None, help="0-based column index (default: auto-detect)")
    parser.add_argument("--duplicates", choices=["error", "all"], default="error",
                        help="Several source folders for one number: fail the row (default) or copy them all")
    parser.add_argument("--traite", type=Path, default=None,
                        help=f"Workbook listing processed pairs (default: {DEFAULT_TRAITE_NAME} next to the Excel)")
    parser.add_argument("--remove-from-excel", action="store_true",
                        help="Also delete the processed rows from the mapping workbook (a timestamped backup copy is made first)")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be done without writing anything")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing destination folder")
    parser.add_argument("--report", type=Path, default=None, help="Write a per-row CSV report (';' separated)")
    parser.add_argument("--log-file", type=Path, default=None, help="Also write the log to this file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", handlers=handlers)

    return run(
        excel_path=args.excel,
        source_root=args.source_root,
        target_root=args.target_root,
        sheet=args.sheet,
        source_col=args.source_col,
        target_col=args.target_col,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        duplicates=args.duplicates,
        report_path=args.report,
        traite_path=args.traite or args.excel.parent / DEFAULT_TRAITE_NAME,
        remove_from_excel=args.remove_from_excel,
    )


if __name__ == "__main__":
    sys.exit(main())