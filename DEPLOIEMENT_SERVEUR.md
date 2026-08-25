# Mode d'emploi — Déploiement et entretien du serveur EMS

> Guide pour **débutant** : ce document explique, étape par étape et sans
> présupposer de connaissances préalables, comment installer, mettre à jour
> et entretenir l'API EMS qui tourne sur la VM serveur `EMSVMA001`. Chaque
> terme technique est expliqué à sa première apparition (voir aussi le
> glossaire en section 1). Basé sur l'analyse des scripts réels du dépôt
> (`push_to_prod.ps1`, `publish_release.ps1`, `build.ps1`,
> `utils/install_service.py`) et de la configuration actuelle
> (`config.ini`, `ems_api/config.py`).

**IP du serveur : `192.168.1.10`** (confirmée — voir section 2).

---

## 0. Le principe en une phrase

Il y a **un seul ordinateur central** (la « VM serveur », nommée
`EMSVMA001`) qui fait tourner en permanence un programme (l'« API ») connecté
à **une seule base de données**. Tous les postes des employés (avec les
applications Bons, Parc, Garanties, etc.) se connectent à ce programme par le
réseau au lieu d'avoir chacun leur propre copie des données. Ce document
explique comment installer ce programme sur le serveur, comment le mettre à
jour quand le code change, et comment vérifier que tout va bien au quotidien.

```
POSTE DE DÉVELOPPEMENT                   VM SERVEUR "EMSVMA001"
────────────────────────────             ─────────────────────────
Dossier du projet "APP API"              Dossier partagé sur le réseau :
                                          \\EMSVMA001\EMS_install
  ems_api/          ─────copie─────►        = C:\EMS  (même dossier, vu
  shared/                                     depuis le serveur lui-même)
  ems_client/                                   ├─ ems_api\   (code + base de
  suivi_affaires.html                                          données ems.db)
                                                ├─ shared\
                                                ├─ ems_client\
                                                ├─ ems_api\static\   (fichiers
                                                │   .zip des mises à jour)
                                                ├─ ems_api\data\updates.json
                                                │   (fichier qui indique aux
                                                │    postes "voici la dernière
                                                │    version")
                                                └─ config.ini  (réglages propres
                                                    au serveur)

Sur le serveur, une "tâche planifiée" Windows nommée EMS_API lance en
permanence la commande :
  C:\EMS\.venv\Scripts\python.exe -m uvicorn ems_api.main:app --port 8765

Ce programme est alors joignable à cette adresse depuis n'importe quel poste
du réseau de l'entreprise :
  http://192.168.1.10:8765/health   → "est-ce que le serveur est vivant ?"
  http://192.168.1.10:8765/docs     → documentation interactive de l'API
  http://192.168.1.10:8765/static   → fichiers de mise à jour téléchargeables
```

---

## 1. Glossaire (à lire en premier en cas de débutant)

| Terme | Explication simple |
|---|---|
| **VM** | « Machine virtuelle » — un ordinateur simulé qui tourne à l'intérieur d'un vrai serveur physique. Se manipule exactement comme un PC Windows normal. |
| **API** | Le programme central qui répond aux demandes des applications (« donner la liste des clients », « enregistrer cette intervention », etc.). Ici, l'API s'appelle `ems_api` et tourne avec un outil nommé **uvicorn**. |
| **RDP** (Bureau à distance) | La méthode pour « prendre le contrôle » de l'écran du serveur depuis un autre poste, comme si l'on était assis devant. Windows fournit l'outil « Connexion Bureau à distance » (`mstsc`). |
| **Partage réseau** | Un dossier d'un ordinateur rendu visible et accessible depuis d'autres ordinateurs du réseau, via un chemin du type `\\NOM-MACHINE\NomDuPartage`. Ici : `\\EMSVMA001\EMS_install`. |
| **PowerShell** | La console de commandes utilisée sur Windows (icône bleue). Tous les scripts de ce projet (`.ps1`) s'exécutent dedans. |
| **Script** | Un fichier `.ps1` qui contient une suite de commandes automatisées, à lancer d'un coup au lieu de taper chaque commande une par une. |
| **venv** (environnement virtuel Python) | Une installation « isolée » de Python et de ses bibliothèques, propre à ce projet, pour ne pas mélanger avec d'autres logiciels Python du serveur. Se trouve dans `C:\EMS\.venv\`. |
| **Dépendances** (`requirements.txt`) | La liste des bibliothèques Python nécessaires au fonctionnement de l'API (ex. FastAPI, SQLAlchemy...). Elles doivent être installées dans le venv. |
| **Tâche planifiée** (Task Scheduler / `schtasks`) | Une fonctionnalité Windows qui lance automatiquement un programme selon des règles (ex. « au démarrage du PC », « tous les jours à telle heure »). Sert ici à démarrer l'API automatiquement et à la relancer après un déploiement. |
| **Service Windows / NSSM** | Une autre façon de faire tourner un programme en arrière-plan, plus robuste que la tâche planifiée (redémarrage auto en cas de crash, gestion propre des logs). `NSSM` est l'outil utilisé pour cette option. |
| **Port** | Un « numéro de porte » sur lequel un programme réseau écoute les demandes. L'API EMS utilise le port `8765`. |
| **`/health`** | Une adresse spéciale de l'API qui répond simplement « je suis vivant » — sert à vérifier rapidement que le serveur fonctionne. |
| **Base de données (`ems.db`)** | Le fichier unique qui contient toutes les données de l'entreprise (clients, moteurs, interventions...). C'est le fichier le plus important à ne jamais perdre. |
| **`robocopy`** | Un outil Windows en ligne de commande pour copier des dossiers entiers de façon fiable (utilisé par les scripts pour copier le code vers le serveur). |
| **PSRemoting** | Une fonctionnalité Windows qui permet d'envoyer des commandes à exécuter directement sur le serveur depuis un autre poste, sans avoir à ouvrir une session RDP. Pratique pour automatiser les redémarrages. |

---

## 2. Informations serveur (à connaître)

| Élément | Valeur |
|---|---|
| Nom de la machine | `EMSVMA001` |
| **Adresse IP du serveur** | **`192.168.1.10`** |
| Adresse de l'API | `http://192.168.1.10:8765` |
| Partage réseau (vu depuis un poste client) | `\\EMSVMA001\EMS_install` |
| Chemin local (vu depuis le serveur lui-même, en RDP) | `C:\EMS` — c'est **le même dossier** que le partage ci-dessus, juste vu « de l'intérieur » |
| Port de l'API | `8765` |
| Nom de la tâche planifiée | `EMS_API` |
| Emplacement du Python isolé (venv) | `C:\EMS\.venv\` |

---

## 3. Prérequis avant de commencer

- **Un compte avec accès au serveur** : identifiants pour se connecter en RDP
  sur `EMSVMA001`, et un compte réseau (souvent le même) disposant du droit
  d'écrire dans le partage `\\EMSVMA001\EMS_install`. En l'absence de ces
  accès, les demander à la personne qui gère l'infrastructure (IT) avant de
  poursuivre.
- **PowerShell** installé sur le poste de développement (déjà présent par
  défaut sur Windows — chercher « PowerShell » dans le menu Démarrer).
- **PSRemoting activé sur le serveur** (voir section 4.6) — permet aux
  scripts de redémarrer l'API automatiquement sans avoir à se connecter en
  RDP à chaque fois. Ce n'est pas obligatoire (les scripts savent s'en
  passer, avec des instructions manuelles à la place), mais c'est beaucoup
  plus confortable.
- **Le dossier des données métier accessible depuis le serveur** : les
  chemins réseau des affaires/interventions/garanties (`config.ini [files]`,
  ex. `Z:\AFFAIRES`) doivent être accessibles **depuis le serveur
  lui-même**, pas seulement depuis le poste de développement. Sinon, l'API
  ne pourra pas lire/écrire ces dossiers.

### Se connecter en RDP sur le serveur (première fois)

1. Appuyer sur la touche Windows, taper `Connexion Bureau à distance` et
   ouvrir l'application (ou taper `mstsc` dans Exécuter, touche
   Windows+R).
2. Dans le champ « Ordinateur », saisir `EMSVMA001` (ou l'IP
   `192.168.1.10`).
3. Cliquer sur « Connexion », puis saisir les identifiants fournis pour le
   serveur.
4. Un bureau Windows du serveur apparaît, utilisable comme n'importe quel
   PC. Tout ce qui est indiqué « en RDP » dans ce document se fait depuis cet
   écran.
5. Pour ouvrir PowerShell **en administrateur** dans cette session : clic
   droit sur le menu Démarrer → « Windows PowerShell (Admin) » ou « Terminal
   (Admin) ».

---

## 4. Installation initiale complète (à faire une seule fois)

⚠️ **Cette section ne concerne que le cas où le serveur n'existe pas encore,
ou a été perdu/réinstallé.** Si `C:\EMS` existe déjà sur le serveur et que
l'API tourne (vérifiable avec `http://192.168.1.10:8765/health`), **passer
directement à la section 5** — c'est le cas d'usage du quotidien.

### 4.1 Préparer le dossier et l'environnement Python (en RDP sur le serveur)

Se connecter en RDP sur `EMSVMA001` (voir section 3), ouvrir PowerShell en
administrateur, puis taper ces commandes une par une (Entrée après chacune) :

```powershell
mkdir C:\EMS
cd C:\EMS
python -m venv .venv
```

**Ce que fait chaque ligne :**
- `mkdir C:\EMS` : crée un dossier vide `C:\EMS` à la racine du disque.
- `cd C:\EMS` : place la console dans ce dossier (les commandes suivantes s'y
  exécuteront).
- `python -m venv .venv` : crée l'environnement Python isolé dans un
  sous-dossier `.venv`. Si Windows répond que `python` n'est pas reconnu,
  c'est que Python n'est pas installé sur le serveur — il faut d'abord
  l'installer depuis [python.org](https://www.python.org/downloads/windows/)
  (cocher « Add python.exe to PATH » pendant l'installation).

Puis mettre à jour l'outil d'installation de paquets Python :

```powershell
.venv\Scripts\pip.exe install --upgrade pip
```

### 4.2 Créer le partage réseau

Toujours en RDP sur le serveur, en PowerShell administrateur :

```powershell
New-SmbShare -Name "EMS_install" -Path "C:\EMS" -FullAccess "DOMAINE\Groupe-IT" -ChangeAccess "DOMAINE\Groupe-Dev"
```

Remplacer `DOMAINE\Groupe-IT` et `DOMAINE\Groupe-Dev` par les vrais noms de
groupes/comptes Active Directory utilisés dans l'entreprise (à demander à
l'IT si nécessaire). Cette commande rend le dossier `C:\EMS` visible sur le
réseau sous le nom `\\EMSVMA001\EMS_install`, avec des droits d'écriture
pour les comptes autorisés.

**Pour vérifier que l'opération a réussi**, depuis le poste de
développement (pas en RDP cette fois), ouvrir l'Explorateur de fichiers et
saisir dans la barre d'adresse : `\\EMSVMA001\EMS_install`. Le dossier
`C:\EMS` doit s'ouvrir.

### 4.3 Premier envoi du code vers le serveur

Retourner sur le **poste de développement** (le RDP n'est plus nécessaire
pour cette étape), ouvrir PowerShell, se placer dans le dossier du projet et
lancer :

```powershell
cd "C:\Users\Stagiaire.be\Desktop\APP API"
.\push_to_prod.ps1
```

Ce script est détaillé en section 5 — pour cette première exécution, il va
notamment **créer automatiquement** un fichier `config.ini` minimal sur le
serveur, puisqu'il n'en existe pas encore.

**Étape manuelle obligatoire ensuite** : se reconnecter en RDP sur le
serveur et ouvrir le fichier `C:\EMS\config.ini` avec le Bloc-notes pour
vérifier/corriger la ligne `data_dir` (section `[files]`) — elle doit
pointer vers le vrai chemin, **tel que vu depuis le serveur**, du dossier
`EMS_Distribution` (généralement quelque chose comme
`C:\APPLICATIONS METIER EMS\EMS_Distribution` ou un chemin réseau
`O:\...`). Le script affiche un message d'avertissement `[WARN]` à l'écran
pour le rappeler.

### 4.4 Installer les dépendances Python sur le serveur

Le script `push_to_prod.ps1` tente de le faire automatiquement (voir section
5), mais en cas d'échec, ou pour la toute première installation, l'opération
se fait manuellement en RDP sur le serveur :

```powershell
C:\EMS\.venv\Scripts\pip.exe install -r C:\EMS\requirements.txt
```

Cette commande lit le fichier `requirements.txt` et installe toutes les
bibliothèques Python nécessaires. L'opération peut prendre plusieurs minutes
la première fois. Quelques bibliothèques demandent une attention
particulière **côté serveur uniquement** :
- `weasyprint` : sert à générer les PDF. Sous Windows, elle a besoin de
  composants système supplémentaires (GTK/Pango) — si l'installation `pip`
  réussit mais que la génération de PDF échoue ensuite, consulter la doc
  d'installation Windows de WeasyPrint.
- `pywin32` : sert à envoyer des e-mails via Outlook. Nécessite qu'Outlook
  soit installé et configuré sur le serveur (ou sur le compte utilisé pour
  faire tourner l'API — voir section 4.5 sur le choix du compte).
- `openpyxl` : sert aux imports de fichiers Excel/CSV, rien de spécial à
  prévoir.

### 4.5 Créer la tâche planifiée qui démarre l'API automatiquement

**Pourquoi cette étape ?** Sans elle, l'API ne tourne que si quelqu'un l'a
lancée manuellement et laisse la fenêtre ouverte — ce qui s'arrête dès que
le serveur redémarre ou que la session RDP se ferme. La tâche planifiée
Windows résout ce problème : elle relance l'API automatiquement au démarrage
du serveur.

En RDP sur le serveur, PowerShell en administrateur :

```powershell
schtasks /create /tn "EMS_API" /tr "C:\EMS\.venv\Scripts\python.exe -m uvicorn ems_api.main:app --host 0.0.0.0 --port 8765" /sc onstart /ru SYSTEM /rl HIGHEST
```

**Explication de chaque option :**
- `/tn "EMS_API"` : nom donné à la tâche (« task name »). Doit rester
  exactement `EMS_API` car les scripts de déploiement s'y réfèrent par ce
  nom.
- `/tr "..."` : la commande exécutée (« task run ») — ici, lancer l'API
  Python sur le port 8765, accessible depuis tout le réseau (`0.0.0.0`).
- `/sc onstart` : la tâche se déclenche au démarrage de Windows (« schedule
  = on start »).
- `/ru SYSTEM` : la tâche tourne avec le compte système intégré, sans
  session utilisateur ouverte.
- `/rl HIGHEST` : exécution avec les droits les plus élevés disponibles.

⚠️ **Point d'attention (envoi d'e-mails)** : le compte `SYSTEM` n'a pas
toujours accès à Outlook (qui a besoin d'une session utilisateur normale
pour fonctionner). Si les e-mails envoyés par l'application (garanties,
devis...) ne partent pas, remplacer `/ru SYSTEM` par un compte de service
dédié avec une session Windows toujours ouverte sur le serveur :
```powershell
schtasks /create /tn "EMS_API" /tr "..." /sc onstart /ru "DOMAINE\svc-ems" /rp "mot-de-passe-du-compte" /rl HIGHEST
```

⚠️ **Point d'attention (dossier de travail)** : la commande doit s'exécuter
« depuis » le dossier `C:\EMS` pour que le programme retrouve ses fichiers
(`ems_api.main` est un import qui suppose qu'on est à la racine du projet).
Si après création de la tâche l'API ne démarre pas, remplacer la commande
`/tr` par le chemin d'un fichier `.bat` qui fait d'abord `cd /d C:\EMS`
avant de lancer uvicorn — s'inspirer de `ems_project/start_api.bat` comme
modèle, en l'adaptant (`host 0.0.0.0` au lieu de `127.0.0.1` pour un accès
réseau, et sans le `pause` final qui bloquerait une exécution automatique).

**Vérifier que la tâche existe bien :**
```powershell
schtasks /query /tn "EMS_API"
```

**Alternative plus robuste : NSSM (service Windows).** Pour un vrai service
Windows (redémarrage automatique en cas de plantage, gestion propre des
logs avec rotation), le dépôt fournit `utils/install_service.py` :
```powershell
cd C:\EMS
C:\EMS\.venv\Scripts\python.exe utils\install_service.py install
net start EMS_API
```
Ceci nécessite au préalable de télécharger `nssm.exe` depuis
[nssm.cc](https://nssm.cc/download) et de le placer dans
`C:\Windows\System32\`. **Attention** : dans le cas de cette option, les
scripts `push_to_prod.ps1` devront être adaptés, car ils redémarrent le
service avec `schtasks /run /tn "EMS_API"` (tâche planifiée), pas avec
`net start`/`nssm restart` (service). Sans adaptation, le redémarrage
automatique après un déploiement ne fonctionnera pas — le service devra
être relancé manuellement à chaque fois (`net stop EMS_API` puis
`net start EMS_API`).

### 4.6 Activer PSRemoting (recommandé, pour automatiser les redémarrages)

Toujours en RDP sur le serveur, PowerShell en administrateur, une seule
fois :

```powershell
Enable-PSRemoting -Force
```

Ceci permet à `push_to_prod.ps1`, lancé depuis le poste de développement,
d'envoyer directement des commandes au serveur (redémarrer l'API, installer
des dépendances) sans nécessiter de reconnexion en RDP à chaque déploiement.
Si cette commande échoue avec un message évoquant un réseau « public »,
c'est que le profil réseau du serveur est mal configuré — contacter l'IT
(généralement ça se résout en passant le profil réseau en « privé » ou
« domaine »).

### 4.7 Démarrer l'API pour la première fois et vérifier

Lancer la tâche planifiée manuellement (en RDP, PowerShell) :

```powershell
schtasks /run /tn "EMS_API"
```

Attendre une dizaine de secondes, puis vérifier que l'API répond. Cette
vérification peut se faire **depuis n'importe quel PC du réseau** (pas
besoin d'être en RDP), simplement en ouvrant un navigateur internet et en
allant à l'adresse :

```
http://192.168.1.10:8765/health
```

Un petit texte `{"status":"ok"}` doit apparaître. Si c'est le cas, l'API
tourne. Vérifier aussi `http://192.168.1.10:8765/docs` : une page
« Swagger UI » listant toutes les fonctionnalités de l'API doit s'afficher —
c'est la documentation interactive, utile pour tester des requêtes à la
main plus tard.

En l'absence de réponse, se reporter directement à la section 8
(Dépannage).

---

## 5. Déploiement courant — mettre à jour le code de l'API

**C'est l'opération la plus fréquente** : à chaque fois que du code a changé
dans `ems_api/`, `shared/`, `ems_client/` ou `suivi_affaires.html`, il faut
l'envoyer sur le serveur pour que les utilisateurs profitent des
changements.

### 5.1 Lancer le déploiement

Sur le **poste de développement** (pas besoin de RDP), ouvrir PowerShell :

```powershell
cd "C:\Users\Stagiaire.be\Desktop\APP API"
.\push_to_prod.ps1
```

Le script affiche sa progression à l'écran avec des sections en cyan
(`===== ... =====`), des lignes vertes `[OK]` quand tout va bien, jaunes
`[WARN]` pour des avertissements sans gravité, et rouges `[ERREUR]` en cas
d'arrêt nécessitant une correction. **Il est important de lire les messages
au fur et à mesure** — le script explique lui-même ce qu'il fait.

### 5.2 Ce que le script fait, étape par étape (pour comprendre ce qui se passe)

1. **Vérifications de départ.** Le script vérifie que l'exécution se fait
   bien dans le bon dossier, que le partage réseau du serveur est
   accessible, et regarde si l'API répondait déjà avant le déploiement (pour
   pouvoir comparer après).
2. **Sauvegarde automatique de la base de données.** Avant de toucher à quoi
   que ce soit, le script copie la base actuelle (`ems.db`) sous un nouveau
   nom horodaté, du type `ems.db.backup_20260824_143000`. **C'est le filet
   de sécurité** : si le déploiement se passe mal, il reste possible de
   revenir à cette version (voir section 5.4, « Annuler un déploiement
   raté »).
3. **Copie du nouveau code.** Le script copie les dossiers `ems_api/`,
   `shared/`, `ems_client/`, ainsi que `suivi_affaires.html` et
   `convertisseurpdf.py`, depuis le poste de développement vers le serveur.
   Il utilise un outil nommé `robocopy` qui **ne touche jamais** aux
   fichiers suivants, même s'ils existent des deux côtés : la base de
   données (`*.db` et ses fichiers annexes `-shm`/`-wal`/`-journal`) et les
   fichiers de logs (`*.log`). **Les données ne risquent donc rien pendant
   cette étape.**
4. **Fichier `updates.json`.** C'est le fichier qui indique aux applications
   des utilisateurs quelle est la dernière version disponible. Il n'est
   copié que s'il n'existe pas encore côté serveur — une fois en place, il
   n'est plus jamais écrasé par ce script (c'est un autre script,
   `publish_release.ps1`, qui s'en charge — voir section 6).
5. **Mise à jour des dépendances Python.** Le script tente de se connecter
   au serveur (via PSRemoting, section 4.6) pour relancer automatiquement
   `pip install -r requirements.txt`, au cas où le code envoyé aurait besoin
   d'une nouvelle bibliothèque. Si PSRemoting n'est pas activé, le script
   fournit la commande à exécuter manuellement en RDP.
6. **Redémarrage du programme.** Le script arrête tous les processus Python
   en cours sur le serveur, supprime les dossiers de cache (`__pycache__`,
   pour garantir l'utilisation du nouveau code et non d'une ancienne version
   mise en cache), puis relance la tâche planifiée `EMS_API`. Là encore, si
   PSRemoting n'est pas disponible, le script affiche les 3 commandes à
   exécuter manuellement en RDP, et **attend une validation par Entrée** une
   fois l'opération faite avant de continuer.
7. **Vérification finale.** Le script attend quelques secondes que le
   serveur redémarre, puis interroge `/health` jusqu'à 6 fois (toutes les
   3 secondes) pour confirmer que tout est reparti correctement. Il teste
   même un endpoint métier concret (génération d'un document
   d'intervention) pour s'assurer que ce n'est pas juste « le serveur
   répond » mais « le serveur fonctionne vraiment ».
8. **Résumé final.** À la fin, le script affiche le nom exact du fichier de
   sauvegarde créé à l'étape 2, avec la commande prête à copier-coller en
   cas de retour en arrière nécessaire.

### 5.3 Si PSRemoting n'est pas disponible (redémarrage manuel)

Le script l'indique clairement en jaune. Dans ce cas, se connecter en RDP
sur `EMSVMA001`, ouvrir PowerShell en administrateur, et taper :

```powershell
Get-Process python | Stop-Process -Force
Get-ChildItem -Path C:\EMS -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
schtasks /run /tn "EMS_API"
```

**Explication :**
- La 1ère ligne arrête tous les programmes Python en cours (dont l'ancienne
  version de l'API).
- La 2ème ligne supprime les fichiers de cache Python pour forcer
  l'utilisation du nouveau code.
- La 3ème ligne relance la tâche planifiée, qui redémarre l'API.

Revenir ensuite sur le poste de développement dans PowerShell (où le script
`push_to_prod.ps1` attend) et appuyer sur Entrée pour qu'il continue et
vérifie que tout va bien.

### 5.4 Annuler un déploiement raté (rollback)

Si après un déploiement l'API ne fonctionne plus correctement, deux niveaux
de rollback sont possibles :

**Revenir en arrière sur la base de données** (en cas de problème touchant
les données, ce qui reste rare car le code ne touche jamais la DB en dehors
des migrations automatiques au démarrage) :
```powershell
Copy-Item "\\EMSVMA001\EMS_install\ems_api\data\ems.db.backup_20260824_143000" "\\EMSVMA001\EMS_install\ems_api\data\ems.db" -Force
```
(remplacer le nom du fichier par celui affiché par le script à la fin).
Puis relancer le service (section 5.3, dernière ligne).

**Revenir en arrière sur le code** : il n'existe pas de bouton automatique
pour cela. Il faut, sur le poste de développement, revenir à une version
antérieure du code avec Git (`git log` pour trouver le bon commit,
`git checkout <commit>` ou équivalent — demander de l'aide en cas de
difficulté avec Git), puis relancer `push_to_prod.ps1` pour renvoyer cette
ancienne version sur le serveur.

---

## 6. Publier une nouvelle version des applications (fichiers .exe)

Cette section concerne les **programmes installés sur les postes des
utilisateurs** (Bons, Parc, Garanties, Affaire, BI, Pièces...) — c'est
différent de l'API du serveur (section 5). C'est ce qui permet aux employés
de recevoir une nouvelle version de leur logiciel, avec le badge de mise à
jour dans le launcher.

### 6.1 Étape 1 — Compiler les applications

Sur le poste de développement :
```powershell
.\build.ps1
```
Ce script demande d'abord s'il faut changer le numéro de version (saisir la
nouvelle version au format `X.Y.Z`, ex. `1.10.0`, ou appuyer simplement sur
Entrée pour garder la version actuelle), puis des notes de version
(facultatif). Il compile ensuite chaque application (Bons, Parc,
Garanties...) en un fichier `.exe`, un processus qui **peut prendre
plusieurs minutes**. À la fin, un fichier `.zip` est créé dans le dossier
`releases\`.

### 6.2 Étape 2 — Publier sur le serveur

```powershell
.\publish_release.ps1
```
Ce script trouve automatiquement le `.zip` le plus récent créé par
`build.ps1`, demande des notes de version (optionnel), puis :
1. copie le `.zip` dans `\\EMSVMA001\EMS_install\ems_api\static\` (c'est
   ce dossier que l'API sert aux utilisateurs via l'adresse `/static`) ;
2. supprime les anciens `.zip` pour ne pas remplir le disque du serveur ;
3. met à jour le fichier `updates.json`, qui indique aux applications des
   utilisateurs qu'une nouvelle version est disponible ;
4. vérifie, en interrogeant `http://192.168.1.10:8765/updates/latest`, que
   le serveur annonce bien la nouvelle version.

**Résultat** : au prochain démarrage de leur launcher, les utilisateurs
verront un badge de mise à jour et pourront installer la nouvelle version.
Aucune autre action n'est nécessaire.

---

## 7. Entretien courant / maintenance

### 7.1 Les sauvegardes de la base de données

Il existe **deux mécanismes de sauvegarde automatique**, en plus de celui,
ponctuel, du script de déploiement :

- **Sauvegarde quotidienne automatique** : dès que l'API démarre, elle lance
  en arrière-plan une tâche qui sauvegarde `ems.db` **tous les jours à 2h00
  du matin**, dans le dossier `C:\EMS\ems_api\data\backups\`, avec un nom du
  type `ems_2026-08-24_0200.db`. Les sauvegardes de plus de **30 jours sont
  automatiquement supprimées** pour ne pas remplir le disque.
- **Sauvegarde avant chaque déploiement** : `push_to_prod.ps1` en crée une
  supplémentaire, nommée `ems.db.backup_<date>_<heure>`, juste avant de
  copier le nouveau code (section 5.2, étape 2).

**Sauvegarde manuelle** (pour en produire une à la demande, par exemple
avant une manipulation risquée) — en RDP sur le serveur :
```powershell
cd C:\EMS
.venv\Scripts\python.exe -m ems_api.backup
```

⚠️ **Point important à comprendre** : toutes ces sauvegardes restent
**sur le même disque dur** que la base de données originale
(`C:\EMS\ems_api\data\`). Ce n'est **pas** une vraie protection contre une
panne matérielle, un vol, ou un incendie du serveur — en cas de mort du
disque du serveur, les sauvegardes disparaissent avec lui. Pour une vraie
sécurité, il faudrait en plus copier régulièrement ces sauvegardes vers un
autre emplacement physique (un NAS, un service cloud, ou un système de
snapshot de la VM géré par l'IT). En l'absence d'un tel dispositif, c'est le
point le plus important à faire mettre en place par la personne qui gère
l'infrastructure.

### 7.2 Consulter les logs (pour comprendre ce qui s'est passé)

Les « logs » sont les fichiers texte où le programme note ce qu'il fait et
les erreurs rencontrées — c'est le premier endroit à consulter en cas de
problème.

- Si l'API tourne via la **tâche planifiée** telle que créée en section 4.5
  (sans redirection), **il n'y a pas de fichier de log** par défaut — la
  sortie du programme n'est nulle part, ce qui complique le diagnostic. Pour
  y remédier, la tâche peut être configurée pour lancer un fichier `.bat`
  qui redirige la sortie :
  ```bat
  C:\EMS\.venv\Scripts\python.exe -m uvicorn ems_api.main:app --host 0.0.0.0 --port 8765 >> C:\EMS\logs\api.log 2>&1
  ```
  (créer d'abord le dossier `C:\EMS\logs`, puis remplacer le contenu de
  `/tr` de la tâche planifiée par le chemin de ce `.bat`).
- Si l'API tourne via **NSSM** (section 4.5, alternative), les logs sont déjà
  automatiquement écrits dans `C:\EMS\logs\api.log` (sortie normale) et
  `api-err.log` (erreurs), avec rotation automatique quand le fichier
  dépasse 10 Mo (pour ne jamais remplir le disque).
- Les logs applicatifs internes à Python (niveau de détail, format) sont
  configurés dans `ems_api/_logging.py`.

### 7.3 Nettoyage du disque du serveur

À vérifier périodiquement (en RDP, dans l'Explorateur de fichiers sur
`C:\EMS\`) :

| Dossier | Ce qu'il faut vérifier |
|---|---|
| `ems_api\data\backups\` | Doit se nettoyer tout seul (rétention 30 jours) — un dossier anormalement volumineux indiquerait que le nettoyage automatique ne tourne pas (il ne se relance qu'au redémarrage de l'API) |
| `ems_api\static\` | Ne devrait contenir qu'un seul `.zip` à la fois (les anciens sont supprimés par `publish_release.ps1`) — un déploiement interrompu peut laisser des fichiers orphelins |
| `logs\` (si NSSM utilisé) | Rotation automatique à 10 Mo, mais surveiller l'espace disque global si beaucoup de redémarrages ont eu lieu |
| `__pycache__` un peu partout | Nettoyé automatiquement à chaque `push_to_prod.ps1`, impact disque négligeable normalement |

### 7.4 Vérifier que le serveur est en bonne santé

Le moyen le plus simple, depuis n'importe quel PC connecté au réseau de
l'entreprise, un navigateur suffit :
```
http://192.168.1.10:8765/health
```
Doit afficher `{"status":"ok"}`. Pour une vérification en ligne de commande
PowerShell :
```powershell
Invoke-WebRequest http://192.168.1.10:8765/health
```

Pour vérifier que la tâche planifiée est bien active (en RDP sur le
serveur) :
```powershell
schtasks /query /tn "EMS_API" /v /fo LIST
```
La ligne `Statut de la tâche` doit indiquer que la tâche tourne (« En cours
d'exécution ») ou s'est terminée normalement selon le mode configuré.

Il n'existe actuellement **aucune alerte automatique** en cas de panne (mail,
Teams...) — la seule façon de détecter une panne du service est une
vérification manuelle ou un signalement par un utilisateur. En cas de pannes
fréquentes, une surveillance automatique périodique de `/health` serait
utile à mettre en place, ce qui n'est pas encore fait.

### 7.5 Mettre à jour les dépendances Python manuellement

En cas d'ajout d'une bibliothèque à `requirements.txt` en dehors d'un
déploiement complet, ou si l'installation automatique a échoué pendant un
`push_to_prod.ps1` :
```powershell
C:\EMS\.venv\Scripts\pip.exe install -r C:\EMS\requirements.txt
```
Puis redémarrer le service (section 5.3).

---

## 8. Dépannage — problèmes courants et solutions

| Symptôme | Cause probable | Solution |
|---|---|---|
| `push_to_prod.ps1` s'arrête à « Partage serveur inaccessible » | Le partage `EMS_install` est injoignable : serveur éteint, panne réseau, ou droits d'accès insuffisants | Vérifier l'ouverture de `\\EMSVMA001\EMS_install` dans l'Explorateur de fichiers. En cas d'échec, tester `ping EMSVMA001` en PowerShell pour voir si le serveur répond au réseau |
| `http://192.168.1.10:8765/health` ne répond pas après un déploiement | Le programme a planté au démarrage (erreur dans le code, dépendance manquante) | Se connecter en RDP, ouvrir PowerShell, et lancer la commande manuellement pour voir le message d'erreur en clair : `C:\EMS\.venv\Scripts\python.exe -m uvicorn ems_api.main:app --port 8765` |
| La copie du code (`robocopy`) semble bloquée très longtemps | Un fichier de la base de données est verrouillé par un autre programme (rare, car les fichiers `.db` sont exclus de la copie) | Vérifier qu'aucun autre logiciel (antivirus, explorateur de fichiers ouvert sur le dossier) ne bloque l'accès au dossier `ems_api\` sur le serveur |
| Les commandes automatiques via PSRemoting échouent systématiquement | `Enable-PSRemoting` n'a pas été activé sur le serveur, ou le pare-feu bloque la connexion | Relancer `Enable-PSRemoting -Force` en RDP sur le serveur (section 4.6). En cas de persistance, contacter l'IT pour vérifier les règles de pare-feu (le service concerné s'appelle WinRM) |
| Les e-mails ne partent pas depuis le serveur | La bibliothèque `pywin32` a besoin qu'Outlook tourne dans une vraie session utilisateur — cela ne fonctionne pas toujours avec le compte `SYSTEM` d'une tâche planifiée | Faire tourner la tâche planifiée avec un compte de service dédié disposant d'une session Windows toujours ouverte (section 4.5), avec Outlook configuré sur ce compte |
| La génération de PDF échoue | La bibliothèque `weasyprint` a besoin de composants système Windows (GTK/Pango) qui ne s'installent pas juste avec `pip install` | Suivre la documentation officielle d'installation Windows de WeasyPrint pour installer le runtime GTK3 manquant |
| Les utilisateurs ne voient pas la nouvelle version après `publish_release.ps1` | Le service n'a pas redémarré, ou cache côté client/navigateur | Le script `publish_release.ps1` vérifie déjà automatiquement `/updates/latest` à la fin — en cas de `[WARN]` signalant une version différente, redémarrer le service manuellement (section 5.3) |
| Incertitude sur le fonctionnement du serveur | — | Ouvrir simplement un navigateur sur `http://192.168.1.10:8765/health` depuis n'importe quel PC du réseau. L'absence de réponse après un certain temps de chargement indique que le serveur ne répond pas (voir la ligne ci-dessus) |

**Réflexe général en cas de blocage** : se reconnecter en RDP sur le
serveur, ouvrir PowerShell en administrateur, et lancer la commande de l'API
**manuellement** (sans passer par la tâche planifiée), pour voir directement
dans la console le message d'erreur exact :
```powershell
cd C:\EMS
.venv\Scripts\python.exe -m uvicorn ems_api.main:app --host 0.0.0.0 --port 8765
```
Le message affiché (généralement en rouge) indique précisément où se situe
le blocage (import Python manquant, port déjà utilisé, fichier
introuvable...). Fermer cette fenêtre (Ctrl+C) une fois le diagnostic fait,
puis relancer proprement via la tâche planifiée
(`schtasks /run /tn "EMS_API"`).

---

## 9. Sécurité (optionnelle, actuellement désactivée)

Par défaut, **l'API n'a aucune authentification** : n'importe quel appareil
sur le réseau de l'entreprise peut lire/modifier les données. C'est un choix
volontaire pour rester simple sur un réseau interne de confiance, mais il
est possible d'ajouter une protection minimale par mot de passe partagé
(« clé d'API ») :

En RDP sur le serveur, PowerShell en administrateur, pour définir la clé de
façon permanente :
```powershell
[Environment]::SetEnvironmentVariable("EMS_API_KEY", "cle-secrete-tres-longue-a-inventer", "Machine")
```
Puis **redémarrer le service** (section 5.3) pour que le changement soit pris
en compte. Une fois activée, chaque application cliente doit être configurée
avec la **même** clé (variable d'environnement `EMS_API_KEY` sur chaque
poste utilisateur), sinon elle ne pourra plus se connecter à l'API — à
prévoir avant d'activer cette option en production, pour ne pas bloquer tout
le monde d'un coup.

Il existe aussi une restriction d'accès optionnelle par dossier
(« COMMERCIAL » de chaque affaire) basée sur les groupes Windows/Active
Directory, à configurer via `commercial_group` dans `config.ini [files]` —
laissé vide par défaut, donc inactif.

---

## 10. Aide-mémoire — les commandes à retenir

**Déployer une mise à jour du code de l'API (le plus fréquent) :**
```powershell
cd "C:\Users\Stagiaire.be\Desktop\APP API"
.\push_to_prod.ps1
```

**Publier une nouvelle version des applications utilisateurs (.exe) :**
```powershell
.\build.ps1
.\publish_release.ps1
```

**Vérifier que le serveur va bien (depuis n'importe quel PC, navigateur) :**
```
http://192.168.1.10:8765/health
```

**Annuler (rollback) la base de données après un déploiement raté :**
```powershell
Copy-Item "\\EMSVMA001\EMS_install\ems_api\data\ems.db.backup_<date_heure>" "\\EMSVMA001\EMS_install\ems_api\data\ems.db" -Force
```

**Redémarrer le service manuellement (en RDP sur EMSVMA001) :**
```powershell
Get-Process python | Stop-Process -Force
Get-ChildItem -Path C:\EMS -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
schtasks /run /tn "EMS_API"
```

**Faire une sauvegarde manuelle de la base de données (en RDP) :**
```powershell
C:\EMS\.venv\Scripts\python.exe -m ems_api.backup
```

**Voir le détail de l'erreur si l'API refuse de démarrer (en RDP) :**
```powershell
cd C:\EMS
.venv\Scripts\python.exe -m uvicorn ems_api.main:app --host 0.0.0.0 --port 8765
```

---

## 11. Points d'amélioration identifiés (non corrigés, à traiter au besoin)

Ces points ont été repérés en analysant le fonctionnement actuel — ce sont
des pistes d'amélioration, pas des blocages :

1. **Pas de sauvegarde hors-site** de la base de données (section 7.1) : en
   cas de panne matérielle du serveur, toutes les sauvegardes seraient
   perdues avec les données originales.
2. **Pas de logs persistants** avec la configuration par défaut de la tâche
   planifiée (section 7.2) : diagnostic difficile pour un problème passé
   sans avoir été observé au moment où il s'est produit.
3. **La création de la tâche planifiée `EMS_API` n'est pas automatisée** :
   en cas de reconstruction complète du serveur, la commande manuelle de la
   section 4.5 doit être refaite — un script dédié (`setup_server.ps1`)
   fiabiliserait une réinstallation complète.
4. **Aucune alerte automatique** en cas de panne du service (section 7.4) —
   la détection dépend actuellement d'une vérification manuelle ou d'un
   signalement utilisateur.
