# EMS — Architecture API REST

Refonte de l'architecture en **client/serveur** : les apps Tkinter
(Bons, Parc, Garanties, Amélioration, BI) deviennent des **clients
légers** qui communiquent avec une **API REST centralisée**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          POSTE UTILISATEUR                          │
│                                                                     │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│   │   Bons   │  │   Parc   │  │Garanties │  │Amelio./BI│            │
│   │ (Tkinter)│  │ (Tkinter)│  │ (Tkinter)│  │ (Tkinter)│            │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│        └─────────────┴─────────────┴─────────────┘                  │
│                        │ (ems_client.api)                           │
│                        │ HTTP/JSON                                  │
└────────────────────────┼────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SERVEUR (NAS / PC central)                    │
│                                                                     │
│             ┌──────────────────────────────────┐                    │
│             │   EMS API   (FastAPI/uvicorn)    │                    │
│             │   http://serveur:8765            │                    │
│             │   /docs (Swagger UI)             │                    │
│             └────────────┬─────────────────────┘                    │
│                          │                                          │
│             ┌────────────▼─────────┐                                │
│             │   SQLite / Postgres  │                                │
│             │   (ems.db unique)    │                                │
│             └──────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

**Bénéfices :**
- **1 seule base de données** partagée, plus de copies/synchronisations
- **N postes** peuvent travailler en simultané sans verrouillage SQLite
- **Documentation API auto-générée** (Swagger UI sur `/docs`)
- Une **interface web** pourra être branchée plus tard sans rien casser
- **Tests automatisés** : `pytest ems_api/tests/`
- **Validation des données** systématique (Pydantic)

## Structure des dossiers

```
EMS/
├── ems_api/                ← SERVEUR (à installer 1x sur le NAS/PC central)
│   ├── main.py             FastAPI app
│   ├── config.py           Settings (env vars)
│   ├── database.py         Session SQLAlchemy
│   ├── models/             Modèles ORM (1 fichier/ressource)
│   ├── schemas/            Validation Pydantic (in/out)
│   ├── routers/            Endpoints REST (CRUD)
│   ├── services/           Logique métier (numérotation, PDF…)
│   ├── tests/              pytest
│   ├── migrate_from_legacy.py    Import de l'ancienne base
│   └── requirements.txt
│
├── ems_client/             ← SDK Python (installé sur chaque poste)
│   ├── __init__.py
│   └── api.py              Wrapper requests (drop-in remplacement)
│
├── ems_project/            ← Apps Tkinter (clients)
│   ├── main.py             from ems_client import api as db
│   └── …
├── garanties_app/
├── amelioration_app/
└── BI_app/
```

## Démarrage

### 1. Installer les dépendances

Sur le serveur :
```
pip install -r ems_api/requirements.txt
```

Sur chaque poste client : juste `requests` (déjà inclus dans
`requirements.txt`).

### 2. Lancer l'API

Depuis la racine du projet :
```
uvicorn ems_api.main:app --host 0.0.0.0 --port 8765
```

(Mettre `127.0.0.1` au lieu de `0.0.0.0` pour limiter au localhost.)

L'API expose alors :
- `http://serveur:8765/` — endpoint racine
- `http://serveur:8765/docs` — **Swagger UI** (test interactif)
- `http://serveur:8765/redoc` — documentation alternative
- `http://serveur:8765/health` — endpoint santé (monitoring)

### 3. Migrer les données existantes (une seule fois)

```
python -m ems_api.migrate_from_legacy
```

Copie clients, moteurs, interventions, garanties, améliorations,
techniciens de l'ancienne base `ems_project/data/ems.db` vers la
nouvelle `ems_api/data/ems.db`.

### 4. Configurer les apps clientes

Sur chaque poste, définir l'URL de l'API :
```
set EMS_API_URL=http://serveur-ems:8765
```
(Sous Windows ; permanent via Paramètres système → Variables d'env.)

Si l'API tourne sur le même PC que les apps :
```
EMS_API_URL=http://127.0.0.1:8765        (défaut, rien à faire)
```

### 5. Migrer les apps Tkinter

Dans chaque fichier `database.py` consommé par les apps, remplacer
les imports par le wrapper :

**Avant :**
```python
import database as db
db.get_clients()
```

**Après :**
```python
from ems_client import api as db
db.get_clients()    # ← exactement la même API
```

C'est tout. La signature des fonctions est identique.

## Sécurité (optionnel)

Pour activer l'authentification par clé d'API :

Sur le serveur :
```
set EMS_API_KEY=ma-cle-secrete-tres-longue-XXXXX
```

Sur chaque poste client :
```
set EMS_API_KEY=ma-cle-secrete-tres-longue-XXXXX
```

L'API rejettera (401) toute requête sans header `X-API-Key` valide.

## Tests

```
cd ems_api
pytest tests/ -v
```

## État d'avancement

| Ressource           | Modèle | Schéma | Router | SDK | Status |
|---------------------|--------|--------|--------|-----|--------|
| Clients             |   ✓    |   ✓    |   ✓    |  ✓  | ✅ Complet |
| Moteurs             |   ✓    |   ✓    |   ✓    |  ✓  | ✅ Complet |
| Techniciens         |   ✓    |   ✓    |   ✓    |  ✓  | ✅ Complet |
| Interventions       |   ✓    |   ✓    |   ✓    |  ✓  | ✅ Complet |
| Signatures          |   *    |   ✓    |   ✓    |  ✓  | ✅ Complet |
| Garanties           |   ✓    |   ✓    |   ✓    |  ✓  | ✅ Complet |
| Améliorations       |   ✓    |   ✓    |   ✓    |  ✓  | ✅ Complet |
| Documents (HTML/PDF)|   —    |   —    |   —    |  —  | À faire |

*Stockées dans la table `interventions`.

## Plan de complétion

Pour chaque ressource restante, le pattern est strictement le même que
pour Clients. Vu un exemple complet, tu peux soit :

1. **Procéder progressivement** : finir une ressource à la fois en
   gardant l'ancien `database.py` en parallèle, et migrer chaque app
   au fur et à mesure.
2. **Me redemander la suite** : je peux te livrer Moteurs +
   Interventions + Garanties + Améliorations + Techniciens d'un coup
   (≈ 1500 lignes au total, sur le même modèle).

L'ordre recommandé pour migrer :

1. **Moteurs** (dépend juste de Clients)
2. **Techniciens** (indépendant)
3. **Interventions** (dépend de Clients + Moteurs + Techniciens)
4. **Signatures** (fait partie d'Interventions)
5. **Garanties** (dépend de Clients + Moteurs)
6. **Améliorations** (dépend de Clients)
7. **Documents** (génération HTML/PDF via le service existant)

## Migration progressive sans casser l'existant

Pour ne pas tout casser d'un coup :

1. Garde l'ancien `ems_project/database.py` en place
2. Lance l'API en parallèle
3. Migre les données 1 fois avec `migrate_from_legacy`
4. Dans `main.py` de l'app Bons, change UNE seule fonction à la fois
   pour utiliser `ems_client.api`. Teste. Si OK, passe à la suivante.
5. Une fois tout migré, supprime l'ancien `database.py`.
