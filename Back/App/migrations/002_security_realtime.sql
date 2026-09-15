-- Apply this migration to an existing Supabase project after schema.sql.
alter table venues enable row level security;
alter table admin_users enable row level security;
alter table venue_tables enable row level security;
alter table sessions enable row level security;
alter table tracks enable row level security;
alter table blocked_tracks enable row level security;
alter table blocked_artists enable row level security;
alter table music_provider_connections enable row level security;
alter table queue_items enable row level security;
alter table votes enable row level security;
alter table venue_settings enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_publication_rel pr
    join pg_class c on c.oid = pr.prrelid
    join pg_publication p on p.oid = pr.prpubid
    where p.pubname = 'supabase_realtime' and c.relname = 'queue_items'
  ) then
    alter publication supabase_realtime add table queue_items;
  end if;
end $$;
