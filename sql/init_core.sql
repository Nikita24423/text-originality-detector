-- Базовая схема (работает без pgvector)

CREATE TABLE IF NOT EXISTS tasks (
    id              BIGSERIAL PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    priority        INT NOT NULL DEFAULT 1,
    mode            TEXT NOT NULL DEFAULT 'corpus',
    filename        TEXT,
    payload         JSONB NOT NULL DEFAULT '{}',
    progress        TEXT DEFAULT '',
    error_message   TEXT,
    plagiarism_pct  REAL,
    copy_pct        REAL,
    deep_borrow_pct REAL,
    ai_pct          REAL,
    result_json     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS corpus_sources (
    id          BIGSERIAL PRIMARY KEY,
    label       TEXT NOT NULL,
    filename    TEXT,
    content     TEXT NOT NULL,
    chunk_count INT NOT NULL DEFAULT 0,
    indexed_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corpus_chunks (
    id              BIGSERIAL PRIMARY KEY,
    source_id       BIGINT NOT NULL REFERENCES corpus_sources(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    embedding_json  JSONB,
    qdrant_point_id UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_corpus_chunks_source
    ON corpus_chunks (source_id);
