import os
import logging
import tempfile
import requests
from market_parser import parse_range
try:
    import kalshi_python
except ImportError:
    pass

logger = logging.getLogger(__name__)

def fetch_kalshi_events(ticker):
    key_id = os.getenv("KALSHI_KEY_ID")
    private_key_str = os.getenv("KALSHI_PRIVATE_KEY")
    
    if not key_id or not private_key_str:
        logger.warning(f"Missing Kalshi Keys. Skipping Kalshi pull for {ticker}.")
        return []

    try:
        tmp_key_path = os.path.join(tempfile.gettempdir(), "kalshi.key")
        # Ensure proper newline formatting for RSA PKCS8 loading
        priv_key = private_key_str.replace("\\\\n", "\\n").replace("\\n", "\n")
        if not priv_key.endswith("\n"): 
            priv_key += "\n"
            
        with open(tmp_key_path, "w") as f:
            f.write(priv_key)
            
        config = kalshi_python.Configuration()
        config.host = "https://api.elections.kalshi.com/trade-api/v2"
        
        # Build Kalshi authenticated SDK Client natively 
        kalshi_api_client = kalshi_python.KalshiClient(config)
        kalshi_api_client.set_kalshi_auth(key_id, tmp_key_path)
        
        market_api = kalshi_python.MarketsApi(kalshi_api_client)
        resp = market_api.get_markets(event_ticker=ticker)
        
        options = []
        if not hasattr(resp, 'markets'):
            logger.warning(f"Kalshi responded with no markets attribute for {ticker}!")
            return []
            
        logger.info(f" -> Kalshi API Raw Found: {len(resp.markets)} underlying markets inside {ticker}")
            
        for m in resp.markets:
            title = m.title
            bounds = parse_range(title)
            
            if bounds == (None, None): 
                logger.info(f"    -> Evaluating Kalshi Leg: '{title}' | Bounds: {bounds} | yes_ask: N/A (Skipped)")
                continue
                
            # Note: Kalshi V2 bulk endpoints purposely dehydrate orderbook tops payload. 
            # SDK's get_market_orderbook fails due to V2 schema change ('orderbook' -> 'orderbook_fp').
            # We explicitly pull the public REST endpoint and calculate yes_ask inversely from the NO bid vector.
            try:
                ob_json = requests.get(f"https://api.elections.kalshi.com/trade-api/v2/markets/{m.ticker}/orderbook").json()
                
                # Kalshi orderbook arrays: 'yes_dollars' are YES bids, 'no_dollars' are NO bids.
                # To execute a YES buy immediately, we must hit the resting NO bids (Ask = 1.0 - max(No_bids)).
                no_dollars = ob_json.get('orderbook_fp', {}).get('no_dollars', [])
                
                if not no_dollars:
                    yes_ask = 0
                else:
                    best_no_bid = max([float(order[0]) for order in no_dollars])
                    yes_ask = int(round((1.0 - best_no_bid) * 100))
                    
                # To execute a NO buy immediately, we must hit the resting YES bids (Ask = 1.0 - max(Yes_bids)).
                yes_dollars = ob_json.get('orderbook_fp', {}).get('yes_dollars', [])
                
                if not yes_dollars:
                    no_ask = 0
                else:
                    best_yes_bid = max([float(order[0]) for order in yes_dollars])
                    no_ask = int(round((1.0 - best_yes_bid) * 100))
                    
                # Removed the 'inverse NO bid' text since it confused the dashboard visualization
                logger.info(f"    --> Calculated Ask successfully for {m.ticker}: YES={yes_ask}c, NO={no_ask}c")
                
            except Exception as e:
                logger.debug(f"Failed to fetch or parse market orderbook execution limits for {m.ticker}: {e}")
                yes_ask = 0
                no_ask = 0
            
            if yes_ask > 0 and yes_ask < 100:
                options.append({
                    "id": f"KALSHI_{m.ticker}_YES",
                    "exchange": "kalshi",
                    "price": yes_ask / 100.0,
                    "bounds": bounds,
                    "type": "YES",
                    "city": f"Kalshi Ticker: {ticker}",
                    "market_date": "Live API Stream"
                })
                
            if no_ask > 0 and no_ask < 100:
                options.append({
                    "id": f"KALSHI_{m.ticker}_NO",
                    "exchange": "kalshi",
                    "price": no_ask / 100.0,
                    "bounds": bounds,
                    "type": "NO",
                    "city": f"Kalshi Ticker: {ticker}",
                    "market_date": "Live API Stream"
                })
            
        return options
    except Exception as e:
        logger.error(f"Error executing Kalshi SDK pull: {e}")
        return []
