# PLAN — assistant IA en jeu

Design validé nistroy 2026-09-12 (ex-`IA.md` du dépôt `Nistroy/minecraft-server`). Code générique : n'importe quel
modpack Fabric 1.21.1 ; connaissances d'un modpack = dépôt séparé.

## Bascule MCP (validé nistroy 2026-10-05)
Remplace Gemini : chaque pote interroge le serveur avec sa propre IA (abonnement Claude Pro / ChatGPT Plus / Antigravity).
| Étape | Contenu | État |
|---|---|---|
| 1 | `minecraft-ia mcp` : MCP lecture seule, fichiers du jeu, statut live (ping) | fait 2026-10-05 |
| 2 | exposition : Tailscale Funnel (pas de domaine), 1 lien secret/pote, révocable | en service 2026-10-05 (Funnel 443 → 8766, test externe OK) |
| 3 | mod : écran `I` lance la CLI headless du pote (`claude -p`, `codex exec`, `agy -p`) branchée sur le MCP, outils MCP seuls ; TPS + positions joueurs (code serveur) | code fait 2026-10-05 (v0.3.0) |
| 4 | retrait Gemini + `/ia` ; pote sans abonnement payant = pas d'assistant (choix nistroy) | à faire |

Vérifié 2026-10-05 :
- Claude : connecteur MCP perso dès le gratuit (1 seul), OAuth facultatif, appelé depuis le cloud Anthropic → URL publique
  (support.claude.com 11175166). Claude Code (`-p`) : Pro minimum.
- ChatGPT : mode développeur, MCP distant, auth « No Authentication » possible (developers.openai.com developer-mode).
  Codex CLI : `codex exec`, MCP HTTP dans `~/.codex/config.toml`, offre Plus minimum.
- Antigravity : MCP distant = clé `serverUrl` dans `~/.gemini/antigravity/mcp_config.json` (`url` ignoré sans erreur).
- Gemini CLI : connexion Google gratuite fermée 2026-06-18 (geminicli.com quota-and-pricing).
- Abonnement d'un pote ≠ API : jamais branché ailleurs que dans sa propre CLI/appli.

Étape 2 : lien `https://<public_host>/<jeton>/mcp` (`minecraft-ia mcp-link add|list|revoke <nom>`) ; fichier
`mcp_links_file` (0600) = empreintes SHA-256 seules, relu à chaque changement (révocation sans redémarrage) ; autre
chemin = 404 (`SecretPathAuth`) ; uvicorn sans journal d'accès (jeton dans le chemin) ; Host accepté = local +
`public_host`. Machine Tailscale renommée `mc-potes` (prénom hors URL publique / journaux CT, nistroy 2026-10-05).
Positions des joueurs visibles par tout détenteur d'un lien.

Étape 3 (choix nistroy 2026-10-05 : Claude Code + Codex + Antigravity, tous restreints au MCP ; lien automatique ;
potes sous Windows) :
- Lien auto : mod → `POST /mcp-link` cerveau (`player`, `name`) → `LinkStore.provision("<pseudo>-jeu")` (nouveau jeton, ancien mort ; nom distinct du lien manuel `<pseudo>`) →
  `{url: https://<public_host>/mcp, token}` ; jeton envoyé par `Authorization: Bearer` (pas dans les arguments).
  `revoke` laisse une marque `revoked` : plus de lien auto tant que `mcp-link add` n'a pas rouvert.
- Live : mod serveur écrit `live_status_file` (JSON `updated`, `tps`, `mspt`, `players[name, dimension, x, y, z]`)
  toutes les 5 s ; `server_status` l'ajoute si < 30 s.
- Verrous vérifiés 2026-10-05 : `claude -p --tools "" --strict-mcp-config --mcp-config <fichier>` (CLI 2.1.289) ;
  `codex exec --ignore-user-config -s read-only -a never --disable shell_tool --disable unified_exec
  -c web_search=disabled -c tools.view_image=false` (learn.chatgpt.com config-reference / developer-commands, non
  testé ici) ; `agy -p` refuse en headless toute action à approuver (testé : commande, lecture hors dossier) mais
  MCP + permission `mcp(minecraft-ia/*)` seulement en config globale (`~/.gemini/config/mcp_config.json`,
  `~/.gemini/antigravity-cli/settings.json`) ; `.agents/` = projet (règles, skills, plugins, hooks), pas de
  permissions. `agy` : pas de stdin (`-p` exige le texte en argument), sortie `--output-format json` → `response`.
- Mod v0.3.0 : `cli/` (Java pur, JUnit) = `Executables` (PATH + PATHEXT, `~/.local/bin`, `%APPDATA%/npm` ; .cmd/.bat →
  arguments sans `"&|<>^%!` ni saut de ligne), `CliCommand` (lignes verrouillées ci-dessus, jeton : fichier `mcp.json`
  Claude / variable `MINECRAFT_IA_TOKEN` Codex / config globale agy), `CliRunner`, `CliOutput`, `AgyConfig` (refuse si
  `toolPermission` ∉ {request-review, strict} ou règle allow ≠ `mcp(`/`read_url(`), `ClientConfig`
  (`config/minecraft_ia-client.json` : `mode` auto/claude/codex/agy/server, chemins, lien). Client `LocalAssistant` ;
  bouton de l'écran = choix de l'IA ; « Autoriser » = `agy mcp add` + règle, sur clic du joueur.
- Testé 2026-10-05 sur le Mac (pipeline Java réel) : Claude Code 12 s, réponse tirée de la table de loot, `whoami`
  refusé ; agy 60 s, statut via MCP, `whoami` refusé (config agy de nistroy restaurée après). Codex : non testé (absent
  du Mac). Windows : non testé (lancement .cmd, chemins).

## But
- Joueur pose question sur mods en jeu → réponse rapide, sourcée, sinon "je sais pas". Jamais inventer.
- IA note ce qu'elle trouve (notes md + statut) → répond plus vite ensuite.
- EMI (recettes/usages) + Jade (bloc visé) supposés dans le pack → IA vise mécaniques, "où trouver", compat.

## Décisions
| Sujet | Choix | Pourquoi |
|---|---|---|
| Interface | écran client (touche `I` par défaut, réassignable) : onglets conversation/historique, bulles, défilement, votes ✔/✘ ; icônes d'items dans le texte ; grille 3x3 des recettes de table de craft citées | privé + historique. 1.21.1 : pas de dialogs serveur (1.21.6+, minecraft.wiki `Dialog`) |
| Icônes | optionnelles : `[[ns:id]]`/`[[#ns:tag]]` après le nom dans `answer.text` ; client `renderItem` (modèles du jeu), tag = défilement 1 s ; grille = source `data:recipe:` lue dans `RecipeManager` client (1.21.1 : `ClientboundUpdateRecipesPacket`), façonnée/sans forme seulement ; chat : marqueurs retirés | visuel sans appel LLM en plus ; pas de changement de payload |
| Secours | `/ia <question>`, `/ia historique`, `/ia vote <id> oui\|non` (boutons chat cliquables), réponse privée | joueur sans mod client |
| 1 jar | mod `minecraft_ia` unique, `environment: *`, sources client séparées (Loom `splitEnvironmentSourceSets`) | 1 release, 1 version ; serveur seul OK, client seul OK (écran dit "serveur sans assistant") |
| Transport | `CustomPacketPayload` + `PayloadTypeRegistry` + `ServerPlayNetworking`/`ClientPlayNetworking`, tailles bornées au décodage (`readUtf(max)`) | joueur authentifié par MC ; rien exposé sur internet/tunnel |
| Cerveau | service Python séparé, `127.0.0.1:8765`, jeton partagé (`~/.config/minecraft-ia/brain-token`, 0600) ; mod serveur = passerelle mince async | corriger/relancer sans redémarrer MC ; testable sans MC |
| LLM | `gemini-3.8-flash`, `thinking_level` `high`, SDK `google-genai==2.23.0`, tier gratuit (vérifié ai.google.dev 2026-09-12 : stable, gratuit, pas de grounding Search, contenu utilisé par Google — accepté nistroy) | gratuit |
| Secours | `fallback_models` (défaut `gemini-3.7-flash`, `gemini-3.5-flash`) : question relancée en conversation neuve sur 503/429 ; `gemini-2.5-flash` fermé aux nouveaux comptes | 2026-09-13 : `gemini-3.8-flash` saturé (503) + 429 après 8 appels ; quotas gratuits comptés par modèle |
| LLM isolé | `brain/src/minecraft_ia/llm.py` seul | changer fournisseur = 1 module |
| Boucle outils | la nôtre (`automatic_function_calling` désactivé) ; réponse finale = outil `answer(text, sources)` | contrôle des sources |
| Pré-recherche | avant chaque modèle : `search_knowledge` + 2 meilleures fiches jointes à la question (sources enregistrées) ; 429 par minute ≤ 15 s → attente puis même modèle | tier gratuit constaté 2026-09-13 : 20 requêtes/jour/modèle, 5/min → viser 1-2 appels/question |
| Anti-invention | source citée acceptée seulement si renvoyée par un outil pendant la recherche ; sinon "je sais pas" | garde-fou en code, pas en prompt |
| Internet | outils maison : API Modrinth, README + issues GitHub (domaines fixes, pas d'URL libre) | ciblé versions ; pas de SSRF/injection via URL |
| Connaissances | dépôt git séparé (`Nistroy/minecraft-ia-kb`, public, CC BY-SA 4.0) ; IA commit (auteur `minecraft-ia`), nistroy édite/revert | lisible, historique, annulation |
| Stockage | SQLite `STRICT`, migrations numérotées (`PRAGMA user_version`), 1 module (`db.py`), FTS5 `unicode61 remove_diacritics 2` | 1 écrivain, 2-5 joueurs |
| Pas de base vectorielle | FTS + lecture des fiches par outil | exactitude noms/ID, debug facile |
| Quotas | par joueur/jour + budget global d'appels LLM/jour, jour = minuit heure du Pacifique (reset RPD Google) ; configurables | limites free tier visibles seulement dans AI Studio |
| Distribution mod | pack packwiz auto-maj du serveur, URL de release GitHub | aucune action des potes |
| MCP | `minecraft-ia mcp`, Streamable HTTP `127.0.0.1:8766/mcp` (`mcp_port`), SDK `mcp==2.3.0` (`MCPServer`), sans état + JSON ; outils `Toolbox` sauf `save_note`/`answer` + `MCP_SPECS` ; erreur d'outil = `ToolError` (JSON) | lecture seule depuis l'extérieur ; aucun LLM côté serveur |
| Fichiers du jeu | `extract` : texte `data/**.json\|mcfunction\|txt` des jars (+ imbriqués, vanilla), `fabric.mod.json` de 1er niveau, `config_dir` du serveur → tables `game_file`/`installed_mod` ; recherche sous-chaîne `instr` (≈35 000 fichiers, 50 Mo, < 0,1 s) | taux de drop, loot, spawn lus dans le vrai fichier ; plusieurs origines par chemin gardées (surcharge datapack) |
| Configs à secret | fichier exclu en entier si clé `*token*`/`*password*`/`*secret*`/`api_key`/`webhook` (`_SECRET_KEY`) ou nom suspect ; caché/binaire/> 1 Mo exclus | 2026-10-05 : `minecraft_ia.json`, `resourceful-config-web.json` exclus |
| Statut live | Server List Ping `127.0.0.1:minecraft_port` (`status.py`) : en ligne, version, MOTD, joueurs (échantillon vanilla) + mods installés | sans console ni RCON ; TPS + positions impossibles par ping → étape 3 |
| Licence | GPL-3.0-only (code) · CC BY-SA 4.0 (connaissances) | choix nistroy 2026-09-12 |

## Architecture
touche/`/ia` → mod (écran client ou commande) → payload → `Gateway` (1 requête en cours/joueur, HTTP async) →
`POST /ask` 127.0.0.1 + `Authorization: Bearer` → `Assistant` (quotas → boucle outils Gemini → contrôle sources →
historique) → réponse → payload écran ou message chat privé.

## Données
| Couche | Contenu | Écrit par | Format |
|---|---|---|---|
| Exactes | items/blocs/mobs (lang `en_us`/`fr_fr`), recettes `data/*/recipe/*.json`, vanilla (jar serveur + `fr_fr` assets Mojang) | `minecraft-ia extract` | SQLite, regénérable, **jamais commité** (contenu des mods) |
| Fiches | 1 fiche caveman/mod + `index.md` généré ; format : `README.md` du dépôt kb | agents + vérif, puis IA/nistroy | md git |
| Notes | fait + source + version + date + statut `non-vérifié`/`confirmé-joueur`/`validé-nistroy`/`contesté` | IA (`save_note`), votes | md git, frontmatter |
| Index | FTS fiches + notes | reconstruit (`kb index`, démarrage, après note/vote) | SQLite |
| Historique + votes | par joueur (UUID) | cerveau | SQLite, **à sauvegarder**, jamais commité |

## Règles de réponse (où c'est appliqué)
- Source obligatoire, sinon "je sais pas" → `Assistant._finalize`.
- Icône gardée si id renvoyé par un outil (`ToolContext.item_ids`) ET item/bloc extrait ou tag d'une recette extraite
  (`Database.renderable`), 6 max ; sinon marqueur retiré, mot gardé → `Assistant._with_icons`, `markers.py`.
- Priorité : données exactes > `validé-nistroy` > fiches > `confirmé-joueur` > web > `non-vérifié` → prompt.
- Vote ✘ → notes citées `contesté` + 1 seule relance (ne coûte pas de question) ; vote ✔ → `confirmé-joueur` ;
  votes ne touchent jamais `validé-nistroy` ; seul l'auteur vote → `Assistant.vote`, `KnowledgeBase.set_note_status`.
- "Je cherche…" immédiat (chat) / entrée en attente (écran).
- Calibrer contre "je sais pas" partout : `minecraft-ia eval <questions.toml>` (0 invention exigé).

## État 2026-09-13
- [x] 0 dépôts GitHub publics `Nistroy/minecraft-ia` + `Nistroy/minecraft-ia-kb` ; `IA.md` retiré du dépôt serveur (PR #12)
- [x] 2 cerveau + CLI (`serve`, `ask`, `extract`, `kb index`, `eval`), pytest + CI verts
- [x] 3-4 mod serveur + client (1 jar), JUnit + CI verts
- [x] extraction réelle, 104 jars du serveur : 7 703 noms, 4 290 recettes
- [x] 1 fiches : 1 par mod de contenu installé, agents + relecture par échantillon (kb PR #1 mergée)
- [x] clé Gemini + limites réelles (429) → 6 questions/joueur/jour, 55 appels LLM/jour
- [x] release `v0.1.0` + serveur (backup `pre-minecraft-ia_2026-09-13_22h10`, log : mod chargé, 0 nouvelle erreur) +
  pack packwiz (`minecraft-server` PR #13) — 2026-09-13
- [ ] test en jeu (`/ia` joueur seulement, pas testable en console) : touche `I`, écran, `/ia` chat, votes, quotas
- [x] v0.2.0 : écran refait + icônes + grilles de craft, pytest + JUnit verts (rendu non testé automatiquement) — 2026-09-13
- [x] v0.2.0 déployée : pack + jar serveur 2026-09-30 (cerveau déjà à jour, lancé 2026-09-27) ; rendu en jeu à vérifier
- [ ] jeu de questions test : `minecraft-ia-kb/eval/questions.toml` (6 amorces) + vraies questions des potes ; `eval` = 0 invention
- [x] cerveau lancé par `./mc start` du dépôt serveur (tmux `ia`, avant le serveur ; `stop` le laisse) — 2026-09-13
- [ ] sauvegarde `brain.sqlite3`
- [x] MCP lecture seule local (`minecraft-ia mcp`) : 11 outils, extraction réelle 139 jars / 34 739 fichiers, appels HTTP réels OK — 2026-10-05
- [ ] `save_note` sans dédoublonnage : 2 notes crabe identiques dans kb (2026-09-13)

## Fiches : leçons
- Agents (Sonnet) extrapolent : noms FR inventés quand le jar n'a pas de `fr_fr`, mécaniques déduites de noms de
  fichiers, comparaisons à des défauts non sourcés. Relire par échantillon, vérifier contre jar / config / Modrinth
  (HTML du body retiré avant recherche).
- Max 2 agents en parallèle, 1 si la limite approche : 8 agents Opus ont épuisé la limite de session 2026-09-12,
  2 agents Sonnet l'ont touchée 2026-09-13.
- `fr_fr` d'un jar parfois périmé (Naturalist) : nom FR seulement si la clé correspond à une entité actuelle.
- Frontmatter invalide = fiche ignorée par le cerveau (log) ; `python` + `KnowledgeBase` pour valider avant commit.

## À revérifier avant maj
- Modèles/tier/thinking Gemini : `ai.google.dev/gemini-api/docs/models`, `/pricing`, `/thinking`, `/rate-limits`.
- Fabric : `meta.fabricmc.net`, template `FabricMC/fabric-example-mod` branche de la version MC ; signatures via `javap` sur jars Loom.

## Sécurité
- Clé Gemini, jeton cerveau, jeton GitHub : `~/.config/minecraft-ia/`, jamais lus ni affichés (erreurs = chemin seulement).
- Cerveau refuse tout bind non local (config + `make_server`) ; mod refuse `brainUrl` non local (le jeton ne sort pas).
- Payloads bornés ; texte joueur nettoyé (`QuestionPolicy`), jamais shell/console ; noms joueur `[A-Za-z0-9_]{1,16}`.
- IA : aucun accès console/commandes MC ; contenu web = données (prompt) ; `save_note` exige une URL déjà vue.
- Logs : jamais le contenu des questions.
