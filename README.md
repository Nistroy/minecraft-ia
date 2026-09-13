# minecraft-ia

Assistant IA en jeu pour un serveur Minecraft **Fabric 1.21.1** moddé. Un joueur appuie sur `I` (ou tape
`/ia <question>`) et pose sa question sur les mods du serveur ; il reçoit une réponse courte avec ses sources,
ou « je sais pas ». L'assistant n'invente pas : une réponse n'est acceptée que si les sources qu'elle cite ont
réellement été consultées pendant la recherche.

## Comment ça marche

```
touche I / /ia ──► mod (client ou serveur) ──► mod serveur ──HTTP 127.0.0.1──► cerveau Python ──► Gemini
                                                                                  │
                                            fiches des mods (git) · données exactes des jars (SQLite)
                                            API Modrinth · README et issues GitHub
```

- **Mod** (`mod/`) : un seul jar Fabric, à installer sur le serveur et, facultatif, chez les joueurs. Côté client :
  un écran (question, conversation, historique perso, votes ✔/✘) qui montre les icônes des items dans les réponses
  et la grille de craft des recettes citées. Sans le mod client, `/ia` répond dans le chat, en privé, avec des
  boutons cliquables.
- **Cerveau** (`brain/`) : service Python local qui cherche dans les connaissances, appelle le LLM, vérifie les
  sources, garde l'historique et les votes. Il n'écoute que sur `127.0.0.1`.
- **Connaissances** : un dépôt git séparé par modpack (exemple : [minecraft-ia-kb](https://github.com/Nistroy/minecraft-ia-kb)).
  Une fiche par mod, plus les notes que l'IA apprend en cherchant. Chaque note est un commit : tout est visible
  et annulable.

## Installation côté serveur

Prérequis : Java 21, Python 3.12+, git, une clé API Gemini ([AI Studio](https://aistudio.google.com)).

```sh
# Cerveau
cd brain
python3 -m venv .venv && .venv/bin/pip install -e .
mkdir -p ~/.config/minecraft-ia
cp config.example.toml ~/.config/minecraft-ia/config.toml   # puis adapter les chemins
# clé Gemini dans ~/.config/minecraft-ia/gemini-key (chmod 600)
.venv/bin/minecraft-ia extract      # noms FR/EN + recettes depuis les jars
.venv/bin/minecraft-ia kb index     # index des fiches
.venv/bin/minecraft-ia serve        # crée le jeton ~/.config/minecraft-ia/brain-token au premier lancement

# Mod : jar des releases dans mods/ du serveur (et du pack joueurs).
# Au premier démarrage : config/minecraft_ia.json (adresse du cerveau, chemin du jeton, limites).
```

Tester sans Minecraft : `minecraft-ia ask "comment aller dans l'Aether ?"`. Mesurer la qualité :
`minecraft-ia eval questions.toml` (questions attendues + pièges qui doivent donner « je sais pas »).

## Vie privée et sécurité

- Les questions restent sur la machine du serveur (SQLite, jamais commitées). Avec le tier gratuit de Gemini,
  Google peut utiliser le contenu envoyé pour améliorer ses produits.
- Clé Gemini et jeton du cerveau : fichiers hors dépôt, jamais affichés.
- Le cerveau refuse d'écouter ailleurs qu'en local ; le mod refuse une adresse de cerveau non locale.
- L'IA n'a aucun accès à la console ni aux commandes Minecraft.

## Développement

Voir `CLAUDE.md` (tests, conventions) et `PLAN.md` (décisions, état).

## Licence

Code : [GPL-3.0](LICENSE). Les connaissances d'un modpack vivent dans leur propre dépôt, avec leur propre licence.
