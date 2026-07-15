-- ============================================================
-- Схема основной платформы (ERD: institutions → documents → plagiarism_matches)
-- Выполнить на базе nikita2 ПОСЛЕ init_core.sql (или через init_platform_all.sql)
-- ============================================================

CREATE TABLE IF NOT EXISTS institutions (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS faculties (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    institution_id  TEXT NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    username                TEXT PRIMARY KEY,
    password                TEXT NOT NULL,
    role                    TEXT NOT NULL DEFAULT 'student',
    email                   TEXT,
    full_name               TEXT,
    additional_roles_json   TEXT,
    faculty_id              TEXT REFERENCES faculties(id) ON DELETE SET NULL,
    institution_id          TEXT REFERENCES institutions(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login              TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS document_types (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description  TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id                      SERIAL PRIMARY KEY,
    title                   TEXT NOT NULL,
    filename                TEXT,
    file_path               TEXT,
    content                 TEXT NOT NULL,
    word_count              INTEGER,
    upload_date             TIMESTAMPTZ NOT NULL DEFAULT now(),
    category                TEXT,
    status                  TEXT NOT NULL DEFAULT 'uploaded',
    file_format             TEXT,
    user_id                 TEXT REFERENCES users(username) ON DELETE SET NULL,
    minhash_signature_json  TEXT,
    shingle_count           INTEGER,
    originality_percent     DOUBLE PRECISION,
    plagiarism_percent_ml   DOUBLE PRECISION,
    ai_percent_ml           DOUBLE PRECISION,
    copy_percent_ml         DOUBLE PRECISION,
    deep_borrow_percent_ml  DOUBLE PRECISION,
    processing_time_ms      INTEGER,
    analytics_status        TEXT NOT NULL DEFAULT 'pending',
    analytics_error         TEXT,
    analytics_updated_at    TIMESTAMPTZ,
    document_type_id        INTEGER REFERENCES document_types(id) ON DELETE SET NULL,
    faculty_id              TEXT REFERENCES faculties(id) ON DELETE SET NULL,
    institution_id          TEXT REFERENCES institutions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_analytics ON documents(analytics_status);

CREATE TABLE IF NOT EXISTS plagiarism_matches (
    id                  SERIAL PRIMARY KEY,
    source_document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    target_document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    similarity_percent  DOUBLE PRECISION NOT NULL,
    copy_percent        DOUBLE PRECISION,
    deep_borrow_percent DOUBLE PRECISION,
    matched_fragments   TEXT,
    algorithm           TEXT NOT NULL DEFAULT 'bge-m3+reranker+tfidf-bm25',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_plagiarism_pair UNIQUE (source_document_id, target_document_id)
);

CREATE INDEX IF NOT EXISTS idx_plagiarism_source ON plagiarism_matches(source_document_id);
CREATE INDEX IF NOT EXISTS idx_plagiarism_target ON plagiarism_matches(target_document_id);

CREATE TABLE IF NOT EXISTS reports (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    generated_by_id TEXT REFERENCES users(username) ON DELETE SET NULL,
    file_path       TEXT,
    access_token    TEXT,
    download_count  INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT REFERENCES users(username) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    details     TEXT,
    ip_address  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO institutions (id, name)
VALUES ('inst-demo', 'Демо университет')
ON CONFLICT (id) DO NOTHING;

INSERT INTO faculties (id, name, institution_id)
VALUES ('fac-demo', 'Факультет информатики', 'inst-demo')
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (username, password, role, full_name, faculty_id, institution_id)
VALUES ('demo', 'demo', 'admin', 'Демо пользователь', 'fac-demo', 'inst-demo')
ON CONFLICT (username) DO NOTHING;

INSERT INTO document_types (name, display_name, description)
VALUES ('coursework', 'Курсовая работа', 'Курсовая работа студента')
ON CONFLICT (name) DO NOTHING;
