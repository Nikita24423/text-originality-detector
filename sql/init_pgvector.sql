-- Дополнение pgvector (запускается ПОСЛЕ init_core.sql автоматически из Python)
-- В pgAdmin вручную используйте sql/init_all.sql

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE corpus_chunks
    ADD COLUMN IF NOT EXISTS embedding vector(1024);

ALTER TABLE corpus_chunks
    ADD COLUMN IF NOT EXISTS rubert_embedding vector(312);
