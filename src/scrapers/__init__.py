from .rss import RssScraper
from .web import HfPapersScraper, GitHubTrendingScraper

SCRAPERS = {
    "rss": RssScraper,
    "youtube": RssScraper,  # YouTube RSS feeds work the same way
    "web_hf_papers": HfPapersScraper,
    "web_github_trending": GitHubTrendingScraper,
}
