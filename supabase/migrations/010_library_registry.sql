-- School library registry columns for the indexer (2026-09-20).
-- One row per indexed source file; the chunks live in the school's Qdrant
-- collection with the same audience tag in point metadata.
alter table romalume.library_documents
  add column if not exists source_path text,
  add column if not exists source_system text,
  add column if not exists kind text,
  add column if not exists url text,
  add column if not exists last_modified date,
  add column if not exists content_hash text,
  add column if not exists text_chars integer,
  add column if not exists indexed_at timestamptz,
  add column if not exists error text;
create unique index if not exists library_client_source_path
  on romalume.library_documents(client_id, source_path) where source_path is not null;
