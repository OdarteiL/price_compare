from app.crawlers.amazon import AmazonCrawler
from app.crawlers.ebay import EbayCrawler
from app.crawlers.generic import GenericCrawler

__all__ = ["AmazonCrawler", "EbayCrawler", "GenericCrawler"]

# Registry of crawlers that support keyword search
SEARCH_CRAWLERS = [AmazonCrawler, EbayCrawler]
