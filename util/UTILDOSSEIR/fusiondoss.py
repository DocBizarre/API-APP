"""
Traitement des affaires sans libellé (nom = numéro seul, ex. "AMOT20210003   00").

- OTHER nu  + MAIN libellé  : fusion par numéro (libellé déjà présent côté MAIN)
- MAIN nu   + OTHER libellé : renomme le dossier MAIN avec le nom d'OTHER, puis fusion
- les deux nus              : fusion par numéro, signalé "reste sans libellé"
- plusieurs candidats MAIN au même numéro : rien n'est fait, listé en fin

Mécanique identique aux runs précédents : copie avec reprise, source vers _TRAITES.
"""

import os
import re
import shutil
from pathlib import Path

MAIN_DIR = Path(r"O:\AFFAIRES.LC")
OTHER_DIR = Path(r"S:\COMMERCIAL\AFFAIRES.LC")
TREATED_DIR = OTHER_DIR / "_TRAITES"
SUBFOLDER_NAME = "COMMERCIAL"
APPLY = True            # False = dry-run
MAIN_SCAN_DEPTH = 3
EXCLUDE_DIRS = {"A_RECLASSER", "_TRAITES"}

CASE_RE = re.compile(r"^(AMOT(\d{8}))")
# nom "nu" : numéro éventuellement suivi de 00/underscores/espaces, sans libellé
BARE_RE = re.compile(r"^AMOT\d{8}[\s_]*0{0,2}[\s_]*$")


def iter_case_dirs(root: Path, max_depth: int):
    stack = [(root, 0)]
    while stack:
        d, lvl = stack.pop()
        try:
            children = list(d.iterdir())
        except OSError as e:
            print(f"[ERREUR ACCES] {d}: {e}")
            continue
        for c in children:
            if not c.is_dir() or c.name in EXCLUDE_DIRS:
                continue
            if CASE_RE.match(c.name):
                yield c
            elif lvl + 1 < max_depth:
                stack.append((c, lvl + 1))


def copy_tree_resumable(src: Path, dst: Path, errors: list) -> bool:
    ok = True
    dst.mkdir(parents=True, exist_ok=True)
    for item in sorted(src.iterdir()):
        target = dst / item.name
        try:
            if item.is_dir():
                ok &= copy_tree_resumable(item, target, errors)
            else:
                if target.exists() and target.stat().st_size == item.stat().st_size:
                    continue
                shutil.copy2(str(item), str(target))
        except OSError as e:
            errors.append((str(item), f"copie: {e}"))
            ok = False
    return ok


def unique_treated_dest(name: str) -> Path:
    dest = TREATED_DIR / name
    i = 1
    while dest.exists():
        dest = TREATED_DIR / f"{name}_{i}"
        i += 1
    return dest


def main():
    main_cases = list(iter_case_dirs(MAIN_DIR, MAIN_SCAN_DEPTH))
    by_num: dict[str, list[Path]] = {}
    for d in main_cases:
        by_num.setdefault(CASE_RE.match(d.name).group(1), []).append(d)

    errors, skipped, still_bare = [], [], []
    done = 0

    for src in sorted(OTHER_DIR.iterdir()):
        if not src.is_dir() or src.name in EXCLUDE_DIRS:
            continue
        m = CASE_RE.match(src.name)
        if not m:
            continue
        num = m.group(1)
        src_bare = bool(BARE_RE.match(src.name))

        candidates = by_num.get(num, [])
        if len(candidates) != 1:
            if candidates:
                skipped.append((src.name, f"{len(candidates)} candidats MAIN"))
            elif src_bare:
                skipped.append((src.name, "aucun dossier MAIN à ce numéro"))
            continue
        target = candidates[0]
        target_bare = bool(BARE_RE.match(target.name))

        # ce script ne traite que les cas où au moins un côté est nu ;
        # les paires libellées relèvent du flux decisions.csv
        if not src_bare and not target_bare:
            continue

        print(f"\n[{num}] OTHER: {src.name}"
              + ("  (sans libellé)" if src_bare else ""))
        print(f"      MAIN : {target.relative_to(MAIN_DIR)}"
              + ("  (sans libellé)" if target_bare else ""))

        # renommage du dossier technique nu avec le nom du dossier commercial
        if target_bare and not src_bare:
            new_target = target.with_name(src.name)
            if new_target.exists():
                skipped.append((src.name, f"renommage impossible, "
                                          f"{src.name} existe déjà dans MAIN"))
                continue
            print(f"      renomme MAIN -> {src.name}")
            if APPLY:
                os.rename(str(target), str(new_target))
                target = new_target
        elif src_bare and target_bare:
            still_bare.append(num)

        print(f"      fusionne -> {target.name}\\{SUBFOLDER_NAME}")
        if APPLY:
            if not copy_tree_resumable(src, target / SUBFOLDER_NAME, errors):
                print("      COPIE_PARTIELLE - source conservée")
                continue
            TREATED_DIR.mkdir(exist_ok=True)
            try:
                os.rename(str(src), str(unique_treated_dest(src.name)))
                done += 1
            except OSError as e:
                errors.append((str(src), f"déplacement _TRAITES: {e}"))
                print("      SOURCE_BLOQUEE - copie complète, ménage côté S:")
        else:
            done += 1

    print(f"\n{done} affaires {'traitées' if APPLY else 'traitables'}.")
    if still_bare:
        print(f"\nSans libellé des deux côtés (fusionnées, à renommer à la main "
              f"si un libellé se trouve dans les documents) :")
        for n in still_bare:
            print(f"  {n}")
    if skipped:
        print(f"\nNon traitées ({len(skipped)}) :")
        for name, why in skipped:
            print(f"  {name} — {why}")
    if errors:
        print(f"\n{len(errors)} erreurs :")
        for p, e in errors:
            print(f"  {p}\n    {e}")
    if not APPLY:
        print("\n== DRY RUN : rien n'a été modifié. APPLY=True pour exécuter. ==")


if __name__ == "__main__":
    main()