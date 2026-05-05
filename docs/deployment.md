# Deployment

Local deployment:

```bash
cp .env.example .env
docker compose up --build
```

The `migration` service runs `alembic upgrade head` before `worker`, `beat` and `api` start. PostgreSQL and Redis healthchecks gate dependent services.

For VPS production usage:

- keep `.env` outside version control;
- use strong database passwords;
- keep Redis and Postgres private;
- configure `FLOWER_BASIC_AUTH`;
- run behind a reverse proxy with TLS.
