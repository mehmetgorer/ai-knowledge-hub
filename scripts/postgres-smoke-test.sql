-- Local PostgreSQL + pgvector smoke test (development)
\set ON_ERROR_STOP on

\echo '== connectivity =='
SELECT current_database() AS database, current_user AS user;

\echo '== PostgreSQL version =='
SELECT version();

\echo '== pgvector in available extensions =='
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name = 'vector';

\echo '== enable vector extension =='
CREATE EXTENSION IF NOT EXISTS vector;

\echo '== vector extension installed =='
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';

\echo '== smoke test complete =='
