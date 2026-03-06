# DB: PlaqueTracker migrations

This folder contains the initial SQL schema for PlaqueTracker. Recommended steps to apply locally (Postgres):

1. Ensure Postgres is running and extensions for UUID are available (e.g., `pgcrypto` for `gen_random_uuid()` or `uuid-ossp` for `uuid_generate_v4()`).

2. From a shell:

```bash
psql -h <host> -U <user> -d <db> -f db/schema.sql
```

3. Adjust indexes, partitions, and retention policies as you scale. Use a migration tool (Flyway, Liquibase, or Alembic) for production workflows.
