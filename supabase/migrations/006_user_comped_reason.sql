-- Per-user comp reason, matching school_settings.
alter table romalume.user_settings add column if not exists comped_reason text;
