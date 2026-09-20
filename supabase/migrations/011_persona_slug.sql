-- Which Ask persona answers for this school (mailbox slug in the Ask system).
alter table romalume.school_settings add column if not exists persona_slug text;
update romalume.school_settings set persona_slug = 'iris' where slug = 'cfa' and persona_slug is null;
