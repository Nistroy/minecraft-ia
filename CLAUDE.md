# minecraft-ia — instructions agents

Assistant IA en jeu pour serveur Fabric 1.21.1 : 1 mod Java (client + serveur) + cerveau Python local. Public, GPL-3.0.
Plan, décisions, état : `PLAN.md` (lire avant d'agir). Docs `.md` = notes denses pour agents (fragments, pas de prose),
sauf `README.md` (humains).

## Carte
- `brain/src/minecraft_ia/` — `db.py` seul accès SQLite (migrations `migrations/NNN_*.sql`) · `llm.py` seul accès LLM ·
  `kb.py` fiches/notes + commits git · `tools.py` outils du LLM · `assistant.py` quotas + boucle + contrôle sources ·
  `server.py` HTTP local · `extract.py` jars → données exactes · `evaluation.py` · `cli.py`.
- `mod/` — Loom split source sets, mappings Mojang : `src/main` commun + serveur (`Gateway`, `/ia`, payloads) ·
  `src/client` touche + écran · `src/test` JUnit (classes sans MC ou `FriendlyByteBuf` seul).
- Connaissances d'un modpack : dépôt séparé (config `kb_path`), jamais ici.

## Tests — TDD obligatoire
- Red-Green-Refactor : pas de comportement sans test rouge d'abord ; bug → test de régression d'abord.
- Cerveau : `cd brain && .venv/bin/ruff format --check src tests && .venv/bin/ruff check src tests && .venv/bin/pytest`
- Mod : `cd mod && JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home ./gradlew build`
- Fini = les deux verts. Jamais affaiblir/supprimer/skip un test pour passer au vert : le dire, demander.
- CI `.github/workflows/ci.yml` : mêmes commandes sur chaque PR ; PR rouge jamais mergée.

## Règles
- Langue : identifiants EN ; docs, commentaires, messages joueurs FR ; commits/branches Conventional Commits EN.
- Git : jamais commit sur `main` ; branche `<type>/<sujet>` ; PR + merge via `gh`.
- Anti-invention : versions/API vérifiées (docs officielles, SDK installé, `javap` sur jars Loom `mod/.gradle/loom-cache`).
  Modrinth/GitHub → `curl` (Python `urllib` SSL cassé sur le Mac de nistroy).
- Sécurité : clé Gemini + jeton cerveau hors dépôt (`~/.config/minecraft-ia/`), jamais lus ni affichés (`test -s`) ;
  cerveau `127.0.0.1` seulement ; texte joueur jamais shell/console ; données extraites des jars et historique
  jamais commités.
- Release mod : tag `vX.Y.Z` → workflow release → jar attaché ; le pack du serveur pointe l'URL de release.
