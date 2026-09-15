create extension if not exists pgcrypto;

create type session_status as enum ('ACTIVE', 'EXPIRED', 'REVOKED');
create type queue_status as enum ('PENDING', 'PLAYING', 'PLAYED', 'SKIPPED', 'REMOVED');

create table venues (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  created_at timestamptz not null default now()
);

create table admin_users (
  id uuid primary key default gen_random_uuid(),
  venue_id uuid not null references venues(id) on delete cascade,
  email text not null,
  provider_user_id text,
  created_at timestamptz not null default now(),
  unique (venue_id, email)
);

create table venue_tables (
  id uuid primary key default gen_random_uuid(),
  venue_id uuid not null references venues(id) on delete cascade,
  label text not null,
  unique (venue_id, label)
);

create table sessions (
  id uuid primary key default gen_random_uuid(),
  venue_id uuid not null references venues(id) on delete cascade,
  table_id uuid references venue_tables(id) on delete set null,
  device_hash text not null,
  created_at timestamptz not null default now(),
  last_activity timestamptz not null default now(),
  expires_at timestamptz not null,
  status session_status not null default 'ACTIVE'
);

create table tracks (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  provider_track_id text not null,
  title text not null,
  artist text not null,
  artwork_url text,
  is_explicit boolean not null default false,
  unique (provider, provider_track_id)
);

create table blocked_tracks (
  venue_id uuid not null references venues(id) on delete cascade,
  track_id uuid not null references tracks(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (venue_id, track_id)
);

create table blocked_artists (
  venue_id uuid not null references venues(id) on delete cascade,
  artist_name text not null,
  created_at timestamptz not null default now(),
  primary key (venue_id, artist_name)
);

create table music_provider_connections (
  id uuid primary key default gen_random_uuid(),
  venue_id uuid not null references venues(id) on delete cascade,
  provider text not null,
  provider_account_id text,
  access_token_encrypted text not null,
  refresh_token_encrypted text,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  unique (venue_id, provider)
);

create table queue_items (
  id uuid primary key default gen_random_uuid(),
  venue_id uuid not null references venues(id) on delete cascade,
  session_id uuid not null references sessions(id),
  track_id uuid not null references tracks(id),
  requested_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  status queue_status not null default 'PENDING',
  votes integer not null default 0 check (votes >= 0),
  score numeric not null default 0
);

create table votes (
  id uuid primary key default gen_random_uuid(),
  queue_item_id uuid not null references queue_items(id) on delete cascade,
  session_id uuid not null references sessions(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (queue_item_id, session_id)
);

create table venue_settings (
  venue_id uuid primary key references venues(id) on delete cascade,
  session_max_hours integer not null default 3,
  session_idle_minutes integer not null default 30,
  request_cooldown_minutes integer not null default 10,
  max_pending_per_session integer not null default 3,
  explicit_content_allowed boolean not null default false,
  same_artist_window integer not null default 5,
  same_artist_limit integer not null default 2
);

create index sessions_active_by_venue on sessions (venue_id, status, expires_at);
create index queue_pending_by_venue on queue_items (venue_id, status, score desc);

-- The API uses the private PostgreSQL connection and remains the authority for
-- session and queue mutations. Browser roles get no direct table access.
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

-- Supabase Realtime broadcasts queue changes; clients still read through FastAPI.
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