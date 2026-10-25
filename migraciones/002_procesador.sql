-- 002 · Entrega 3: el procesador escribe los resultados que llegan por la cola `resultados`.
-- `actualizado` en modelo es lo que usa para vencer una evaluación en_curso sin noticias.

alter table modelo add column if not exists actualizado timestamptz not null default now();
create index if not exists modelo_en_curso on modelo (estado_evaluacion, actualizado);
