# JobHunter Bot

JobHunter Bot é um robô diário de coleta, pontuação, persistência e alerta de vagas para desenvolvedores back-end com foco em Python. Ele usa Celery Beat para agendamento, Celery Worker para execução assíncrona, Playwright para fontes HTML dinâmicas, GitHub REST API para o repositório `backend-br/vagas`, PostgreSQL para armazenamento e Telegram para o resumo matinal.

## Por Que Celery

Um cron job simples executa comandos em horários definidos, mas não entrega bem garantias operacionais para um pipeline real. Com Celery, o projeto ganha fila, retry controlado, separação entre agendador e worker, backend de resultados, monitoramento via Flower e possibilidade de escalar workers sem reescrever a arquitetura.

Celery Beat fica responsável por disparar a tarefa diária às 08:00, enquanto o worker executa `fetch_and_process_jobs`. Se a coleta ficar lenta, se houver mais fontes ou se o volume crescer, basta adicionar mais workers ou filas especializadas.

## Por Que Playwright

Algumas páginas de vagas renderizam conteúdo via JavaScript, mudam DOM após carregamento inicial ou aplicam proteções simples contra clientes HTTP crus. `requests` e BeautifulSoup continuam excelentes para APIs e HTML estático, mas Playwright permite carregar a página como um navegador real, com User-Agent configurado, timeout, contexto isolado e execução headless.

Neste projeto, GitHub Issues usa REST API porque é mais estável e simples. ProgramaThor e LinkedIn usam Playwright de forma defensiva. O LinkedIn pode bloquear ou alterar seletores com frequência; por isso, falhas nele são registradas e não interrompem o pipeline.

## Como Funciona A Pontuação

A função `score_job(job, desired_stack, desired_seniority)` calcula uma nota de 0 a 100. Tecnologias no título têm peso maior, tecnologias na lista `stack` têm peso intermediário e menções na descrição têm peso menor. Depois, a senioridade ajusta o resultado: uma vaga junior recebe nota zero quando a busca deseja senioridade senior, enquanto vagas sem senioridade clara recebem uma penalização moderada.

Para adaptar a outra stack, altere `DESIRED_STACK` no `.env`, por exemplo:

```env
DESIRED_STACK=Python,FastAPI,Kubernetes,GCP,PostgreSQL,Redis
DESIRED_SENIORITY=pleno
```

## Arquitetura

```text
jobhunter/
├── app/
│   ├── __init__.py
│   ├── celery_app.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── linkedin.py
│   │   ├── programathor.py
│   │   └── github_backendbr.py
│   ├── scoring.py
│   ├── deduplicator.py
│   ├── notifier.py
│   └── tasks.py
├── scripts/
│   └── init_db.sql
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Configuração

Crie seu arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

No Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edite pelo menos estas variáveis:

```env
TELEGRAM_BOT_TOKEN=123456:token_do_bot
TELEGRAM_CHAT_ID=123456789
DESIRED_STACK=Python,Django,FastAPI,PostgreSQL,Docker,AWS,Celery,Redis,SQLAlchemy
DESIRED_SENIORITY=senior
```

As variáveis sensíveis nunca ficam no código. PostgreSQL, Redis, Telegram, e-mail e preferências de scraping são lidos com `pydantic-settings`.

## Como Criar O Bot Do Telegram

1. Abra o Telegram e converse com `@BotFather`.
2. Envie `/newbot`, escolha nome e username.
3. Copie o token gerado para `TELEGRAM_BOT_TOKEN`.
4. Envie uma mensagem qualquer para seu bot.
5. Acesse no navegador:

```text
https://api.telegram.org/botSEU_TOKEN/getUpdates
```

6. Procure `chat.id` no JSON e coloque em `TELEGRAM_CHAT_ID`.

Para grupos, adicione o bot ao grupo, envie uma mensagem e repita o `getUpdates`.

## Subindo O Ambiente

```bash
docker compose up --build
```

Serviços criados:

- `postgres`: PostgreSQL 16 com `scripts/init_db.sql` executado na primeira inicialização.
- `redis`: broker e backend do Celery.
- `worker`: executa tarefas Celery.
- `beat`: agenda a execução diária.
- `flower`: painel de monitoramento em `http://localhost:5555`.

## Execução Manual

Com os containers de pé:

```bash
docker compose exec worker celery -A app.celery_app call app.tasks.fetch_and_process_jobs
```

Para acompanhar o worker:

```bash
docker compose logs -f worker
```

Para ver o Beat:

```bash
docker compose logs -f beat
```

## Consultando O Banco

Abra o `psql` dentro do container:

```bash
docker compose exec postgres psql -U jobhunter -d jobhunter
```

Consultas úteis:

```sql
SELECT id, title, company, source, seniority, score, created_at
FROM jobs
ORDER BY created_at DESC
LIMIT 20;

SELECT *
FROM execution_logs
ORDER BY started_at DESC
LIMIT 10;
```

## Logs

Os logs saem no console e no arquivo `logs/jobhunter.log`, com rotação diária e retenção de 14 arquivos.

```bash
docker compose logs -f worker
docker compose exec worker tail -f logs/jobhunter.log
```

Cada etapa registra eventos: início da execução, scraper por fonte, falhas isoladas, deduplicação, scoring, inserção no banco e envio de notificação.

## Deduplicação

A deduplicação é estrita por `link`, que também é `UNIQUE` no PostgreSQL. O pipeline compara links já salvos nos últimos 7 dias para cumprir a regra de negócio e também verifica duplicatas históricas para evitar colisão com a restrição única.

Também há deduplicação dentro do lote atual. Se duas fontes retornarem a mesma URL canônica, apenas uma será persistida.

## Fontes Implementadas

- GitHub Issues do `backend-br/vagas`, via REST API.
- ProgramaThor, via Playwright no endpoint público `/jobs`.
- LinkedIn Jobs, via Playwright em busca pública por `JOB_SEARCH_QUERY` e `JOB_SEARCH_LOCATION`.

O scraper do LinkedIn é propositalmente defensivo: se houver bloqueio, captcha, mudança de seletor ou timeout, o erro é logado e as demais fontes continuam.

## E-mail Opcional

Ative com:

```env
ENABLE_EMAIL=true
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USERNAME=seu_email@gmail.com
EMAIL_PASSWORD=sua_senha_de_app
EMAIL_FROM=seu_email@gmail.com
EMAIL_TO=destino@gmail.com
```

## Robots.txt E Compliance

Para produção real, implemente uma checagem por fonte usando `urllib.robotparser.RobotFileParser` antes de acessar URLs HTML e respeite limites de taxa por domínio. Também revise termos de uso das plataformas. Este projeto já isola falhas por scraper, limita páginas, usa timeout de 30 segundos e permite desligar fontes via `SOURCES`.

Exemplo para desligar LinkedIn:

```env
SOURCES=github_backendbr,programathor
```

## Troubleshooting

Se o worker não conseguir abrir Chromium:

```bash
docker compose build --no-cache worker beat flower
```

Se quiser recriar o banco do zero:

```bash
docker compose down -v
docker compose up --build
```

Se o Telegram não enviar mensagem, confira token, chat id e se você enviou pelo menos uma mensagem ao bot antes de chamar `getUpdates`.
