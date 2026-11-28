# Azure Function de Cap90 : tâches nocturnes

Function Python (modèle de programmation v2) déclenchée par un minuteur, **chaque nuit à 03:00 UTC**.
Elle enchaîne deux tâches indépendantes : si l'une échoue, l'erreur est journalisée et l'autre s'exécute quand même.

## Rôle

1. **Purge des annonces**
   - Supprime dans la table `annonces` les annonces dont `expire_le` est dépassé.
   - Sans `expire_le`, l'expiration vaut `cree_le` + 30 jours (J+30).
   - Supprime aussi leur photo (`photo_blob`) dans le conteneur `annonces-photos`. La photo est supprimée d'abord,
     l'annonce ensuite : si la photo ne peut pas être supprimée, l'annonce reste et sera reprise la nuit suivante.
   - Une annonce dont aucune date n'est lisible n'est jamais supprimée : elle est signalée dans les journaux.
2. **Rappels des démarches**
   - Repère dans la table `etapes` les démarches non faites dont la date limite est à moins de 7 jours ou dépassée
     (même seuil que la page Notifications de l'application).
   - Écrit une ligne par utilisateur dans les journaux (sortie standard et Application Insights), avec
     seulement l'identifiant tronqué à 8 caractères et les codes des démarches : ni pseudo, ni ville, ni titre.
   - Point d'extension pour l'e-mail (V2) : `rappels.py` définit l'interface `CanalRappel`,
     le canal `CanalJournal` (V1) et le canal `CanalEmail` (prévu, pas encore disponible). Le canal se choisit
     dans `choisir_canal()`.

## Planning

| Élément | Valeur |
| --- | --- |
| Expression NCRONTAB | `0 0 3 * * *` (secondes, minutes, heures, jour, mois, jour de la semaine) |
| Heure | 03:00 UTC, soit 04:00 à Paris en hiver et 05:00 en été |
| Fuseau | UTC. Ne pas définir `WEBSITE_TIME_ZONE` (non pris en charge sur Linux en plan Consommation). |
| Démarrage | `run_on_startup=False` : pas d'exécution au démarrage ni au déploiement |

Le test `test_minuteur_a_3_h_utc` vérifie que la seule fonction enregistrée est `taches_nocturnes`,
avec ce planning exact.

## Fichiers

```
function/
  function_app.py              minuteur et enchaînement des deux tâches
  taches.py                    logique de choix (fonctions pures, testées sans réseau)
  rappels.py                   canaux de rappel (journaux en V1, e-mail en V2)
  stockage.py                  accès aux tables et aux blobs pour la Function
  host.json
  requirements.txt             dépendances propres à la Function
  local.settings.example.json  exemple de configuration locale, sans secret
  essai_local.py               essai contre Azurite sans les Core Tools
  tests/                       tests pytest
```

La Function a son propre `stockage.py` au lieu de réutiliser `app/services/storage.py` : elle est déployée
depuis son dossier seul (le code de `app/` ne serait pas dans le paquet) et n'a pas besoin de Flask.

## Configuration

| Variable | Valeur | Rôle |
| --- | --- | --- |
| `STORAGE_MODE` | `azure` sur Azure, `azurite` en local | Choix du stockage |
| `AZURE_STORAGE_ACCOUNT_NAME` | Nom du compte de stockage de l'application | Tables `annonces` et `etapes`, conteneur `annonces-photos` |
| `AzureWebJobsStorage__accountName` | Nom du compte de stockage du runtime Functions | Stockage interne du runtime (verrous du minuteur), par identité, sans clé |
| `AZURE_CLIENT_ID` | Identifiant client de l'identité | Seulement si l'identité managée est attribuée par l'utilisateur |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Chaîne de connexion | Envoi des journaux vers Application Insights |

Aucune clé de compte n'est utilisée : sur Azure, l'accès passe par `DefaultAzureCredential` (identité managée).
En local, la chaîne `UseDevelopmentStorage=true` vise l'émulateur Azurite.

## Rôles RBAC de l'identité de la Function

Sur le compte de stockage de l'application :

| Rôle | Utilité |
| --- | --- |
| Storage Table Data Contributor | Lire `etapes`, lire et supprimer dans `annonces` |
| Storage Blob Data Contributor | Supprimer les photos dans `annonces-photos` |

Sur le compte de stockage du runtime (`AzureWebJobsStorage__accountName`) : **Storage Blob Data Owner**,
nécessaire au runtime pour les connexions par identité (verrous et état du minuteur).

## Conteneur et table

Le conteneur `annonces-photos` est créé par le module Terraform `storage` du dépôt
[PROJET_Cloud_Computing_Group17_Infrastructure](https://github.com/FOGUERAYAN/PROJET_Cloud_Computing_Group17_Infrastructure).
La table `annonces` est créée par l'application au démarrage. La Function ne crée rien : si la table est vide,
elle journalise "rien à purger" et s'arrête normalement.

## Lancer en local

Prérequis : Azurite lancé (`docker compose up -d` à la racine du dépôt) et, pour `func start`,
les [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) version 4.

1. Préparer un environnement Python pour la Function :

   ```
   cd function
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copier `local.settings.example.json` vers `local.settings.json` (fichier ignoré par git).
3. Lancer `func start`.
4. Déclencher le minuteur sans attendre 03:00 :

   ```
   curl -X POST http://localhost:7071/admin/functions/taches_nocturnes -H "Content-Type: application/json" -d "{}"
   ```

Sans les Core Tools, `python function/essai_local.py` (depuis la racine du dépôt) crée une annonce expirée et
une annonce valide avec leurs photos dans Azurite, lance les deux tâches, vérifie que seule l'annonce expirée
et sa photo ont disparu, puis nettoie.

## Tests

Les tests de `function/tests/` font partie de la suite pytest du dépôt (`pytest` à la racine) et donc de la CI.
Ils couvrent le choix des annonces à purger, l'ordre photo puis annonce, la reprise après un échec,
le choix des démarches à rappeler (seuil de 7 jours), l'absence de donnée personnelle dans les journaux,
le point d'extension e-mail et le planning du minuteur.
