# Scraping

Each source implements `BaseScraper.scrape()` and returns normalized `Job` objects.

Guidelines for a new scraper:

1. Add a class in `app/scrapers`.
2. Keep fetch and parse logic separate.
3. Save HTML/screenshot artifacts on failures with `save_artifact`.
4. Never let one source stop the entire pipeline.
5. Add fixtures and parser tests without hitting the network.

Playwright tracing can be enabled with:

```env
ENABLE_PLAYWRIGHT_TRACING=true
```

For production compliance, set `RESPECT_ROBOTS_TXT=true` and review each site's terms.
