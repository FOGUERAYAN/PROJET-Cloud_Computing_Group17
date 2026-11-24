# Cap90 – Application

Cap90 aide les nouveaux arrivants en France (étudiants internationaux, expatriés, réfugiés) pendant leurs trois premiers mois. À l'inscription, l'utilisateur répond à cinq questions (statut, ville, date d'arrivée, langue maternelle, centres d'intérêt) et l'application génère un rétroplanning personnalisé des démarches, avec leurs dates limites.

Projet Cloud Computing – JUNIA ISEN, équipe 17.

- Dépôt de l'infrastructure : [PROJET_Cloud_Computing_Group17_Infrastructure](https://github.com/FOGUERAYAN/PROJET_Cloud_Computing_Group17_Infrastructure)
- Règles de travail : [CONTRIBUTING.md](CONTRIBUTING.md)

## Fonctionnalités

| Module | Contenu | Version |
|---|---|---|
| 1 – Rétroplanning et kits de langue | checklist datée depuis le jour d'arrivée, pièces requises, liens officiels, rappels, lexique | V1 |
| 2 – Coffre-fort et partage 24 h | dépôt de justificatifs, lien de partage valable 24 h (User Delegation SAS) | V1 |
| 3 – Solidarité et dons | annonces de dons avec photo, supprimées après 30 jours | V1 |
| 4 – Parrainage et associations | décrit dans le rapport, non développé | V2 |

## Stack technique

Python 3.12, Flask, Gunicorn (port 8000), azure-identity, azure-storage-blob, azure-data-tables, pytest, ruff. Développement local avec l'émulateur Azurite.

## Configuration

L'application est configurée uniquement par variables d'environnement (principe 12-Factor). Modèle : [`.env.example`](.env.example).

| Variable | Rôle |
|---|---|
| `PORT` | port d'écoute (8000) |
| `STORAGE_ACCOUNT_NAME` | compte de stockage (Blob et Table) |
| `KEY_VAULT_URL` | URL du Key Vault |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | télémétrie Application Insights |

Aucune clé ni aucun mot de passe : l'application s'authentifie avec `DefaultAzureCredential` (identité managée sur Azure, `az login` en local).

## Lancer en local

> Section complétée par Hafsatou (installation, Azurite, lancement, tests).

## CI

Le workflow [`ci.yml`](.github/workflows/ci.yml) s'exécute sur chaque Pull Request vers `main` et sur chaque push sur `main` :

| Job | Vérifications |
|---|---|
| `lint-test` | `ruff check`, `ruff format --check`, `pytest` |
| `docker-build` | construction de l'image Docker |
| `gitleaks` | recherche de secrets dans tout l'historique Git |

La publication de l'image dans Azure Container Registry sera ajoutée si l'authentification GitHub Actions → Azure (OIDC) est autorisée sur Azure for Students.
