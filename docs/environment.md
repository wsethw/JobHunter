# Environment

Configuration is loaded through `pydantic-settings`.

Important variables:

- `DATABASE_URL`
- `REDIS_URL`
- `SOURCES`
- `MUST_HAVE_STACK`
- `NICE_TO_HAVE_STACK`
- `NEGATIVE_KEYWORDS`
- `REMOTE_ONLY`
- `MIN_SCORE_TO_NOTIFY`
- `ENABLE_TELEGRAM`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ENABLE_EMAIL`
- `FLOWER_BASIC_AUTH`

Run `python -m app.cli validate-config` to print a redacted configuration snapshot.
