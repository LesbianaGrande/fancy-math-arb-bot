import requests
import json
import logging
from market_parser import parse_range

logger = logging.getLogger(__name__)

def fetch_polymarket_events(slug):
    """
    Fetches gamma-api polymarket data and normalizes it.
    """
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return []
            
        data = r.json()
        if not data: return []
        
        event = data[0]
        options = []
        
        for m in event.get("markets", []):
            title = m.get("groupItemTitle", "")
            bounds = parse_range(title)
            if bounds == (None, None): continue
            
            # Fetch best ask directly to emulate real cost basis execution
            best_ask = m.get("bestAsk", 0)
            
            try:
                prices_str = m.get("outcomePrices", "[\"0\", \"1\"]")
                prices = json.loads(prices_str)
                yes_price = best_ask if best_ask != 0 else float(prices[0])
            except:
                continue
                
            # Log PM YES options to our universal matrix
            if yes_price > 0.001 and yes_price < 0.999:
                options.append({
                    "id": f"PM_{m['id']}_YES",
                    "exchange": "polymarket",
                    "price": yes_price,
                    "bounds": bounds,
                    "type": "YES",
                    "city": event.get("title", slug),
                    "market_date": event.get("endDateIso", "Unknown")
                })
        return options
    except Exception as e:
        logger.error(f"Error fetching Polymarket: {e}")
        return []
