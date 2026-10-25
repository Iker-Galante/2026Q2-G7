-- 001 · esquema inicial del pre-MVP
-- Se aplica con: python tools/migrar.py   (o psql "$DATABASE_URL" -f migraciones/001_inicial.sql)

create table if not exists migracion_aplicada (
  nombre    text primary key,
  aplicada  timestamptz not null default now()
);

create table modelo (
  id                 uuid primary key default gen_random_uuid(),
  nombre             text not null,
  version            text not null,
  tipo_estudio       text not null,
  tarea              text not null,
  etiquetas          jsonb not null,
  s3_prefix          text not null,            -- modelos/<nombre>/<version>/
  contrato           jsonb not null,           -- copia de modelo.json al publicar
  -- evaluación: la escribe eval-1
  estado_evaluacion  text not null check (estado_evaluacion in ('pendiente','en_curso','ok','error')),
  accuracy           numeric(5,4),
  metricas           jsonb,
  conjunto           text,
  conjunto_version   text,
  manifiesto         jsonb,
  evaluador_id       text,
  evaluado_en        timestamptz,
  error              text,
  creado             timestamptz not null default now(),
  publicado          timestamptz not null default now(),
  unique (nombre, version)
);
create index modelo_pendientes on modelo (estado_evaluacion, publicado);

create table estudio (
  id            uuid primary key default gen_random_uuid(),
  tipo_estudio  text not null,
  s3_key        text not null,
  content_type  text not null,
  tamano_bytes  bigint,
  estado        text not null check (estado in ('pendiente_subida','subido')),
  creado        timestamptz not null default now()
);

-- La "cola": tal cual la §12 de la guía, más duracion_ms y error.
create table trabajo (
  id            uuid primary key default gen_random_uuid(),
  estudio_id    uuid not null references estudio(id),
  modelo_id     uuid not null references modelo(id),
  estado        text not null check (estado in ('pendiente','en_curso','ok','error')),
  intentos      int  not null default 0,
  worker_id     text,
  resultado     jsonb,
  duracion_ms   int,
  error         text,
  creado        timestamptz not null default now(),
  actualizado   timestamptz not null default now()
);
create index trabajo_pendientes on trabajo (estado, actualizado);
