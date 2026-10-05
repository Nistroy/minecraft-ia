-- Fichiers texte des jars (data/, fabric.mod.json) + configs du serveur : regénérables, jamais commités.
-- Plusieurs origines peuvent fournir le même chemin (datapack surchargé) : on les garde toutes.
CREATE TABLE game_file (
    origin  TEXT NOT NULL,                  -- id du mod, `minecraft` ou `config`
    path    TEXT NOT NULL,
    content TEXT NOT NULL,
    PRIMARY KEY (path, origin)
) STRICT;

CREATE TABLE installed_mod (
    id      TEXT PRIMARY KEY,               -- jars de premier niveau de mods_dir
    version TEXT
) STRICT;
