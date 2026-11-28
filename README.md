# Cap90

Cap90 aide les étudiants qui arrivent dans la Métropole Européenne de Lille pendant leurs 90 premiers jours.
L'utilisateur répond à 5 questions et obtient un rétroplanning daté de ses démarches administratives.
Un coffre-fort de justificatifs et un espace de dons entre habitants arriveront ensuite.

Projet de Cloud Computing, JUNIA ISEN. L'application tourne dans un conteneur Docker sur une VM Azure,
derrière un Load Balancer. Elle utilise Azure Table Storage et Azure Blob Storage via une Managed Identity.

L'infrastructure (Terraform, VM, Load Balancer, stockage, Key Vault) et le contrat d'interface entre l'application
et l'infrastructure sont dans le dépôt
[PROJET_Cloud_Computing_Group17_Infrastructure](https://github.com/FOGUERAYAN/PROJET_Cloud_Computing_Group17_Infrastructure).

## Fonctionnalités

- Mise en page sur 1200 px : bandeau bleu nuit en tête de chaque page, puis deux colonnes sur ordinateur
  (contenu et colonne latérale avec la progression, la prochaine étape, l'agenda et les liens utiles du thème).
- Accueil : bandeau "Bienvenue à Lille", 8 tuiles d'accès, prochaine étape et agenda de la semaine.
- Mon profil (pastille avec les initiales, onglet Profil sur mobile) : modification des 5 réponses avec
  recalcul du planning après confirmation (les étapes faites sont gardées), badges, accès au coffre-fort,
  suppression de toutes les données après confirmation.
- Liens officiels : bouton "Site officiel" sur chaque démarche, lieu et aide, et `app/data/liens_utiles.json`
  (chaque adresse a été testée avant d'être ajoutée). Étiquettes de thème cliquables vers `/liens-utiles?theme=...`.

- Accueil avec un bouton "Créer mon profil".
- Profil en 5 questions (statut, ville, date d'arrivée, langue maternelle, centres d'intérêt), sans mot de passe.
  L'identifiant utilisateur est gardé dans la session Flask.
- Planning : anneau de progression, "Ta prochaine étape" mise en avant, étapes groupées selon la date du jour
  (En retard, Cette semaine, Ce mois-ci, Plus tard, Déjà faites) dans des blocs repliables,
  pièces à préparer à cocher (champ `pieces_pretes`), badges, et message de confirmation de 4 secondes
  après "C'est fait" (animation CSS qui respecte `prefers-reduced-motion`).
- Planning : bloc "Où aller" (adresse et métro) quand la démarche est liée à un lieu (`lieu_id`).
- Lille : lieux utiles, se loger (sites recommandés et fiche anti-arnaques), découvrir Lille
  (filtres à voir, manger pas cher, sortir, et page de détail).
- `/medias/<nom>` : photos lues dans le conteneur Blob privé `medias-lille`, avec un cache HTTP d'un jour.
  Sans photo, un bloc de couleur avec l'icône de la catégorie s'affiche.
- Solidarité : agenda "Cette semaine à Lille" (aide alimentaire, épiceries solidaires, bénévolat),
  sept colonnes sur ordinateur et liste par jour sur mobile, avec le jour courant mis en avant.
  Section "Devenir bénévole" vers JeVeuxAider.gouv.fr. Les dons entre habitants arriveront ensuite.
- Travailler : saisie des heures par mois et jauge des 964 heures autorisées aux étudiants étrangers.
  La période d'un an commence à la date de validation du visa (date où l'étape est cochée dans le planning)
  et recommence à chaque anniversaire. Les heures étant saisies par mois, une période compte les 12 mois
  à partir du mois de validation. Couleur primaire sous 80 %, alerte de 80 à 100 %, retard au-delà.
- Coffre-fort : page d'attente.
- `/health` : renvoie `{"status": "ok"}` sans accéder au stockage (sonde du Load Balancer).

Les délais du catalogue (`app/data/demarches.json`) sont indicatifs et marqués `"a_verifier": true`.
Ils doivent être vérifiés sur service-public.fr.
De même, les lieux (`app/data/lieux.json`) et l'entraide (`app/data/entraide.json`) sont marqués `"a_verifier": true` : les champs dont on n'est pas sûr
(adresse, métro, prix, jour, horaires) sont laissés vides et doivent être complétés.

## Arborescence

```
app/
  __init__.py        create_app()
  config.py          lecture des variables d'environnement
  routes/            accueil, profil, planning, lille, medias, travail, coffre, solidarite, health
  services/
    planning.py      calcul du rétroplanning (fonctions pures)
    lieux.py         chargement, validation et filtres des lieux
    entraide.py      chargement, validation et agenda de l'entraide
    travail.py       période annuelle, total des heures et seuils de la jauge (fonctions pures)
    storage.py       interface de stockage, implémentations Azure (Tables et Blob) et mémoire
  data/              démarches, lieux, entraide et liens utiles
  templates/         pages Jinja
  static/css/        theme.css (palette) et app.css (mise en page)
medias/              photos à envoyer dans le conteneur Blob
scripts/             charger_medias.py, telecharger_photos.py
function/            Azure Function des tâches nocturnes (purge des annonces, rappels) : voir function/README.md
tests/               tests pytest, avec le stockage en mémoire
```

## Lancer en local avec Docker Compose

Prérequis : Docker Desktop ou Rancher Desktop démarré.

1. Créer le fichier `.env` à partir de l'exemple :

   ```
   cp .env.example .env
   ```

2. Générer une clé de session et la coller dans `SECRET_KEY` du fichier `.env` :

   ```
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Lancer l'application et Azurite :

   ```
   docker compose up --build
   ```

4. Ouvrir http://localhost:8000.

Si le port 8000 est déjà utilisé sur la machine, changer `APP_PORT` dans `.env` (par exemple 8080).

Azurite écoute sur les ports 10000 (Blob) et 10002 (Table). Les tables `profils`, `etapes` et `annonces`
sont créées au démarrage de l'application. Les données sont conservées dans le volume `azurite-data`
(`docker compose down -v` pour tout effacer).

La connexion locale utilise uniquement `UseDevelopmentStorage=true`. Comme cette chaîne vise `127.0.0.1`,
le conteneur de l'application partage le réseau du conteneur Azurite (`network_mode: service:azurite`).

## Ajouter une photo

1. Déposer le fichier dans `medias/` (jpg, jpeg, png ou webp, nom sans accent ni espace, par exemple `grand-place.jpg`).
2. Dans `app/data/lieux.json`, remplir `photo` avec le nom du fichier et `credit_photo` avec l'auteur et la licence.
   L'application refuse de démarrer si une photo n'a pas de crédit.
3. Avec docker compose lancé, envoyer les photos dans Azurite depuis l'environnement virtuel :

   ```
   python scripts/charger_medias.py
   ```

   Puis relancer l'application (`docker compose up --build -d`) pour qu'elle relise `lieux.json`.

Le conteneur `medias-lille` est privé : les images passent toujours par la route `/medias/<nom>`.

## Profil : langues et communes

La langue maternelle (code ISO 639-1, liste dans `app/data/langues.json`) et la commune de la métropole
(liste dans `app/data/communes.json`, Lille par défaut) se choisissent dans des listes, vérifiées côté serveur.
"Autre langue" affiche un champ "Précise ta langue" en CSS (`:has()`), sans JavaScript.

Les profils créés avant ce changement se migrent avec :

```
python scripts/migrer_profils.py --dry-run
python scripts/migrer_profils.py
```

## Polices et icônes

Tabler Icons 3.19.0 (licence MIT), Inter et Poppins (licence SIL OFL 1.1) sont hébergées dans
`app/static/vendor/` avec leurs licences. L'application ne charge aucune ressource depuis un domaine extérieur,
ce que vérifie un test.

## Récupérer des photos libres (Wikimedia Commons)

`scripts/telecharger_photos.py` cherche une photo pour chaque lieu sans photo (sauf les sites de logement),
garde la première image en paysage sous licence CC0, domaine public, CC BY ou CC BY-SA, la télécharge
dans `medias/<id>.jpg` et remplit `photo` et `credit_photo` dans `lieux.json`.

1. Renseigner `PHOTOS_CONTACT` dans `.env` (contact de l'équipe, envoyé dans le User-Agent demandé par Wikimedia).
2. Vérifier les choix sans rien télécharger :

   ```
   python scripts/telecharger_photos.py --dry-run
   ```

3. Lancer le téléchargement (option `--lieux id1,id2` pour ne traiter que certains lieux), relire les crédits,
   puis envoyer les photos avec `python scripts/charger_medias.py`.
   Ce script convertit d'abord les JPG et PNG en WebP (1200 px au plus, environ 150 Ko, Pillow),
   met à jour les noms et les dimensions dans `lieux.json` et `modules.json`, et affiche le poids
   avant et après conversion.

Options utiles :

- `--requete "texte"` : recherche personnalisée, pour un seul lieu (`--lieux id`) ou pour un bandeau.
- `--bandeau decouvrir` : photo de bandeau d'un module, enregistrée dans `app/data/modules.json`
  (champ `photo_bandeau`), fichier `medias/bandeau-<module>.jpg`.
- `--propositions 3` : en `--dry-run`, affiche plusieurs images possibles ; `--choix 2` télécharge la deuxième.

```
python scripts/telecharger_photos.py --dry-run --propositions 3 --lieux citadelle --requete "Citadelle de Lille Porte Royale"
python scripts/telecharger_photos.py --lieux citadelle --requete "Citadelle de Lille Porte Royale" --choix 2
```

## Organismes et associations : pas de logo

Les logos officiels sont des marques protégées et pourraient laisser croire à un partenariat.
Les organismes, les sites de logement et les associations sont représentés par une pastille de monogramme
(champ `sigle`, 2 à 5 caractères, dans `lieux.json`, `entraide.json` et `liens_utiles.json`).
Couleur : primaire pour les démarches, alerte pour l'entraide, bleu nuit pour le logement.
Cap90 est un projet étudiant indépendant, sans lien avec les organismes cités.

## Coffre-fort

Chaque utilisateur dépose ses justificatifs (PDF, JPG ou PNG, 10 Mo au maximum) dans le conteneur Blob privé
`coffre`, sous son propre préfixe : `<id utilisateur>/<identifiant aléatoire>`. Le nom d'origine est gardé dans
les métadonnées du blob et rendu au téléchargement (en-tête `Content-Disposition`).

- L'extension et la signature réelle du fichier sont vérifiées (un programme renommé en `.pdf` est refusé).
- Liste, téléchargement et suppression passent toujours par l'application, qui ne lit que le préfixe
  de l'utilisateur connecté. Le conteneur n'est jamais exposé directement.
- "Supprimer mes données" (Mon profil) efface aussi tous les fichiers du coffre.
- Pour la démonstration, n'utiliser que de faux documents.

### Lien de partage de 24 h

Le mode est choisi automatiquement selon la connexion au stockage :

| Environnement | Lien | Fonctionnement |
| --- | --- | --- |
| Azure (`STORAGE_MODE=azure`) | User Delegation SAS | L'application obtient une clé de délégation avec `get_user_delegation_key` grâce à la Managed Identity (`DefaultAzureCredential`), puis signe une SAS en lecture seule, HTTPS uniquement, pour un seul blob, qui expire au bout de 24 h. Aucune clé de compte n'est utilisée. |
| Azurite ou mémoire | Lien interne signé | Azurite ne gère pas la délégation Microsoft Entra ID. L'application crée un jeton signé avec `itsdangerous` et `SECRET_KEY`, valable 24 h, servi par `/partage/<jeton>` en lecture seule. |

Supprimer le fichier rend le lien inutilisable avant la fin des 24 h.

### Droits à donner sur Azure (RBAC)

Rôles à attribuer à la Managed Identity de la VM, au niveau du compte de stockage.
Aucune clé de compte n'est utilisée : sans ces trois rôles, l'application ne peut pas fonctionner sur Azure.

| Rôle | Utilité dans Cap90 |
| --- | --- |
| Storage Blob Data Contributor | Lire, écrire et supprimer les blobs : conteneur `medias-lille` (photos) et conteneur `coffre` (justificatifs). |
| Storage Blob Delegator | Obtenir la clé de délégation (`get_user_delegation_key`) pour signer les liens de partage de 24 h (User Delegation SAS). |
| Storage Table Data Contributor | Créer et lire les tables `profils`, `etapes`, `annonces` et `heures`, et y écrire les données. |

Côté infrastructure, l'accès anonyme aux blobs doit être désactivé au niveau du compte de stockage
(Terraform : `allow_nested_items_to_be_public = false`).

## Mes démarches et notifications

- La page des démarches s'appelle "Mes démarches". Son adresse reste `/planning`, et `/mes-demarches`
  y redirige (redirection temporaire 302).
- La page Notifications (cloche en haut à droite, avec le nombre d'alertes) est calculée à l'affichage,
  sans base de données : échéances à moins de 7 jours ou dépassées, distributions d'entraide du jour
  et du lendemain, pièces encore à préparer pour la prochaine démarche. Pas encore d'e-mail.

## Vérifier les liens officiels

```
python scripts/verifier_liens.py
```

Le script teste chaque lien des données et signale les erreurs (403, 404), les redirections vers l'accueil
et les pages introuvables. Deux sites (CAF et Lokaviz) répondent par une page anti-robot : leurs liens restent
sur l'accueil et doivent être vérifiés à la main dans un navigateur.

## Lancer les tests

Les tests n'ont pas besoin d'Azurite : ils utilisent le stockage en mémoire.

Sous Windows (PowerShell) :

```
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest
```

Sous Linux ou macOS, activer l'environnement avec `source .venv/bin/activate`.

## Lancer sans Docker (mode mémoire)

Gunicorn ne fonctionne pas sous Windows. Pour un essai rapide, utiliser le serveur de développement Flask :

```
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:STORAGE_MODE = "memoire"
flask --app "app:create_app()" run --port 8000
```

Les données sont perdues à l'arrêt.

## Variables d'environnement

| Variable | Obligatoire | Description |
| --- | --- | --- |
| `SECRET_KEY` | Oui | Clé de signature des sessions Flask. Longue et aléatoire, jamais versionnée. |
| `APP_PORT` | Non | Port de la machine hôte utilisé par docker compose (8000 par défaut). Hors contrat, absent de `.env.example`. |
| `STORAGE_MODE` | Non | `memoire` (défaut), `azurite` (local) ou `azure` (Managed Identity). |
| `AZURE_STORAGE_CONNECTION_STRING` | En mode `azurite` | Toujours `UseDevelopmentStorage=true`, fournie directement par `docker-compose.yml`. Hors contrat, absente de `.env.example`. |
| `PHOTOS_CONTACT` | Pour le script de photos | Contact de l'équipe envoyé à Wikimedia Commons. Jamais versionné. |
| `AZURE_STORAGE_ACCOUNT_NAME` | En mode `azure` | Nom du compte de stockage (`stcap90prodfrc`). L'authentification passe par `DefaultAzureCredential`. |
| `AZURE_CLIENT_ID` | Si identité user-assigned | Client ID de l'identité managée, lu par `DefaultAzureCredential`. Inutile avec une identité system-assigned. |

Prévues par le [contrat d'interface avec l'infrastructure](https://github.com/FOGUERAYAN/PROJET_Cloud_Computing_Group17_Infrastructure), pas encore lues par le code : `KEY_VAULT_URL` (URL du Key Vault) et `APPLICATIONINSIGHTS_CONNECTION_STRING` (télémétrie Application Insights).

`.env.example` contient exactement les variables du contrat : `STORAGE_MODE`, `AZURE_STORAGE_ACCOUNT_NAME`,
`SECRET_KEY`, `KEY_VAULT_URL`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `AZURE_CLIENT_ID` (facultative) et `PHOTOS_CONTACT`.
Le port de l'application est fixé à 8000 dans le `Dockerfile`.

Aucun secret n'est écrit dans le code. Le fichier `.env` est ignoré par git et par Docker.

### Variables attendues sur la VM Azure

Le conteneur lit uniquement ces variables. Les noms doivent être écrits exactement ainsi
(lus dans `app/config.py`) :

| Variable | Valeur sur la VM | Origine |
| --- | --- | --- |
| `SECRET_KEY` | Chaîne longue et aléatoire | Secret de Key Vault, lu par la VM au démarrage. Jamais dans un fichier versionné ni dans l'image. |
| `STORAGE_MODE` | `azure` | Valeur fixe. |
| `AZURE_STORAGE_ACCOUNT_NAME` | Nom du compte de stockage, `stcap90prodfrc` (sans URL ni clé) | Sortie Terraform du compte de stockage. |
| `KEY_VAULT_URL` | URL du Key Vault | Prévue par le contrat, pas encore lue par l'application : `SECRET_KEY` arrive déjà par variable d'environnement. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Chaîne de connexion Application Insights | Prévue par le contrat, pas encore lue par l'application. |

À ne pas définir sur Azure : `AZURE_STORAGE_CONNECTION_STRING` (réservée à Azurite), `APP_PORT` (docker compose)
et `PHOTOS_CONTACT` (script local).

Si la VM utilise une identité managée **attribuée par l'utilisateur** (et non celle attribuée par le système),
`DefaultAzureCredential` doit aussi recevoir `AZURE_CLIENT_ID` (identifiant client de cette identité) pour savoir
laquelle utiliser. Avec l'identité attribuée par le système, rien à ajouter.

Exemple de lancement sur la VM, sans écrire le secret dans la commande ni dans un fichier versionné :

```
docker run -d --restart unless-stopped -p 8000:8000 \
  -e SECRET_KEY -e STORAGE_MODE=azure -e AZURE_STORAGE_ACCOUNT_NAME \
  <registre>/cap90-app:<version>
```

(`-e SECRET_KEY` sans valeur reprend la variable déjà chargée depuis Key Vault dans l'environnement de la VM.)
La sonde de santé du Load Balancer vise `/health` sur le port 8000.

## Image Docker

L'image part de `python:3.12.16-slim-trixie` : version exacte de Python (3.12.16) et de Debian (13, trixie),
pour que deux constructions donnent le même résultat. On met cette version à jour volontairement
(changer le tag, reconstruire, relancer les tests), au lieu de suivre automatiquement `python:3.12-slim`.
L'image tourne avec un utilisateur non root, expose le port 8000 et contient un `HEALTHCHECK` sur `/health`.

## Modèle de données (Azure Table Storage)

| Table | PartitionKey | RowKey | Champs |
| --- | --- | --- | --- |
| `profils` | `profil` | identifiant utilisateur (uuid) | pseudo, statut, ville, date_arrivee, langue, interets, cree_le |
| `etapes` | identifiant utilisateur | code de la démarche | titre, date_limite, statut (`a_faire`, `fait`), fait_le, pieces_pretes, ordre |
| `annonces` | ville normalisée | uuid | titre, description, categorie, photo_blob, cree_le, expire_le |
| `heures` | identifiant utilisateur | mois (AAAA-MM) | heures |

La table `annonces` est créée, mais ses pages ne sont pas encore développées.

## CI

Le workflow [`ci.yml`](.github/workflows/ci.yml) s'exécute sur chaque Pull Request vers `main` et sur chaque push sur `main` :

| Job | Vérifications |
| --- | --- |
| `lint-test` | `ruff check`, `ruff format --check`, `pytest` |
| `docker-build` | construction de l'image Docker |
| `gitleaks` | recherche de secrets dans tout l'historique Git |

La publication de l'image dans Azure Container Registry sera ajoutée si l'authentification de GitHub Actions vers Azure (OIDC) est autorisée sur Azure for Students.
