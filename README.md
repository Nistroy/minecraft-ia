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

## Avec ta propre IA (Claude, ChatGPT/Codex, Antigravity)

Si tu as Claude Code, Codex ou Antigravity installé et connecté sur ton PC, l'écran (`I`) peut leur poser la question
à la place de l'IA du serveur. C'est ton abonnement qui répond, et l'IA ne peut utiliser que les outils du serveur
(fichiers du jeu, tables de loot, fiches, statut) : ni ton terminal, ni tes fichiers, ni le web.

- Le bouton en haut de l'écran choisit l'IA ; le mod trouve tout seul celles qui sont installées.
- Ton lien d'accès au serveur est créé automatiquement à la première question et gardé dans
  `config/minecraft_ia-client.json`. Ne partage pas ce fichier.
- Antigravity n'a pas d'option de verrouillage à chaque lancement : le bouton « Autoriser » ajoute à sa config le seul
  serveur MCP `minecraft-ia`. Le mod refuse de le lancer si ta config Antigravity approuve d'office des commandes ou
  des écritures.

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

### Serveur MCP (lecture seule)

`minecraft-ia mcp` expose les mêmes outils, plus la lecture des fichiers du jeu (tables de loot, tags, configs des
mods) et l'état du serveur (en ligne, version, joueurs connectés), à l'IA de chaque joueur : Claude, ChatGPT,
Antigravity… Aucun LLM ne tourne sur le serveur ; rien ne peut y être écrit. Il n'écoute que sur `127.0.0.1` ;
on l'expose sur internet avec un tunnel HTTPS, par exemple `tailscale funnel --bg 8766`, puis on règle
`public_host` dans la config.

Chaque joueur reçoit son propre lien secret, révocable à tout moment, même pendant que le serveur tourne :

```sh
minecraft-ia mcp-link add alex      # affiche https://<public_host>/<jeton>/mcp, une seule fois
minecraft-ia mcp-link list
minecraft-ia mcp-link revoke alex
```

Le lien se colle tel quel dans Claude (connecteur personnalisé), ChatGPT (mode développeur, sans authentification)
ou Antigravity (`serverUrl`). Toute autre adresse répond 404.

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
