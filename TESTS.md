# Trame de test EMS — avant push en production

> **Mode d'emploi** : cocher chaque case au fur et à mesure. Un `[ ]` non coché = bloquant avant push.  
> Renseigner la colonne **Résultat** : ✅ OK · ❌ KO (décrire) · ⚠️ dégradé acceptable

---

## 0. Pré-requis

| # | Vérification | Résultat |
|---|---|---|
| 0.1 | API démarrée (`py ems_api/main.py` ou service), accessible sur `http://192.168.1.47:8765` | |
| 0.2 | `GET /health` → `{"status":"ok"}` | |
| 0.3 | `GET /` retourne version + auth status | |
| 0.4 | Base de données non vide (au moins 1 client, 1 moteur) | |
| 0.5 | config.ini présent dans `EMS_Distribution/` avec URL et dossiers corrects | |

---

## 1. API — Backend

### 1.1 Clients

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.1.1 | Lister tous les clients | `GET /clients` | 200, liste JSON | |
| 1.1.2 | Rechercher par nom (param `search`) | `GET /clients?search=ocea` | Filtre correct | |
| 1.1.3 | Créer un client | `POST /clients` body `{"nom":"Test SA"}` | 201, id généré | |
| 1.1.4 | Dupliquer un client (même nom) | `POST /clients` même nom | Merge ou 409 sans crash | |
| 1.1.5 | Modifier un client | `PUT /clients/{id}` | 200, champs mis à jour | |
| 1.1.6 | Supprimer un client sans dépendances | `DELETE /clients/{id}` | 200 | |
| 1.1.7 | Supprimer un client avec moteurs liés | `DELETE /clients/{id}` | Cascade ou erreur explicite | |

### 1.2 Moteurs

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.2.1 | Lister moteurs | `GET /moteurs` | 200 | |
| 1.2.2 | Recherche multi-champ (navire, marque, n° série) | `GET /moteurs?search=...` | Filtre correct | |
| 1.2.3 | Par n° série exact | `GET /moteurs/by-serie/XXX` | 200 ou 404 propre | |
| 1.2.4 | Garanties expirantes | `GET /moteurs/garantie-expirante?jours_max=90` | Liste cohérente | |
| 1.2.5 | Créer moteur (n° série unique) | `POST /moteurs` | 201 | |
| 1.2.6 | Créer moteur (n° série dupliqué) | `POST /moteurs` | Erreur explicite, pas de crash | |
| 1.2.7 | Modifier moteur | `PUT /moteurs/{id}` | 200 | |
| 1.2.8 | Supprimer moteur | `DELETE /moteurs/{id}` | 200 | |

### 1.3 Interventions

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.3.1 | Lister toutes | `GET /interventions` | 200 | |
| 1.3.2 | Filtrer par statut | `GET /interventions?statut=En cours` | Filtre correct | |
| 1.3.3 | Filtrer par urgence | `GET /interventions?urgence=Critique` | Filtre correct | |
| 1.3.4 | Urgentes | `GET /interventions/urgentes` | Uniquement En cours + urgente/critique | |
| 1.3.5 | Non notifiées | `GET /interventions/non-notifies` | Bons sans notif client ou tech | |
| 1.3.6 | Créer bon | `POST /interventions` | 201, num_bon auto-généré | |
| 1.3.7 | Modifier bon | `PUT /interventions/{id}` | 200, version incrémentée | |
| 1.3.8 | Supprimer bon | `DELETE /interventions/{id}` | 200 | |
| 1.3.9 | Générer HTML | `GET /interventions/{id}/document.html` | HTML valide, pas de 500 | |
| 1.3.10 | Signature client | `POST /interventions/{id}/signature-client` body base64 | 200, signature stockée | |

### 1.4 Garanties

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.4.1 | Lister | `GET /garanties` | 200 | |
| 1.4.2 | Filtrer par statut et attribution | `GET /garanties?statut=Suivi EMS&attribution=Constructeur` | Filtre correct | |
| 1.4.3 | Garanties d'un moteur | `GET /garanties/by-moteur/{id}` | Liste liée au moteur | |
| 1.4.4 | Créer garantie | `POST /garanties` | 201, num_ems auto | |
| 1.4.5 | Modifier garantie | `PUT /garanties/{id}` | 200 | |
| 1.4.6 | Supprimer garantie | `DELETE /garanties/{id}` | 200 | |
| 1.4.7 | Générer HTML fiche | `GET /garanties/{id}/document.html` | HTML valide | |

### 1.5 Améliorations

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.5.1 | Lister | `GET /ameliorations` | 200 | |
| 1.5.2 | Filtrer statut + priorité | `GET /ameliorations?statut=En cours&priorite=Haute` | Filtre correct | |
| 1.5.3 | Stats | `GET /ameliorations/stats` | Compteurs par statut cohérents | |
| 1.5.4 | Créer ticket | `POST /ameliorations` | 201, num_ticket auto | |
| 1.5.5 | Modifier ticket | `PUT /ameliorations/{id}` | 200 | |
| 1.5.6 | Supprimer ticket | `DELETE /ameliorations/{id}` | 200 | |
| 1.5.7 | Générer HTML | `GET /ameliorations/{id}/document.html` | HTML valide | |

### 1.6 Techniciens

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.6.1 | Lister | `GET /techniciens` | 200 | |
| 1.6.2 | Créer technicien | `POST /techniciens` | 201 | |
| 1.6.3 | Dupliquer (même nom) | `POST /techniciens` | Merge ou erreur sans crash | |
| 1.6.4 | Modifier | `PUT /techniciens/{id}` | 200 | |
| 1.6.5 | Supprimer | `DELETE /techniciens/{id}` | 200 | |

### 1.7 Pièces

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.7.1 | Lister (défaut 500) | `GET /pieces` | 200, max 500 | |
| 1.7.2 | Recherche ref + libellé + marque | `GET /pieces?search=filtre` | Résultats filtrés | |
| 1.7.3 | Count | `GET /pieces/count` | Entier cohérent avec liste | |
| 1.7.4 | Par référence exacte | `GET /pieces/by-reference/REF123` | 200 ou 404 propre | |
| 1.7.5 | Créer pièce | `POST /pieces` | 201 | |
| 1.7.6 | Import bulk CSV | `POST /pieces/import-bulk` | 200, doublons ignorés | |
| 1.7.7 | Modifier | `PUT /pieces/{id}` | 200 | |

### 1.8 Configuration

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.8.1 | Lister types intervention | `GET /types-intervention` | Liste ordonnée | |
| 1.8.2 | Ajouter type | `POST /types-intervention` | 201 | |
| 1.8.3 | Renommer type | `PUT /types-intervention` | 200 | |
| 1.8.4 | Supprimer type | `DELETE /types-intervention/{libelle}` | 200 | |
| 1.8.5 | Lister marques moteur | `GET /marques-moteur` | ≥ 10 marques par défaut | |
| 1.8.6 | Lister statuts garantie | `GET /statuts-garantie` | Liste ordonnée | |

### 1.9 Stats & Dashboard

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.9.1 | Stats globales | `GET /stats` | Tous compteurs présents | |
| 1.9.2 | Config dashboard | `GET /config/dashboard-cards` | JSON valide | |
| 1.9.3 | Sauvegarder config dashboard | `POST /config/dashboard-cards` | 200, persisté | |

### 1.10 Admin & Sync

| # | Scénario | Méthode | Attendu | Résultat |
|---|---|---|---|---|
| 1.10.1 | Export DB | `GET /admin/export-db` | Fichier .db téléchargeable | |
| 1.10.2 | Sync pull | `POST /sync/pull` | Liste bons avec `version` | |
| 1.10.3 | Sync push sans conflit | `POST /sync/push` body `base_version` = version actuelle | 200, version incrémentée | |
| 1.10.4 | Sync push avec conflit | `POST /sync/push` body `base_version` < version actuelle | Liste des IDs en conflit retournée | |

---

## 2. App Bons (EMS_Bons.exe)

### 2.1 Démarrage

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 2.1.1 | Lancer EMS_Bons.exe | Fenêtre s'ouvre, pas d'erreur console | |
| 2.1.2 | Connexion API affichée dans barre de titre ou status bar | URL correcte visible | |
| 2.1.3 | Dashboard se charge avec les widgets actifs | Pas de widget vide/erreur | |

### 2.2 Dashboard

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 2.2.1 | Cartes stats affichées (En cours, À facturer, Clos, etc.) | Valeurs numériques cohérentes | |
| 2.2.2 | Widget Urgentes → liste des bons urgents/critiques | Bons En cours urgents visibles | |
| 2.2.3 | Widget Activité récente | Derniers bons modifiés visibles | |
| 2.2.4 | Widget Garanties expirantes | Cohérent avec données moteurs | |
| 2.2.5 | Double-clic sur un bon dans un widget → ouvre le détail | Formulaire bon s'ouvre | |
| 2.2.6 | Clic sur configuration dashboard → activer/désactiver un widget | Changement persisté après fermeture/réouverture | |

### 2.3 Liste des interventions

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 2.3.1 | Affichage de la liste complète | Colonnes correctes (urgence, num, client, navire, tech, date, notif) | |
| 2.3.2 | Filtre par statut (En cours / À facturer / Facturé / Clos) | Liste filtrée dynamiquement | |
| 2.3.3 | Filtre par urgence (Normale / Urgente / Critique) | Liste filtrée dynamiquement | |
| 2.3.4 | Recherche texte (num bon, client, n° série) | Résultats corrects | |
| 2.3.5 | Couleur urgence : Critique = rouge, Urgente = orange | Couleurs correctes dans la liste | |
| 2.3.6 | Double-clic → ouvre formulaire de détail | Formulaire pré-rempli | |
| 2.3.7 | Bouton Supprimer → confirmation + suppression | Bon disparu de la liste | |

### 2.4 Création d'un bon

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 2.4.1 | Sélectionner un client existant dans le combobox | Client auto-complété | |
| 2.4.2 | Sélectionner un moteur → infos moteur remplies automatiquement | Marque, navire, machine renseignés | |
| 2.4.3 | Sélectionner un moteur → le client lié se remplit si vide | Client auto-rempli | |
| 2.4.4 | Choisir type d'intervention dans le menu déroulant | Valeurs depuis DB (pas hardcodées) | |
| 2.4.5 | Choisir urgence → couleur badge/label change | Feedback visuel | |
| 2.4.6 | Ajouter un technicien via le picker | Technicien apparaît dans la sélection | |
| 2.4.7 | Ajouter plusieurs techniciens | Tous visibles, séparés par virgule en DB | |
| 2.4.8 | Enregistrer bon → num_bon auto-généré | Ex : `BON-2026-0042` | |
| 2.4.9 | Enregistrer sans client ou n° série → message d'erreur | Pas de crash, erreur explicite | |
| 2.4.10 | Cocher "garantie intervention" → champ visible | Comportement logique | |
| 2.4.11 | Saisir une date invalide (ex : 32/13/2026) | Message d'erreur, pas de crash | |
| 2.4.12 | Ajouter moteur supplémentaire via lien "＋ ajouter un moteur" | Ligne apparaît, valeurs sauvegardées | |

### 2.5 Génération du bon & email

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 2.5.1 | Bouton "Générer PDF / HTML" | Fichier créé dans le bon dossier (pas dans temp) | |
| 2.5.2 | Ouvrir le fichier généré → vérifier footer | Uniquement "9 Rue d'Armorique", pas de 9bis, pas de Fax | |
| 2.5.3 | Email client → brouillon s'ouvre (ou message indiquant de joindre manuellement) | Pas de boîte de dialogue Windows erreur | |
| 2.5.4 | Email client sans Outlook classique → message indiquant de joindre le fichier manuellement + dossier s'ouvre | Comportement gracieux | |
| 2.5.5 | Dossier Explorer s'ouvre positionné à droite (pas plein écran) | Fenêtre ~42% largeur, alignée à droite | |
| 2.5.6 | Email tech → même comportement | Idem 2.5.3 | |

### 2.6 Signatures

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 2.6.1 | Ouvrir un bon → zone de signature client visible | Canvas de signature présent | |
| 2.6.2 | Signer avec la souris → enregistrer | Signature base64 stockée | |
| 2.6.3 | Re-ouvrir le bon → signature affichée | Image correcte | |
| 2.6.4 | Signature tech idem | | |

---

## 3. App Parc (EMS_Parc.exe)

### 3.1 Démarrage

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 3.1.1 | Lancer EMS_Parc.exe | Fenêtre s'ouvre, onglets Clients / Moteurs / Techniciens visibles | |

### 3.2 Clients

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 3.2.1 | Liste clients affichée | Colonnes : nom, contact, email, téléphone | |
| 3.2.2 | Recherche par nom / email / contact | Filtre dynamique | |
| 3.2.3 | Créer client → formulaire + enregistrement | Apparaît dans la liste | |
| 3.2.4 | Modifier client | Champs mis à jour | |
| 3.2.5 | Supprimer client sans moteurs → OK | Disparu de la liste | |
| 3.2.6 | Import CSV clients | Colonnes détectées automatiquement, doublons ignorés | |

### 3.3 Moteurs

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 3.3.1 | Liste moteurs avec colonnes correctes | n° série, navire, marque, machine, type, date, garantie, statut_g | |
| 3.3.2 | Recherche multi-champ | Filtre par n° série, navire, marque, code affaire | |
| 3.3.3 | Créer moteur → formulaire | |
| 3.3.4 | Champ **Marque** → SearchableCombobox avec les marques DB | Pas un champ texte libre | |
| 3.3.5 | Bouton ⚙ à côté de Marque → ouvre dialogue gestion marques | Ajout / renommage / suppression | |
| 3.3.6 | Modifier une marque dans le dialogue → combobox mis à jour | Nouvelle valeur visible | |
| 3.3.7 | Modifier moteur | Champs mis à jour | |
| 3.3.8 | Supprimer moteur | Disparu de la liste | |
| 3.3.9 | Double-clic sur moteur → détail affiché | Marque, client, navire corrects | |

### 3.4 Techniciens

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 3.4.1 | Liste techniciens | Colonnes : nom, email, téléphone | |
| 3.4.2 | Créer technicien | Apparaît dans liste | |
| 3.4.3 | Email invalide → avertissement | Validation présente | |
| 3.4.4 | Modifier / Supprimer | Fonctionnel | |

---

## 4. App Garanties (EMS_Garanties.exe)

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 4.1 | Lancer EMS_Garanties.exe | Fenêtre s'ouvre | |
| 4.2 | Liste des garanties | Colonnes : num_ems, client, moteur, statut, attribution, montant | |
| 4.3 | Filtre par statut | Fonctionne | |
| 4.4 | Filtre par attribution | Fonctionne | |
| 4.5 | Créer une garantie → num_ems auto-généré | Ex : `GAR-2026-0012` | |
| 4.6 | Lier à un moteur existant | Moteur visible dans la fiche | |
| 4.7 | Modifier garantie | Champs mis à jour | |
| 4.8 | Supprimer garantie | Disparu de la liste | |
| 4.9 | Générer fiche HTML | Fichier créé dans `garanties/<num_ems>/` (pas dans temp) | |
| 4.10 | Ouvrir fiche HTML → footer correct | "9 Rue d'Armorique", pas de 9bis, pas de Fax | |
| 4.11 | Notification email | Même comportement que bons (pas de boîte erreur Windows) | |

---

## 5. App Amélioration (EMS_Amelioration.exe)

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 5.1 | Lancer EMS_Amelioration.exe | Fenêtre s'ouvre | |
| 5.2 | Liste des tickets | Colonnes : num_ticket, titre, client, priorité, statut, technicien, date cible | |
| 5.3 | Filtre par statut | Fonctionne | |
| 5.4 | Filtre par priorité | Fonctionne | |
| 5.5 | Créer ticket → num_ticket auto | Ex : `AME-2026-0007` | |
| 5.6 | Assigner plusieurs techniciens | Tous visibles | |
| 5.7 | Modifier ticket | Champs mis à jour | |
| 5.8 | Changer statut (À étudier → En cours → Déployé) | Transitions fonctionnelles | |
| 5.9 | Supprimer ticket | Disparu de la liste | |
| 5.10 | Générer fiche HTML | Fichier créé dans `ameliorations/<num_ticket>/` (pas dans temp) | |
| 5.11 | Ouvrir fiche HTML → footer correct | "9 Rue d'Armorique", pas de 9bis, pas de Fax | |

---

## 6. App Pièces (EMS_Pieces.exe)

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 6.1 | Lancer EMS_Pieces.exe | Fenêtre s'ouvre | |
| 6.2 | Liste pièces (max 500 par défaut) | Colonnes : référence, libellé, marque, notes | |
| 6.3 | Recherche temps réel (ref + libellé + marque) | Filtre à la frappe | |
| 6.4 | Créer une pièce | Apparaît dans la liste | |
| 6.5 | Créer une pièce avec référence dupliquée | Erreur explicite, pas de crash | |
| 6.6 | Modifier une pièce | Champs mis à jour | |
| 6.7 | Supprimer une pièce | Disparue de la liste | |
| 6.8 | Import CSV/Excel | Doublons ignorés, compteur pièces importées affiché | |
| 6.9 | Import CSV avec colonnes non standard | Mapping auto-détecté ou erreur explicite | |

---

## 7. App BI (EMS_BI.exe)

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 7.1 | Lancer EMS_BI.exe | Fenêtre Tkinter + navigateur s'ouvrent | |
| 7.2 | Export DB déclenché au démarrage | `GET /admin/export-db` appelé, base encodée | |
| 7.3 | Dashboard BI chargé dans le navigateur | Tableaux et graphiques visibles | |
| 7.4 | Exécuter une requête SQL dans l'interface | Résultats affichés, pas d'erreur JS | |
| 7.5 | Serveur HTTP local sur port 17430 (ou configuré) | Pas de conflit de port | |

---

## 8. Launcher (EMS_Launcher.exe)

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 8.1 | Lancer EMS_Launcher.exe | Menu principal s'affiche | |
| 8.2 | Lancer EMS Bons depuis le launcher | App Bons s'ouvre dans un processus séparé | |
| 8.3 | Lancer EMS Parc depuis le launcher | App Parc s'ouvre | |
| 8.4 | Lancer EMS Pièces depuis le launcher | App Pièces s'ouvre | |
| 8.5 | Lancer EMS Garanties depuis le launcher | App Garanties s'ouvre | |
| 8.6 | Lancer EMS Amélioration depuis le launcher | App Amélioration s'ouvre | |
| 8.7 | Lancer EMS BI depuis le launcher | App BI s'ouvre + navigateur | |
| 8.8 | Fermer une app lancée → launcher toujours actif | Pas de crash du launcher | |

---

## 9. Tests d'intégration cross-app

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 9.1 | Créer un moteur dans Parc → visible dans combobox de Bons | Synchronisation via API | |
| 9.2 | Créer un client dans Parc → visible dans combobox de Bons | Idem | |
| 9.3 | Créer un technicien dans Parc → visible dans picker de Bons | Idem | |
| 9.4 | Créer un bon avec un moteur qui a une garantie → bannière garantie visible dans le bon | Données garantie affichées | |
| 9.5 | Modifier le statut d'un bon → dashboard reflète le changement après rafraîchissement | Compteurs mis à jour | |
| 9.6 | Ajouter une marque via ⚙ dans Parc → marque disponible dans combobox Moteur du bon | Cohérence base de données | |

---

## 10. Tests de déploiement .exe

| # | Scénario | Attendu | Résultat |
|---|---|---|---|
| 10.1 | Lancer depuis `EMS_Distribution/` (pas depuis le dossier source) | Toutes les apps fonctionnent | |
| 10.2 | Dossiers garanties générés dans `EMS_Distribution/garanties/` | Pas dans un dossier temp PyInstaller | |
| 10.3 | Dossiers améliorations générés dans `EMS_Distribution/ameliorations/` | Pas dans un dossier temp PyInstaller | |
| 10.4 | Bons générés dans le dossier configuré dans config.ini | Chemin correct | |
| 10.5 | config.ini lu depuis le dossier du .exe | Pas depuis le dossier source Python | |
| 10.6 | Lancer sur une machine sans Python installé | Fonctionne (tout bundlé) | |
| 10.7 | Lancer deux apps simultanément depuis le launcher | Pas de conflit de processus ou de base | |
| 10.8 | Vérifier absence du cache .pyc (`__pycache__`) dans EMS_Distribution | Dossier absent ou vide | |

---

## 11. Régressions à surveiller

| # | Comportement à ne pas avoir régressé | Résultat |
|---|---|---|
| 11.1 | Footer des bons : uniquement "9 Rue d'Armorique", Tel, site web | |
| 11.2 | Footer fiches garantie : identique (pas de 9bis, pas de Fax) | |
| 11.3 | Footer fiches amélioration : identique | |
| 11.4 | Signature emails : "9 Rue d'Armorique" uniquement | |
| 11.5 | Pas de boîte de dialogue Windows "aucun programme de messagerie" | |
| 11.6 | Explorer s'ouvre en fenêtre positionnée (pas plein écran) | |
| 11.7 | Champ Marque dans formulaire moteur (Parc) = SearchableCombobox avec liste DB | |
| 11.8 | Section "MARQUE MOTEUR" absente du formulaire bon d'intervention | |
| 11.9 | Marque auto-remplie dans le bon quand un moteur est sélectionné | |

---

*Dernière mise à jour : 2026-06-08*
