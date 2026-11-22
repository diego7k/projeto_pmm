-- Rodar com o avnadmin depois do primeiro load.py.

GRANT USAGE ON SCHEMA painel TO painel_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA painel TO painel_leitura;
ALTER DEFAULT PRIVILEGES FOR ROLE avnadmin IN SCHEMA painel GRANT SELECT ON TABLES TO painel_leitura;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Fase 3: o dashboard conecta com este usuário. Mesmo que o app tivesse uma falha,
-- as transações dele são só de leitura e nenhuma consulta passa de 15 s.
ALTER ROLE painel_leitura SET default_transaction_read_only = on;
ALTER ROLE painel_leitura SET statement_timeout = '15s';
