#!/bin/sh
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE oficina_os_homolog;
    CREATE USER oficina_os_user WITH ENCRYPTED PASSWORD 'oficina_os_pass';
    REVOKE CONNECT ON DATABASE oficina_os_homolog FROM PUBLIC;
    GRANT CONNECT ON DATABASE oficina_os_homolog TO oficina_os_user;

    CREATE DATABASE oficina_billing_homolog;
    CREATE USER oficina_billing_user WITH ENCRYPTED PASSWORD 'oficina_billing_pass';
    REVOKE CONNECT ON DATABASE oficina_billing_homolog FROM PUBLIC;
    GRANT CONNECT ON DATABASE oficina_billing_homolog TO oficina_billing_user;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "oficina_os_homolog" <<-EOSQL
    GRANT ALL ON SCHEMA public TO oficina_os_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO oficina_os_user;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "oficina_billing_homolog" <<-EOSQL
    GRANT ALL ON SCHEMA public TO oficina_billing_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO oficina_billing_user;
EOSQL
