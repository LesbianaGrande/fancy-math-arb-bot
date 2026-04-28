import requests
import json
import logging
from market_parser import parse_range
from py_clob_client_v2 import ClobClient, Side

logger = logging.getLogger(__name__)

# Initialize read-only CLOB V2 Client for getting real-time prices
try:
    clob_client = ClobClient(host="https://clob.polymarket.com", chain_id=137)
except Exception as e:
    logger.error(f"Failed to init ClobClient: {e}")
    clob_client = None

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
            
            yes_price = 0.0
            no_price = 0.0
            
            # Fetch best ask directly to emulate real cost basis execution
            if clob_client and "clobTokenIds" in m:
                try:
                    token_ids_str = m.get("clobTokenIds", "[]")
                    token_ids = json.loads(token_ids_str)
                    if len(token_ids) >= 2:
                        try:
                            yes_price_obj = clob_client.get_price(token_ids[0], Side.BUY)
                            yes_price = float(yes_price_obj.get("price", 0.0)) if isinstance(yes_price_obj, dict) else 0.0
                        except Exception:
                            yes_price = 0.0
                            
                        try:
                            no_price_obj = clob_client.get_price(token_ids[1], Side.BUY)
                            no_price = float(no_price_obj.get("price", 0.0)) if isinstance(no_price_obj, dict) else 0.0
                        except Exception:
                            no_price = 0.0
                except Exception as e:
                    logger.error(f"Error parsing clobTokenIds: {e}")

            # Fallback to Gamma API
            if yes_price == 0.0 or no_price == 0.0:
                best_ask = m.get("bestAsk", 0)
                try:
                    prices_str = m.get("outcomePrices", "[\"0\", \"1\"]")
                    prices = json.loads(prices_str)
                    yes_price = best_ask if best_ask != 0 else float(prices[0])
                    no_price = float(prices[1])
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
                
            # Log PM NO options to our universal matrix
            if no_price > 0.001 and no_price < 0.999:
                options.append({
                    "id": f"PM_{m['id']}_NO",
                    "exchange": "polymarket",
                    "price": no_price,
                    "bounds": bounds,
                    "type": "NO",
                    "city": event.get("title", slug),
                    "market_date": event.get("endDateIso", "Unknown")
                })
        return options
    except Exception as e:
        logger.error(f"Error fetching Polymarket: {e}")
        return []
