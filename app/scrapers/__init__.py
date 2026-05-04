"""Scraper implementations for JobHunter Bot."""

import logging

from app.scrapers.base import BaseScraper, Job
from app.scrapers.github_backendbr import GitHubBackendBRScraper
from app.scrapers.linkedin import LinkedInScraper
from app.scrapers.programathor import ProgramathorScraper

logger = logging.getLogger(__name__)

__all__ = [
    "BaseScraper",
    "Job",
    "GitHubBackendBRScraper",
    "LinkedInScraper",
    "ProgramathorScraper",
]
