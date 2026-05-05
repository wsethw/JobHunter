class JobHunterError(Exception):
    """Base exception for JobHunter failures."""


class ScraperError(JobHunterError):
    """Raised when a scraper fails in a controlled way."""


class NotificationError(JobHunterError):
    """Raised when notification delivery fails."""


class NotificationConfigError(NotificationError):
    """Raised when a notification channel is not configured correctly."""


class ConfigurationError(JobHunterError):
    """Raised when runtime configuration is invalid."""


class PersistenceError(JobHunterError):
    """Raised when database persistence fails."""
