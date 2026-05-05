# Security Policy

## Secrets

Never commit `.env`, Telegram tokens, SMTP passwords, database passwords, private keys or production URLs with credentials. The application redacts known secret fields when printing configuration and `.gitignore` excludes `.env`.

## Supported Checks

Run:

```bash
make audit
pre-commit run --all-files
```

The pre-commit configuration includes `detect-private-key`, YAML/TOML checks, whitespace cleanup and Ruff.

## Production Notes

- Keep Flower behind authentication with `FLOWER_BASIC_AUTH`.
- Do not expose PostgreSQL or Redis publicly.
- Use a dedicated Telegram bot token with minimal scope.
- Rotate SMTP application passwords periodically.
- Review target site terms and robots.txt before enabling scraping in production.

## Reporting

For portfolio use, open a private issue or contact the maintainer directly before publishing sensitive findings.
