"""
Extrait les COMMERCIAL mal placés vers MAIN_DIR/A_RECLASSER/<nom d'origine>/COMMERCIAL
Cible le dossier destinataire par son nom EXACT (repris du log du premier run).
"""

import shutil
from pathlib import Path

MAIN_DIR = Path(r"C:\Users\Stagiaire.be\Downloads\AFFAIRES.LC")
QUARANTINE = MAIN_DIR / "A_RECLASSER"
DRY_RUN = False

# num -> (dossier MAIN qui a reçu le contenu par erreur, nom d'affaire d'origine côté OTHER)
MISPLACED = {
    "AMOT20260001": (
        "AMOT20260001   00_MARINE PERFORMANCE_MALOUROSI - MALOUROSI - DI13.080M + MG 5114DC",
        "AMOT20260001   00_MECA MARINE PROPULSION_ATLANTIQUE 6M33.2",
    ),
    "AMOT20260004": (
        "AMOT20260004   00_OCEA - WIGHT SHIPYARD - 12M26.3",
        "AMOT20260004   00_SCANIA FRANCE_CAMPAGNE DE RAPPEL BIELLES DI16",
    ),
    "AMOT20260016": (
        "AMOT20260016   00_CHANTIER NAVAL DELAVERGNE_WALLIS GEB - WALLIS - GEB - DOSSIER CEGID 20250050",
        "AMOT20260016   00_PORS MORO_PILOTE DE LA ROCHELLE - DI13-070M + REDUCTEUR TWIN DISC MGX5096A",
    ),
    "AMOT20260018": (
        "AMOT20260018   00_ARMEMENT LECUYER - PENN KLEIZ - DOSSIER CEGID MOT20260027",
        "AMOT20260018   00_SOCARENAM ST MALO_MONTAGE EDAS dague et mousquet",
    ),
    "AMOT20260022": (
        "AMOT20260022   00_BATEAUX ROUGES - LADY CLAIRE - DOSSIER CEGID MOT20250062",
        "AMOT20260022   00_MD NAVAL_DI13.80M - AVARIE MOTEUR",
    ),
    "AMOT20260023": (
        "AMOT20260023   00_CHANTIER PORS MOROS - PILOTE LA ROCHELLE - DOSSIER CEGID 20260016",
        "AMOT20260023   00_SOCARENAM BOULOGNE_TC250119 - CAMPAGNE BIELLES POM N°5",
    ),
    "AMOT20260025": (
        "AMOT20260025   00_NORD MOTORS_VCSM MARONNI - NEF150 - PRO2026053",
        "AMOT20260025   00_SCANIA FRANCE_TC250119 - REMPLACEMENT BIELLES POM N°5",
    ),
    "AMOT20260029": (
        "AMOT20260029   00_ARMEMENT L'ETOURDI_ETOURDI - ETOURDI -DI13.081",
        "AMOT20260029   00_BERTOT CLAUDE _IRIS IV - NEF400",
    ),
}


def main():
    for num, (wrong_dest_name, original_name) in MISPLACED.items():
        same_num = [d for d in MAIN_DIR.iterdir()
                    if d.is_dir() and d.name.startswith(num)]
        others = [d.name for d in same_num if d.name != wrong_dest_name]
        if others:
            print(f"[{num}] autres dossiers portant ce numéro (non touchés) :")
            for n in others:
                print(f"      {n}")

        wrong_dest = MAIN_DIR / wrong_dest_name
        commercial = wrong_dest / "COMMERCIAL"
        if not commercial.is_dir():
            print(f"[{num}] pas de COMMERCIAL dans « {wrong_dest_name} », ignoré")
            continue

        dest = QUARANTINE / original_name / "COMMERCIAL"
        print(f"[{num}] extrait: {commercial.relative_to(MAIN_DIR)}")
        print(f"      vers:    {dest.relative_to(MAIN_DIR)}")
        if not DRY_RUN:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(commercial), str(dest))

    if DRY_RUN:
        print("\n== DRY RUN : rien n'a été modifié. ==")


if __name__ == "__main__":
    main()