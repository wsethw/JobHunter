# JobHunter Bot

[![CI](https://github.com/your-user/jobhunter-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/your-user/jobhunter-bot/actions/workflows/ci.yml)

JobHunter Bot é um sistema de coleta, pontuação, persistência e alerta de vagas back-end Python. Ele combina Celery, Redis, PostgreSQL, Alembic, SQLAlchemy, Playwright, Pydantic Settings, Telegram/e-mail, CLI, API FastAPI e uma suíte automatizada de testes.

## Visão Geral

O Celery Beat dispara a tarefa diária às 08:00. O worker chama `PipelineService`, que executa scrapers reais, normaliza vagas, gera fingerprint/hash, calcula score explicável, persiste com upsert real no PostgreSQL e envia um relatório com as melhores vagas.

```mermaid
flowchart LR
    Beat["Celery Beat"] --> Worker["Celery Worker"]
    Worker --> Pipeline["PipelineService"]
    Pipeline --> Scrapers["ScrapingService"]
    Pipeline --> Scoring["ScoringService"]
    Pipeline --> DB["Repositories + PostgreSQL"]
    Pipeline --> Notify["Telegram/E-mail"]
    API["FastAPI"] --> DB
```

## Por Que Celery

Celery traz fila, retry, backend de resultados, monitoramento com Flower e escala horizontal. Um cron job simples dispara comandos, mas não oferece a mesma separação entre agendamento, execução, auditoria e reprocessamento.

## Por Que Playwright

GitHub Issues usa API REST. ProgramaThor e LinkedIn podem depender de HTML dinâmico, por isso usam Playwright em modo headless. O LinkedIn pode bloquear automações; por isso ele é defensivo, pode ser removido de `SOURCES` e salva artefatos em `logs/artifacts/` quando falha.

## Scoring Explicável

O scoring considera:

- tecnologias obrigatórias em `MUST_HAVE_STACK`;
- tecnologias desejáveis em `NICE_TO_HAVE_STACK`;
- senioridade;
- remoto/localização;
- salário informado;
- palavras negativas;
- stack no título, tags e descrição.

O banco guarda `score_reasons`, por exemplo:

```txt
Score: 86.50
Motivos:
- encontrou Python, FastAPI e PostgreSQL
- senioridade compatível: senior
- vaga remota
- penalidade: salário não informado
```

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

No PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Serviços:

- `postgres`: PostgreSQL 16.
- `redis`: broker/backend Celery.
- `migration`: executa `alembic upgrade head`.
- `worker`: executa tarefas.
- `beat`: agenda execução diária.
- `flower`: `http://localhost:5555`.
- `api`: `http://localhost:8000`.

## Comandos

```bash
make install
make test
make test-cov
make lint
make format
make typecheck
make audit
make quality
make up
make down
make logs
make db
make run-task
```

Execução manual via Celery:

```bash
docker compose exec worker celery -A app.celery_app call app.tasks.fetch_and_process_jobs
```

Execução via CLI:

```bash
python -m app.cli validate-config
python -m app.cli run-once --dry-run
python -m app.cli run-once
python -m app.cli list-jobs
python -m app.cli test-notification
python -m app.cli export --format csv
python -m app.cli export --format json
python -m app.cli export --format markdown
```

## Variáveis De Ambiente

Principais:

```env
DATABASE_URL=postgresql+psycopg://jobhunter:jobhunter@postgres:5432/jobhunter
REDIS_URL=redis://redis:6379/0
SOURCES=github_backendbr,programathor,linkedin
MUST_HAVE_STACK=Python,PostgreSQL
NICE_TO_HAVE_STACK=FastAPI,Docker,AWS,Redis,Celery
NEGATIVE_KEYWORDS=estágio,frontend only,presencial obrigatório
PREFERRED_LOCATION=remote,brazil
REMOTE_ONLY=false
MIN_SCORE_TO_NOTIFY=50
```

Telegram:

```env
ENABLE_TELEGRAM=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

E-mail:

```env
ENABLE_EMAIL=true
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USERNAME=
EMAIL_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
```

## Telegram

1. Converse com `@BotFather`.
2. Use `/newbot`.
3. Copie o token para `TELEGRAM_BOT_TOKEN`.
4. Envie uma mensagem ao bot.
5. Abra `https://api.telegram.org/botSEU_TOKEN/getUpdates`.
6. Copie `chat.id` para `TELEGRAM_CHAT_ID`.

## Banco E Migrations

O schema é versionado com Alembic:

```bash
alembic upgrade head
```

Consultar:

```bash
docker compose exec postgres psql -U jobhunter -d jobhunter
```

```sql
SELECT id, title, company, score, seen_count, last_seen_at
FROM jobs
ORDER BY last_seen_at DESC
LIMIT 20;
```

## API

Endpoints:

- `GET /health`
- `GET /jobs`
- `GET /jobs/top`
- `GET /jobs/{id}`
- `GET /executions`
- `GET /metrics/summary`

Exemplo:

```bash
curl http://localhost:8000/jobs/top
```

## Testes E Qualidade

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
ruff format --check .
mypy app tests
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
pip-audit -r requirements.txt
```

Os scrapers são testados com fixtures HTML/JSON, sem internet real.

## Adicionando Nova Fonte

1. Crie `app/scrapers/minha_fonte.py`.
2. Herde `BaseScraper`.
3. Separe coleta e parsing.
4. Retorne `Job`.
5. Registre em `SCRAPER_REGISTRY`.
6. Adicione fixture e testes.
7. Inclua a fonte em `SOURCES`.

## Segurança

- `.env` não é versionado.
- Configuração redige secrets em `validate-config`.
- Flower usa `FLOWER_BASIC_AUTH`.
- `pip-audit` e pre-commit estão configurados.
- Não exponha Postgres/Redis em produção.

Veja [SECURITY.md](SECURITY.md).

## Documentação

- [Arquitetura](docs/architecture.md)
- [Testes](docs/testing.md)
- [Scraping](docs/scraping.md)
- [Deployment](docs/deployment.md)
- [Ambiente](docs/environment.md)
- [Roadmap](docs/roadmap.md)

## Limitações Conhecidas

- LinkedIn pode bloquear automações e mudar seletores.
- Robots.txt é configurável, mas a política por domínio ainda está no roadmap.
- O dashboard atual é API; uma UI web visual pode ser adicionada sobre FastAPI.
