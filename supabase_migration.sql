-- Executar no Supabase SQL Editor
-- https://app.supabase.com → seu projeto → SQL Editor

create table if not exists clientes (
  id          text primary key,
  nome        text not null,
  dados       jsonb not null,
  criado_em   text not null
);

-- Desabilita RLS (acesso controlado pela service_role key no backend)
alter table clientes disable row level security;

-- Clientes existentes (migração)
insert into clientes (id, nome, dados, criado_em) values
  ('27c7ec5a380e', 'Fazenda Sao Jose - Carlos',
   '{"pulverizador":{"modelo":"Jacto Uniport 3030","volume_tanque_L":3000.0},"vazao_L_ha":100.0,"area_tanque_ha":30.0,"pontas":["TT110015","AIXR110015"],"calibracao":"","observacao":"Colocar 500L de agua antes de adicionar produtos. Tanque pre-mistura 50L."}',
   '2026-10-13'),
  ('51d7b686c461', 'Fazenda Santa Clara - Joao',
   '{"pulverizador":{"modelo":"Jacto Uniport 2000","volume_tanque_L":2000.0},"vazao_L_ha":100.0,"area_tanque_ha":20.0,"pontas":["TT110015","AIXR110015","Leque HI 35"],"calibracao":"","observacao":""}',
   '2026-10-16')
on conflict (id) do nothing;
