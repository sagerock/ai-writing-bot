-- Thumbs up/down feedback carries structured fields, not just a body.
alter table romalume.feedback
  alter column body drop not null,
  add column if not exists message_id text,
  add column if not exists rating text,
  add column if not exists model text,
  add column if not exists routed_category text,
  add column if not exists message_snippet text;
create index if not exists feedback_created_idx on romalume.feedback(created_at desc);
