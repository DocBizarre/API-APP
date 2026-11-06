"""
EMS – Import CSV du parc clients & moteurs
Lit un fichier CSV, mappe les colonnes vers les champs DB, et déduplique par N° série.
"""

import csv
import io
from pathlib import Path

from ems_client import api as db


# Mapping par défaut : nom de colonne CSV → champ DB
# Plusieurs alias possibles par champ (essai dans l'ordre, insensible casse/espaces)
DEFAULT_MAPPING = {
    # Client
    "nom_client":        ["Tiers", "Client", "Nom client", "Société"],
    "type_client":       ["Type Client", "Type client", "Catégorie client"],
    # Moteur — champs principaux
    "navire":            ["Machine / Engin", "Machine/Engin", "Navire", "Engin", "Site"],
    "navire_immatriculation": ["Immatriculation", "Immatriculation navire", "N° immatriculation"],
    "navire_port_attache":    ["Port d'attache", "Port attache", "Port"],
    "num_serie":         ["N° Série", "N° Serie", "Numéro de série", "Num série", "N°Série"],
    "ref_constructeur":  ["Ref Constructeur", "Réf. Constructeur", "Ref constructeur"],
    "application":       ["Application"],
    "type_moteur":       ["Type", "Type moteur", "Type moteur / inverseur"],
    "typologie":         ["Typologie"],
    "marque":            ["Marque"],
    "code_affaire":      ["Code Affaire", "Code affaire", "N° Affaire"],
    "machine":           ["Machine", "Type machine", "Modèle"],
    "date_mise_service": ["Date mise en service", "Mise en service", "Date MES", "MES"],
    "duree_garantie":    ["Durée garantie", "Garantie (mois)", "Garantie mois", "Garantie"],
    "puissance_rpm":     ["Puissance/RPM", "Puissance RPM", "Puissance"],
    "puissance_pme_rpm": ["Puissance PME/RPM", "Puissance PME RPM", "Puissance PME"],
    # Moteur — champs client utilisateur final (ajoutables manuellement dans l'UI)
    "client_utilisateur_nom":     ["Client utilisateur", "Utilisateur final"],
    "client_utilisateur_email":   ["Email utilisateur", "Email utilisateur final"],
    "client_utilisateur_tel":     ["Tél. utilisateur", "Téléphone utilisateur"],
    "client_utilisateur_adresse": ["Adresse utilisateur", "Adresse utilisateur final"],
}


def _norm(s):
    """Normalisation pour matching de colonnes."""
    return (s or "").strip().lower().replace("°", "").replace(" ", "")


# Mapping par défaut pour le catalogue des références produits (table `pieces`,
# utilisée par les lignes des bons de commande / intentions d'achat).
# Ordre = du plus spécifique au plus générique : une colonne déjà affectée
# n'est plus proposée aux champs suivants (« Prix d'achat » ne doit pas aussi
# être prise comme prix de vente).
PIECES_MAPPING = {
    # Colonnes fournisseur d'abord : « Réf. fournisseur » ne doit pas être prise
    # comme référence produit, ni « Fournisseur » comme marque.
    "ref_fournisseur": ["Réf. fournisseur", "Ref. fournisseur", "Réf fournisseur",
                        "Ref fournisseur", "Référence fournisseur", "Reference fournisseur",
                        "Supplier ref", "Supplier reference", "Vendor ref"],
    "fournisseur": ["Fournisseur", "Supplier", "Vendor", "Distributeur"],
    "reference":  ["Référence", "Reference", "Réf", "Ref", "Réf.", "Ref.", "P/N", "PN",
                   "Part Number", "Part No", "Code article", "Code produit", "Code", "SKU"],
    "libelle":    ["Libellé", "Libelle", "Désignation", "Designation", "Description",
                   "Article", "Produit", "Nom"],
    "marque":     ["Marque", "Brand", "Fabricant", "Constructeur"],
    "prix_achat": ["Prix d'achat", "Prix achat", "Prix d achat", "PA", "PA HT",
                   "Coût", "Cout", "Prix fournisseur", "Prix net"],
    "prix_vente": ["Prix de vente", "Prix vente", "PV", "PV HT", "Tarif", "Prix public",
                   "Prix HT", "Prix"],
    "notes":      ["Notes", "Note", "Commentaire", "Commentaires", "Remarque"],
}


def detect_columns(headers, aliases_map=None):
    """
    Auto-détecte le mapping en cherchant chaque champ DB dans les en-têtes CSV.
    `aliases_map` : {champ: [alias...]} (défaut : DEFAULT_MAPPING, parc moteurs).
    Une même colonne n'est jamais affectée à deux champs.
    Retourne un dict {field: column_index_or_None}.
    """
    aliases_map = DEFAULT_MAPPING if aliases_map is None else aliases_map
    norm_headers = [_norm(h) for h in headers]
    mapping = {}
    used = set()
    for field, aliases in aliases_map.items():
        idx = None
        for alias in aliases:
            target = _norm(alias)
            for i, h in enumerate(norm_headers):
                if h == target and i not in used:
                    idx = i
                    break
            if idx is not None:
                break
        mapping[field] = idx
        if idx is not None:
            used.add(idx)
    return mapping


def read_csv_preview(path, max_rows=15, delimiter=None, encoding=None, aliases_map=None):
    """
    Lit le CSV et retourne (headers, rows_preview, total_lines, detected_mapping, used_delim, used_enc).
    Détection auto du séparateur et de l'encodage si non fournis.
    """
    path = Path(path)
    raw = path.read_bytes()

    # Détection encodage
    if encoding is None:
        for enc in ("utf-8-sig", "utf-8", "cp1252", "iso-8859-1", "latin-1"):
            try:
                text = raw.decode(enc)
                encoding = enc
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")
            encoding = "utf-8"
    else:
        text = raw.decode(encoding, errors="replace")

    # Détection séparateur
    if delimiter is None:
        sample = "\n".join(text.splitlines()[:5])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            # Fallback : compter les occurrences
            counts = {sep: sample.count(sep) for sep in [";", ",", "\t", "|"]}
            delimiter = max(counts, key=counts.get) if counts else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return [], [], 0, {}, delimiter, encoding

    headers = rows[0]
    data = rows[1:]
    preview = data[:max_rows]
    mapping = detect_columns(headers, aliases_map)
    return headers, preview, len(data), mapping, delimiter, encoding


def _cell(row, idx):
    """Récupère une cellule en gérant les index None ou hors limites."""
    if idx is None or idx < 0 or idx >= len(row):
        return ""
    v = row[idx]
    return v.strip() if v else ""


def import_rows(path, mapping, delimiter, encoding,
                skip_empty_serie=False, dry_run=False, progress_cb=None):
    """
    Importe les lignes du CSV.

    Stratégie de dédoublonnage :
      - Par N° série (col `num_serie`) : un seul moteur créé par N° série unique.
      - Si N° série vide ET skip_empty_serie=True : ligne ignorée.
      - Si N° série vide ET skip_empty_serie=False : moteur quand même créé
        avec un N° généré "AUTO-NNNN".
      - Clients dédoublonnés par nom (insensible casse/espaces).

    Retourne un dict avec les stats : {
        'clients_crees', 'clients_existants',
        'moteurs_crees', 'moteurs_mis_a_jour', 'moteurs_doublons',
        'lignes_ignorees', 'erreurs'  (liste de tuples (n_ligne, msg))
    }
    """
    stats = {
        "clients_crees": 0, "clients_existants": 0,
        "moteurs_crees": 0, "moteurs_mis_a_jour": 0, "moteurs_doublons": 0,
        "lignes_ignorees": 0, "lignes_total": 0,
        "erreurs": [],
    }

    path = Path(path)
    text = path.read_bytes().decode(encoding, errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return stats
    data = rows[1:]
    stats["lignes_total"] = len(data)

    # Caches en mémoire pour cette import
    clients_cache = {}    # nom_normalisé → client_id
    series_vues = set()    # N° série déjà traités dans CE batch (dédoublonnage)
    auto_counter = 1

    for i, row in enumerate(data, start=2):  # ligne 2 = première ligne de données
        if progress_cb:
            progress_cb(i - 1, len(data))

        nom_client  = _cell(row, mapping.get("nom_client"))
        num_serie   = _cell(row, mapping.get("num_serie"))

        # Ligne complètement vide ?
        if not any(_cell(row, idx) for idx in mapping.values() if idx is not None):
            stats["lignes_ignorees"] += 1
            continue

        # N° série vide
        if not num_serie:
            if skip_empty_serie:
                stats["lignes_ignorees"] += 1
                continue
            # Générer un N° série automatique unique
            while True:
                gen = f"AUTO-{auto_counter:04d}"
                auto_counter += 1
                if gen not in series_vues and not db.find_moteur_by_serie(gen):
                    num_serie = gen
                    break

        # Dédoublonnage strict par N° série dans CE batch
        if num_serie in series_vues:
            stats["moteurs_doublons"] += 1
            continue
        series_vues.add(num_serie)

        # Récupérer ou créer le client + créer/mettre à jour le moteur.
        # Tout est dans le même bloc try/except : une erreur sur UNE ligne
        # (client ou moteur) ne doit pas interrompre le traitement des
        # lignes suivantes.
        try:
            client_id = ""
            if nom_client:
                nom_norm = nom_client.strip().lower()
                if nom_norm in clients_cache:
                    client_id = clients_cache[nom_norm]
                else:
                    existant = db.find_client_by_nom(nom_client)
                    if existant:
                        client_id = existant["id"]
                        stats["clients_existants"] += 1
                    else:
                        if not dry_run:
                            client_id = db.upsert_client({
                                "nom": nom_client.strip(),
                                "contact": "", "email": "",
                                "telephone": "", "adresse": "",
                            })
                        else:
                            client_id = f"DRY-{nom_norm}"
                        stats["clients_crees"] += 1
                    clients_cache[nom_norm] = client_id

            moteur_data = _build_moteur_data(row, mapping, client_id, num_serie)

            existant = db.find_moteur_by_serie(num_serie)
            if existant:
                if not dry_run:
                    # Mise à jour partielle : une colonne absente/vide dans CE
                    # CSV ne doit pas effacer une valeur déjà en base (ex :
                    # réimport d'un fichier "navires" sans colonne client, qui
                    # écraserait sinon le client_id de tous les moteurs).
                    update_data = {k: v for k, v in moteur_data.items() if v}
                    db.upsert_moteur(update_data, moteur_id=existant["id"])
                stats["moteurs_mis_a_jour"] += 1
            else:
                if not dry_run:
                    db.upsert_moteur(moteur_data)
                stats["moteurs_crees"] += 1
        except Exception as e:
            stats["erreurs"].append((i, str(e)))

    return stats


def _build_moteur_data(row, mapping, client_id, num_serie):
    return {
        "client_id":        client_id,
        "num_serie":        num_serie,
        "navire":           _cell(row, mapping.get("navire")),
        "navire_immatriculation": _cell(row, mapping.get("navire_immatriculation")),
        "navire_port_attache":    _cell(row, mapping.get("navire_port_attache")),
        "machine":          (_cell(row, mapping.get("machine"))
                             or _cell(row, mapping.get("ref_constructeur"))
                             or _cell(row, mapping.get("type_moteur"))),
        "type_moteur":      _cell(row, mapping.get("type_moteur")),
        "date_mise_service":_cell(row, mapping.get("date_mise_service")),
        "duree_garantie":   _cell(row, mapping.get("duree_garantie")),
        "marque":           _cell(row, mapping.get("marque")),
        "application":      _cell(row, mapping.get("application")),
        "typologie":        _cell(row, mapping.get("typologie")),
        "puissance_rpm":    _cell(row, mapping.get("puissance_rpm")),
        "puissance_pme_rpm": _cell(row, mapping.get("puissance_pme_rpm")),
        "ref_constructeur": _cell(row, mapping.get("ref_constructeur")),
        "code_affaire":     _cell(row, mapping.get("code_affaire")),
        "type_client":      _cell(row, mapping.get("type_client")),
        "client_utilisateur_nom":     _cell(row, mapping.get("client_utilisateur_nom")),
        "client_utilisateur_email":   _cell(row, mapping.get("client_utilisateur_email")),
        "client_utilisateur_tel":     _cell(row, mapping.get("client_utilisateur_tel")),
        "client_utilisateur_adresse": _cell(row, mapping.get("client_utilisateur_adresse")),
    }


# ═══════════════════════════════════════════════════════════════════════════
#   Import du catalogue des références produits (table `pieces`)
# ═══════════════════════════════════════════════════════════════════════════

def parse_prix(val) -> float:
    """« 1 234,56 € » / « 1234.56 » / « 1.234,56 » → 1234.56 ; vide ou illisible → 0."""
    s = str(val or "").strip().replace("€", "").replace("\u00a0", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        # le dernier séparateur rencontré est le séparateur décimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return round(float(s), 4)
    except ValueError:
        return 0.0


def _read_all_rows(path, delimiter, encoding):
    text = Path(path).read_bytes().decode(encoding or "utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return rows[1:] if rows else []


def import_pieces_rows(path, mapping, delimiter, encoding,
                       skip_doublons=True, dry_run=False, progress_cb=None,
                       fournisseur_defaut=""):
    """
    Importe le catalogue des références produits depuis le CSV, selon le
    mapping {champ: index_colonne} choisi dans l'écran d'affectation des colonnes.
    Les lignes sans référence sont ignorées. Référence déjà en base :
    skip_doublons=True → complète seulement les champs vides ; False → mise à jour.
    dry_run=True → simulation côté serveur (rien n'est écrit).
    Fournisseur : colonne « fournisseur » de la ligne, sinon `fournisseur_defaut`
    (choisi pour tout le fichier) ; la référence est alors liée à ce fournisseur.

    Retourne {'lignes_total', 'lignes_ignorees', 'importees', 'mises_a_jour',
              'ignorees', 'completees', 'erreurs' (liste de (n_ligne, msg))}.
    """
    rows = _read_all_rows(path, delimiter, encoding)
    total = len(rows)
    pieces, ignorees_vides = [], 0
    for row in rows:
        ref = _cell(row, mapping.get("reference"))
        if not ref:
            ignorees_vides += 1
            continue
        pieces.append({
            "reference":  ref,
            "libelle":    _cell(row, mapping.get("libelle")),
            "marque":     _cell(row, mapping.get("marque")),
            "notes":      _cell(row, mapping.get("notes")),
            "prix_achat": parse_prix(_cell(row, mapping.get("prix_achat"))),
            "prix_vente": parse_prix(_cell(row, mapping.get("prix_vente"))),
            "fournisseur":     _cell(row, mapping.get("fournisseur")),
            "ref_fournisseur": _cell(row, mapping.get("ref_fournisseur")),
        })

    res = {"importees": 0, "mises_a_jour": 0, "ignorees": 0, "completees": 0,
           "erreurs": 0, "details_erreurs": []}
    # Envoi par lots : un fichier de plusieurs milliers de lignes reste fluide
    # et la barre de progression avance.
    LOT = 1000
    for start in range(0, len(pieces), LOT):
        r = db.bulk_import_pieces(pieces[start:start + LOT],
                                  skip_doublons=skip_doublons, dry_run=dry_run,
                                  fournisseur=fournisseur_defaut)
        for k in ("importees", "mises_a_jour", "ignorees", "completees", "erreurs"):
            res[k] += r.get(k, 0) or 0
        res["details_erreurs"] += r.get("details_erreurs", []) or []
        if progress_cb:
            progress_cb(min(start + LOT, len(pieces)), len(pieces))
    if progress_cb:
        progress_cb(total, total)

    erreurs = [(0, m) for m in res["details_erreurs"]]
    if res["erreurs"] and not erreurs:
        erreurs = [(0, f"{res['erreurs']} ligne(s) invalide(s)")]
    return {
        "lignes_total":    total,
        "lignes_ignorees": ignorees_vides,
        "importees":       res["importees"],
        "mises_a_jour":    res["mises_a_jour"],
        "ignorees":        res["ignorees"],
        "completees":      res["completees"],
        "erreurs":         erreurs,
    }
