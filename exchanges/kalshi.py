import os
import logging
import tempfile
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
        config.host = "https://trading-api.kalshi.com/trade-api/v2"
        
        # Build Kalshi authenticated SDK Client natively 
        kalshi_api_client = kalshi_python.KalshiClient(config)
        kalshi_api_client.set_kalshi_auth(key_id, tmp_key_path)
        
        market_api = kalshi_python.MarketsApi(kalshi_api_client)
        resp = market_api.get_markets(event_ticker=ticker)
        
        options = []
        if not hasattr(resp, 'markets'):
            return []
            
        for m in resp.markets:
            title = m.title
            bounds = parse_range(title)
            if bounds == (None, None): continue
            
            yes_ask = m.yes_ask
            if not yes_ask or yes_ask <= 1 or yes_ask > 98: continue
            
            options.append({
                "id": f"KALSHI_{m.ticker}_YES",
                "exchange": "kalshi",
                "price": yes_ask / 100.0,
                "bounds": bounds,
                "type": "YES",
                "city": f"Kalshi Ticker: {ticker}",
                "market_date": "Live API Stream"
            })
            
        return options
    except Exception as e:
        logger.error(f"Error executing Kalshi SDK pull: {e}")
        return []
