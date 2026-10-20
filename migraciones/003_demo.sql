-- Outbox y presupuesto persistente de reintentos para la demo automática.
create table demo_inicializacion (
    clave text primary key,
    mensaje jsonb not null,
    intentos integer not null default 0,
    enviado timestamptz,
    error boolean not null default false
);
