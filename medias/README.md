# Photos de Cap90

Dépose ici les images des lieux (jpg, jpeg, png ou webp). `scripts/charger_medias.py` convertit
les JPG et PNG en WebP (1200 px au plus, environ 150 Ko) avant l'envoi dans le stockage.
Noms autorisés : lettres sans accent, chiffres, tiret et tiret bas, par exemple `grand-place.jpg`.

Chaque photo doit avoir un crédit (auteur et licence) dans le champ `credit_photo` de `app/data/lieux.json`.
N'utilise que des photos dont la licence autorise la réutilisation, par exemple une photo de Wikimedia Commons
sous licence CC BY-SA, ou une photo que tu as prise toi-même.

Envoi dans le stockage : `python scripts/charger_medias.py` (voir le README principal).
