# Cap90

Cap90 aide les étudiants qui arrivent dans la Métropole Européenne de Lille pendant leurs 90 premiers jours.
L'utilisateur répond à 5 questions et obtient un rétroplanning daté de ses démarches administratives.
Un coffre-fort de justificatifs et un espace de dons entre habitants arriveront ensuite.

Projet de Cloud Computing, JUNIA ISEN. L'application tourne dans un conteneur Docker sur une VM Azure,
derrière un Load Balancer. Elle utilise Azure Table Storage et Azure Blob Storage via une Managed Identity.

## Fonctionnalités

- Accueil avec un bouton "Créer mon profil".
- Profil en 5 questions (statut, ville, date d'arrivée, langue maternelle, centres d'intérêt), sans mot de passe.
  L'identifiant utilisateur est gardé dans la session Flask.
- Planning : jour courant ("Jour 12 sur 90"), étapes avec date limite, jours restants, case "fait",
  pièces à fournir et lien officiel. Une étape à moins de 7 jours est signalée avec la couleur d'alerte.
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
  data/              catalogue des démarches, des lieux et de l'entraide
  templates/         pages Jinja
  static/css/        theme.css (palette) et app.css (mise en page)
medias/              photos à envoyer dans le conteneur Blob
scripts/             charger_medias.py
function/            future Azure Function (vide)
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
| `APP_PORT` | Non | Port de la machine hôte utilisé par docker compose (8000 par défaut). |
| `STORAGE_MODE` | Non | `memoire` (défaut), `azurite` (local) ou `azure` (Managed Identity). |
| `AZURE_STORAGE_CONNECTION_STRING` | En mode `azurite` | Toujours `UseDevelopmentStorage=true`. Aucune clé de compte. |
| `AZURE_STORAGE_ACCOUNT_NAME` | En mode `azure` | Nom du compte de stockage. L'authentification passe par `DefaultAzureCredential`. |

Aucun secret n'est écrit dans le code. Le fichier `.env` est ignoré par git et par Docker.

## Modèle de données (Azure Table Storage)

| Table | PartitionKey | RowKey | Champs |
| --- | --- | --- | --- |
| `profils` | `profil` | identifiant utilisateur (uuid) | pseudo, statut, ville, date_arrivee, langue, interets, cree_le |
| `etapes` | identifiant utilisateur | code de la démarche | titre, date_limite, statut (`a_faire`, `fait`), fait_le, ordre |
| `annonces` | ville normalisée | uuid | titre, description, categorie, photo_blob, cree_le, expire_le |
| `heures` | identifiant utilisateur | mois (AAAA-MM) | heures |

La table `annonces` est créée, mais ses pages ne sont pas encore développées.
