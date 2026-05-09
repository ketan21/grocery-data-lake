"""Configuration — API URLs, headers, database path."""

from pathlib import Path

BASE_URL = "https://api.ah.nl"
GRAPHQL_URL = f"{BASE_URL}/graphql"

AUTH_ENDPOINT = f"{BASE_URL}/mobile-auth/v1/auth/token/anonymous"
SEARCH_ENDPOINT = f"{BASE_URL}/mobile-services/product/search/v2"
BULK_LOOKUP_ENDPOINT = f"{BASE_URL}/mobile-services/product/search/v2/products"
DETAIL_ENDPOINT = f"{BASE_URL}/mobile-services/product/detail/v4/fir/{{webshopId}}"
CATEGORIES_ENDPOINT = f"{BASE_URL}/mobile-services/v1/product-shelves/categories"
BONUS_METADATA_ENDPOINT = f"{BASE_URL}/mobile-services/bonuspage/v3/metadata"

CLIENT_ID = "appie-ios"
CLIENT_VERSION = "9.28"
APPLICATION = "AHWEBSHOP"

USER_AGENT = "Appie/9.28 (iPhone17,3; iPhone; CPU OS 26_1 like Mac OS X)"

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "x-client-name": CLIENT_ID,
    "x-client-version": CLIENT_VERSION,
    "x-application": APPLICATION,
    "x-accept-language": "nl-NL",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Rate limiting (seconds)
SEARCH_DELAY = 0.5   # seconds between search requests (rate limit: ~2 req/sec)
DETAIL_DELAY = 0.2   # seconds between detail requests (rate limit: ~5 req/sec)
PAGE_SIZE = 200      # max tested successfully

# Database
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "grocery.db"
