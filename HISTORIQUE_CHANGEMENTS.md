# Historique des changements — EMS (Emeraude Moteurs Systèmes)

> Document généré le 2026-08-04 à partir de l'historique Git (dépôt principal `APP API` + sous-module `ems_project`) et des dates de modification des fichiers non encore commités. À mettre à jour à chaque nouveau commit, ou en relançant une génération.
>
> Légende des apps : **BI_app** (tableau de bord), **affaire_app / suivi_affaires.html** (suivi d'affaires web), **garanties_app** (garanties), **pieces_app** (pièces détachées), **ems_api** (backend FastAPI, commun à toutes les apps), **ems_client** (client API partagé), **ems_project** (sous-module : app Parc moteurs, app Bons d'intervention), **shared** (génération PDF, mails, imports CSV).

---

## Mai 2026 — Démarrage du projet

### 2026-05-22 — Premiers commits (Stagiaire BE)
- Initialisation du dépôt (`first commit`, `commit initial`).

### 2026-05-26 — Stabilisation API et bons d'intervention
- Correctifs sur des dysfonctionnements de l'API.
- Correctifs sur les interventions + ajout de la date de clôture à l'ouverture automatique d'un bon d'intervention.

### 2026-05-28 — Import/export terrain
- Changements pour l'import/export utilisés sur le terrain, plus plusieurs demandes majeures côté métier.

### 2026-06-02 — Premier packaging
- Export de l'application en `.exe` + mise en place du versionnage.
- Corrections de features mineures.

### 2026-06-03 — Ajustements
- Corrections diverses ("pour TT demain").

---

## Juin 2026 — Reprise par DocBizarre (avec Claude Code)

### 2026-06-08 — Reprise du projet
- Push global de nouvelles features et correctifs.
- Fix de la signature (bons d'intervention).
- Commit de test de trame.

### 2026-06-09 — Bons d'intervention
- Changement sur la gestion des jours dans le bon d'intervention.
- Fix génération PDF.

### 2026-06-15 — Grosse journée : mode hors ligne + naissance du suivi d'affaires web
- **App Bons** : ajout du mode hors ligne + correctifs mineurs.
- **Suivi d'affaires** : création de la nouvelle interface web autonome `suivi_affaires.html` — tableau de bord, liste des affaires avec filtres, chapitres modulables (drag & drop, détails JSON libres), liaison aux moteurs, interventions liées, commentaires. Le launcher ouvre désormais cette page dans le navigateur.
- Fix du modal "lier un moteur" (dropdown inline, modal élargi, résultats enrichis marque/type/navire/machine/client).
- Refonte du modal "chapitre" : sélecteur de moteur avec chips + recherche, catégories modulables (ajout libre, mémorisées en local), bouton "Modèle" pré-remplissant les champs selon la catégorie.
- Refonte de la navigation : la sidebar liste est remplacée par un tableau paginé, triable, avec recherche et filtres par statut — pensé pour tenir sur des milliers d'affaires.
- **Parc moteurs** : ajout des sous-ensembles de moteur (1ère version avec modèle dédié `SousEnsemble` + CRUD REST + onglet dédié dans la fiche moteur, côté API et côté GUI/submodule).

### 2026-06-16 — Fiabilisation des sous-ensembles moteurs
- Câblage backend manquant des sous-ensembles (table jamais créée, route jamais montée — corrigé).
- Refonte : un sous-ensemble devient un **Moteur auto-référencé** (`parent_moteur_id`) au lieu d'un modèle dédié — même formulaire, hiérarchie affichée avec flèche ▶/▼ dans la liste des moteurs.
- Préremplissage du sous-ensemble limité au contexte partagé avec le moteur parent (navire, machine, client…), sans copier les champs propres (marque, type, réf. constructeur…).
- Fix : `.gitmodules` manquant pour le sous-module `ems_project` (un clone frais n'avait pas l'URL distante).
- Nettoyage : arrêt du suivi Git des artefacts générés (build/dist/exe, `__pycache__`, bases de données locales).

### 2026-06-23 — Journée majeure : auto-updater, contacts, facturation, PDF, mails
- **Auto-updater** : vérification de version + téléchargement + application à chaud côté client, endpoint `/updates/latest` côté API, badge de mise à jour dans le launcher. Plusieurs correctifs le même jour (manifest serveur non écrasé, encodage script de déploiement, imports PyInstaller).
- **Build & déploiement** : zippage automatique de la distribution après compilation, script `publish_release.ps1` (publication sur le serveur + mise à jour du manifest), prompt de bump de version avant compilation.
- **Contacts** : nouveau modèle `Contact` avec mémorisation automatique des signataires/demandeurs, API CRUD, champs signataire/demandeur sur les interventions.
- **Affaires** : nouveaux champs facturation/transport (prix HT, TVA, fournisseur, échéances, transporteur, suivi transport…), statut **"À facturer"**, sous-dossiers automatiques par chapitre.
- **Moteurs** : endpoints CRUD dédiés aux sous-ensembles (`/moteurs/{id}/sous-ensembles`).
- **Garanties** : endpoint de notification client/technicien.
- **PDF** : nouveau convertisseur d'accusé de réception ERP → mise en page EMS (`convertisseurpdf.py` + endpoint `/pdf/accuse-reception`).
- **Statistiques** : statut "Date à programmer" + widget correspondant sur le dashboard BI.
- **Mails** : templates HTML avec logo EMS et coordonnées en pied de message.
- **Bon d'intervention (PDF)** : "Temps de trajet" renommé en "Km parcourus", badge garantie, corrections de calcul des totaux.
- **App Affaire** : refonte en mini-serveur web local (fin de l'UI Tkinter) ouvrant `suivi_affaires.html` dans le navigateur.
- **App Garanties** : logo EMS en en-tête + intégration des mails HTML.
- **BI** : animations (fadeInUp, glow, pulse), support "reduced motion".
- **Suivi d'affaires** : badge "À facturer", drag-and-drop des champs de modèle, panneau sous-ensembles moteur.
- Version bumpée à **1.9.0**.

---

## Juillet 2026

### 2026-07-09 — Système de bons de commande + refonte suivi d'affaires
Commit volumineux (41 fichiers, ~6100 lignes ajoutées) :
- **Bons de commande** : nouveau modèle, router (`ems_api/routers/bons_commande.py`) et schémas dédiés — création, suivi, montants.
- **Numérotation** : nouveau service centralisé de génération de numéros séquentiels (affaires, bons, bons de commande…).
- **Admin** : nouvelle page `admin_numerotation.html` pour piloter/corriger la numérotation.
- **Config** : nouveau module `ems_api/config.py`.
- **Types de moteur** et **modèles de chapitre** : nouveaux routers dédiés.
- **PDF affaire** (`shared/affaire_pdf.py`) : réécriture importante (+639 lignes).
- **Suivi d'affaires** : très grosse évolution de `suivi_affaires.html` (+3239 lignes) — nombreux ajouts fonctionnels autour des bons de commande et de la gestion d'affaire.
- **Sous-module ems_project** : statut "Date à programmer", accès au dossier racine des garanties, améliorations des dialogues Garantie/Bon/Moteur.

*(Dernier commit à ce jour : `7934172`, 2026-07-09 16:35 — mise à jour du pointeur de sous-module.)*

---

## Travaux en cours depuis le 9 juillet (non commités)

Aucun commit Git n'a été fait depuis le 9 juillet ; la section ci-dessous reconstitue une chronologie à partir des dates de dernière modification des fichiers actuellement en attente de commit (`git status`). Elle donne une idée du suivi jour par jour, mais reste approximative (une modification peut avoir été retouchée plusieurs fois).

### 2026-07-15 — Nouveau module Fournisseurs
- Nouveau modèle `Fournisseur` + router `/fournisseurs` (liste, upsert automatique par nom/contact/email).

### 2026-07-16 — Tests numérotation
- Ajout d'un test dédié à la remise à zéro annuelle de la numérotation (`test_numerotation_reset_annuel.py`).

### 2026-07-24 — Pièces détachées
- Évolution du modèle et du schéma `Piece` (préparation du champ prix de vente, cf. 28/07).

### 2026-07-28 — Navires + refonte app Pièces
- Nouveau modèle `Navire` + router `/navires` (recherche par nom, upsert) + schéma dédié.
- Refonte importante de `pieces_app/app_pieces.py` (+393 lignes) et du router `/pieces`.
- Ajout du champ **prix de vente** sur les pièces (en plus du prix d'achat déjà existant).
- Ajustements `shared/bon_generator.py` et `ems_api/config.py`.

### 2026-07-29 — Devis (API) + mails de devis
- Nouveau router `/devis` : CRUD complet, listing par statut, **transformation d'un devis en affaire**, génération PDF du devis.
- `shared/mailer.py` : nouveau template et fonction d'envoi d'e-mail de devis (confirmation de prise en compte + devis joint).

### 2026-07-31 — Bons de commande enrichis
- `convertisseurpdf.py` : ajustements.
- Modèle/schéma `BonCommande` étendus : adresse de livraison structurée, historique de **paiements**, frais de port, référence/lien **Monstock**.

### 2026-08-03 — Journée dense : navires sur moteurs/affaires, PDF affaire, garanties, imports CSV
- Modèle `Devis` finalisé (champs navire, acompte %, délai de paiement, moteurs supplémentaires, destinataire, demande client…).
- Modèles/schémas `Intervention` et `Moteur` étendus (rattachement navire — immatriculation, port d'attache —, puissance/RPM et puissance PME/RPM).
- `garanties_app/app_garanties.py` : ajustements.
- `shared/csv_importer.py` : mapping enrichi (immatriculation navire, port d'attache, puissance/RPM) et nettoyage d'anciens champs (cylindrée, famille, collection retirés du mapping par défaut).
- `BI_app/ems_bi.html` : ajustements.
- `shared/affaire_pdf.py` : réécriture majeure (+1096 lignes).
- Modèle/schéma `Affaire` étendus : adresse de livraison, dates FAT/fin FAT, champ "complexité", lots vendus.
- Router `/contacts` et `ems_client/api.py` : évolutions liées aux nouveaux champs contact (prénom, entreprise).

### 2026-08-04 — Numérotation devis, câblage final, migrations DB
- `ems_api/services/numerotation.py` : génération de numéros de devis (`DEV-AAAA-XXXX`) + utilitaire d'extraction du code affaire court.
- Router `/moteurs` et router `/bons_commande` : ajustements liés aux nouveaux champs.
- `suivi_affaires.html` : suite des évolutions (+2352 lignes au total sur l'ensemble des modifications non commitées).
- Modèle `Contact` : ajout des champs prénom / entreprise.
- Routers `/interventions` et `/affaires` : ajustements.
- `ems_api/database.py` : plus de 30 nouvelles migrations de colonnes (livraison affaire/BC, paiements BC, interlocuteurs fournisseur, champs devis, champs navire sur moteurs/affaires, complexité affaire…) + migrations ponctuelles de reprise de données (ancienne adresse fournisseur → nouveaux champs structurés, ancien contact fournisseur → liste d'interlocuteurs).

**Fichiers non encore suivis par Git à cette date** (nouveaux modules pas encore ajoutés) : `ems_api/models/devis.py`, `ems_api/models/fournisseur.py`, `ems_api/models/navire.py`, `ems_api/routers/devis.py`, `ems_api/routers/fournisseurs.py`, `ems_api/routers/navires.py`, `ems_api/schemas/contact.py`, `ems_api/schemas/devis.py`, `ems_api/schemas/navire.py`, `ems_api/tests/test_numerotation_reset_annuel.py`, ainsi qu'un dossier `EMS TEST/`.

> ⚠️ Tout ce module Devis + Fournisseurs + Navires + les évolutions Bons de commande/Affaires/Moteurs ci-dessus représente un ensemble de travail conséquent qui n'a **jamais été commité**. Un commit (ou plusieurs commits thématiques : Devis, Navires/Fournisseurs, Bons de commande, migrations DB) est recommandé pour sécuriser ce travail et obtenir un historique daté précis à partir de maintenant.

---

## Sous-module `ems_project` (apps Parc moteurs / Bons) — repères indépendants
- **2026-05-12** : premiers commits du sous-module (antérieurs à l'extraction du dépôt principal).
- **2026-06-08** : "Test push".
- **2026-06-15 → 2026-07-09** : suit en miroir les évolutions "sous-ensembles moteurs" et "statut Date à programmer / garanties" détaillées ci-dessus (les commits du dépôt principal mettent à jour le pointeur de sous-module à chaque évolution).
