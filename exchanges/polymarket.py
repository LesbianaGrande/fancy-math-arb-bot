import requests
import logging
from market_parser import parse_range

logger = logging.getLogger(__name__)

def fetch_polymarket_events(slug):
    """
    Fetches gamma-api polymarket data and normalizes it.
    """
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    
    # Normally we do `resp = requests.get(url).json()`
    # And iterate over `markets` to pass `groupItemTitle` to `parse_range()`
    
    return []
