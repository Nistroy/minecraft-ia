# PLAN — assistant IA en jeu

Design validé nistroy 2026-09-12 (ex-`IA.md` du dépôt `Nistroy/minecraft-server`). Code générique : n'importe quel
modpack Fabric 1.21.1 ; connaissances d'un modpack = dépôt séparé.

## But
- Joueur pose question sur mods en jeu → réponse rapide, sourcée, sinon "je sais pas". Jamais inventer.
- IA note ce qu'elle trouve (notes md + statut) → répond plus vite ensuite.
- EMI (recettes/usages) + Jade (bloc visé) supposés dans le pack → IA vise mécaniques, "où trouver", compat.

## Décisions
| Sujet | Choix | Pourquoi |
|---|---|---|
| Interface | écran client (touche `I` par défaut, réassignable) : question, conversation, historique perso, votes ✔/✘ | privé + historique. 1.21.1 : pas de dialogs serveur (1.21.6+, minecraft.wiki `Dialog`) |
| Secours | `/ia <question>`, `/ia historique`, `/ia vote <id> oui\|non` (boutons chat cliquables), réponse privée | joueur sans mod client |
| 1 jar | mod `minecraft_ia` unique, `environment: *`, sources client séparées (Loom `splitEnvironmentSourceSets`) | 1 release, 1 version ; serveur seul OK, client seul OK (écran dit "serveur sans assistant") |
| Transport | `CustomPacketPayload` + `PayloadTypeRegistry` + `ServerPlayNetworking`/`ClientPlayNetworking`, tailles bornées au décodage (`readUtf(max)`) | joueur authentifié par MC ; rien exposé sur internet/tunnel |
| Cerveau | service Python séparé, `127.0.0.1:8765`, jeton partagé (`~/.config/minecraft-ia/brain-token`, 0600) ; mod serveur = passerelle mince async | corriger/relancer sans redémarrer MC ; testable sans MC |
| LLM | `gemini-3.8-flash`, `thinking_level` `high`, SDK `google-genai==2.23.0`, tier gratuit (vérifié ai.google.dev 2026-09-12 : stable, gratuit, pas de grounding Search, contenu utilisé par Google — accepté nistroy) | gratuit |
| Secours | `fallback_models` (défaut `gemini-3.7-flash`, `gemini-3.5-flash`) : question relancée en conversation neuve sur 503/429 ; `gemini-2.5-flash` fermé aux nouveaux comptes | 2026-09-13 : `gemini-3.8-flash` saturé (503) + 429 après 8 appels ; quotas gratuits comptés par modèle |
| LLM isolé | `brain/src/minecraft_ia/llm.py` seul | changer fournisseur = 1 module |
| Boucle outils | la nôtre (`automatic_function_calling` désactivé) ; réponse finale = outil `answer(text, sources)` | contrôle des sources |
| Anti-invention | source citée acceptée seulement si renvoyée par un outil pendant la recherche ; sinon "je sais pas" | garde-fou en code, pas en prompt |
| Internet | outils maison : API Modrinth, README + issues GitHub (domaines fixes, pas d'URL libre) | ciblé versions ; pas de SSRF/injection via URL |
| Connaissances | dépôt git séparé (`Nistroy/minecraft-ia-kb`, public, CC BY-SA 4.0) ; IA commit (auteur `minecraft-ia`), nistroy édite/revert | lisible, historique, annulation |
| Stockage | SQLite `STRICT`, migrations numérotées (`PRAGMA user_version`), 1 module (`db.py`), FTS5 `unicode61 remove_diacritics 2` | 1 écrivain, 2-5 joueurs |
| Pas de base vectorielle | FTS + lecture des fiches par outil | exactitude noms/ID, debug facile |
| Quotas | par joueur/jour + budget global d'appels LLM/jour, jour = minuit heure du Pacifique (reset RPD Google) ; configurables | limites free tier visibles seulement dans AI Studio |
| Distribution mod | pack packwiz auto-maj du serveur, URL de release GitHub | aucune action des potes |
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
- Priorité : données exactes > `validé-nistroy` > fiches > `confirmé-joueur` > web > `non-vérifié` → prompt.
- Vote ✘ → notes citées `contesté` + 1 seule relance (ne coûte pas de question) ; vote ✔ → `confirmé-joueur` ;
  votes ne touchent jamais `validé-nistroy` ; seul l'auteur vote → `Assistant.vote`, `KnowledgeBase.set_note_status`.
- "Je cherche…" immédiat (chat) / entrée en attente (écran).
- Calibrer contre "je sais pas" partout : `minecraft-ia eval <questions.toml>` (0 invention exigé).

## État 2026-09-13
- [x] 0 dépôts GitHub publics `Nistroy/minecraft-ia` + `Nistroy/minecraft-ia-kb` ; `IA.md` retiré du dépôt serveur (PR #12)
- [x] 2 cerveau + CLI (`serve`, `ask`, `extract`, `kb index`, `eval`), pytest + CI verts
- [x] 3-4 mod serveur + client (1 jar), JUnit + CI verts ; jamais lancé en jeu
- [x] extraction réelle, 104 jars du serveur : 7 703 noms, 4 290 recettes
- [x] 1 fiches : 1 par mod de contenu installé, agents + relecture par échantillon (dépôt kb, branche `docs/fiches-mods`)
- [ ] clé Gemini (`~/.config/minecraft-ia/gemini-key`) + RPD réel lu dans AI Studio → `questions_per_player_per_day`, `llm_calls_per_day`
- [ ] jeu de questions test : `minecraft-ia-kb/eval/questions.toml` (6 amorces) + vraies questions des potes ; `eval` = 0 invention
- [ ] release `v0.1.0` (tag → workflow release), test en jeu, puis installation serveur (garde-fous du dépôt serveur :
  backup, redémarrage demandé) + ajout au pack packwiz (mod client = impact joueurs)
- [ ] cerveau au démarrage (launchd) + sauvegarde `brain.sqlite3`

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
