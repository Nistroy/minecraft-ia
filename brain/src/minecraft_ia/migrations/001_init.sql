-- Historique + votes : privés, sauvegardés, jamais commités.
CREATE TABLE question (
    id          INTEGER PRIMARY KEY,
    player      TEXT NOT NULL,              -- UUID Minecraft
    player_name TEXT NOT NULL,
    text        TEXT NOT NULL,
    asked_at    TEXT NOT NULL,              -- ISO 8601 UTC
    day         TEXT NOT NULL               -- jour du quota (minuit heure du Pacifique, comme Google)
) STRICT;
CREATE INDEX question_player_day ON question (player, day);

CREATE TABLE answer (
    id          INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES question (id),
    text        TEXT NOT NULL,
    sources     TEXT NOT NULL,              -- liste JSON
    notes       TEXT NOT NULL,              -- liste JSON des notes utilisées (pour les votes)
    status      TEXT NOT NULL CHECK (status IN ('ok', 'unknown', 'error')),
    llm_calls   INTEGER NOT NULL,
    retry_of    INTEGER REFERENCES answer (id),
    answered_at TEXT NOT NULL
) STRICT;
CREATE INDEX answer_question ON answer (question_id);

CREATE TABLE vote (
    answer_id INTEGER NOT NULL REFERENCES answer (id),
    player    TEXT NOT NULL,
    up        INTEGER NOT NULL CHECK (up IN (0, 1)),
    voted_at  TEXT NOT NULL,
    PRIMARY KEY (answer_id, player)
) STRICT;

CREATE TABLE llm_usage (
    day   TEXT PRIMARY KEY,
    calls INTEGER NOT NULL
) STRICT;

-- Données exactes extraites des jars : regénérables.
CREATE TABLE item (
    id      TEXT NOT NULL,                  -- ns:id
    kind    TEXT NOT NULL CHECK (kind IN ('item', 'block', 'entity')),
    mod     TEXT NOT NULL,
    name_en TEXT,
    name_fr TEXT,
    PRIMARY KEY (id, kind)
) STRICT;

CREATE TABLE recipe (
    id     TEXT PRIMARY KEY,
    mod    TEXT NOT NULL,
    type   TEXT NOT NULL,
    result TEXT,
    json   TEXT NOT NULL
) STRICT;
CREATE INDEX recipe_result ON recipe (result);

CREATE TABLE recipe_input (
    recipe_id TEXT NOT NULL REFERENCES recipe (id) ON DELETE CASCADE,
    input     TEXT NOT NULL,                -- ns:id ou #tag
    PRIMARY KEY (recipe_id, input)
) STRICT;
CREATE INDEX recipe_input_input ON recipe_input (input);

CREATE VIRTUAL TABLE item_fts USING fts5 (
    id, kind UNINDEXED, name_en, name_fr,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- Index de recherche des fiches + notes : jetable, reconstruit depuis le dépôt de connaissances.
CREATE VIRTUAL TABLE kb_fts USING fts5 (
    path UNINDEXED, slug, kind UNINDEXED, title, body,
    tokenize = 'unicode61 remove_diacritics 2'
);
