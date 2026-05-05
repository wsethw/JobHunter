# Testing

Install dev dependencies:

```bash
make install
```

Run:

```bash
make test
make test-cov
make quality
```

The suite includes unit tests for scoring, configuration, parsers, scrapers, deduplication and notification delivery with mocks. Integration tests exercise repositories and the pipeline using isolated SQLAlchemy sessions.
