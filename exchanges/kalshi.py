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
            # We must explicitly query the individual market to materialize the specific yes_ask limit price.
            try:
                single_m_resp = market_api.get_market(ticker=m.ticker)
                yes_ask = getattr(single_m_resp.market, 'yes_ask', 0)
            except Exception as e:
                logger.debug(f"Failed to fetch market orderbook execution limits for {m.ticker}: {e}")
                yes_ask = 0
            
            # Temporary internal log to inspect API data drops
            logger.info(f"    -> Evaluating Kalshi Leg: '{title}' | Bounds: {bounds} | yes_ask: {yes_ask}")
            
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
