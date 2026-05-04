import logging
import requests
from paper_db import SessionLocal, Trade, resolve_trade
import json
from datetime import datetime, timedelta

logger = logging.getLogger("SettlementEngine")

def settle_open_trades():
    session = SessionLocal()
    # Query all trades that are OPEN
    open_trades = session.query(Trade).filter(Trade.status == 'OPEN').all()
    session.close() # Close session so we don't hold a lock during slow API calls
    
    if not open_trades:
        return
        
    logger.info(f"Checking settlement status for {len(open_trades)} OPEN trades...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    for t in open_trades:
        try:
            if getattr(t, 'timestamp', None):
                trade_time = t.timestamp
                if isinstance(trade_time, str):
                    try:
                        trade_time = datetime.fromisoformat(trade_time.replace('Z', '+00:00').split('.')[0])
                    except Exception:
                        pass
                        
                if isinstance(trade_time, datetime):
                    # Since markets are only created for today/tomorrow (max 48hr lifespan),
                    # any trade older than 2 full days is definitively expired in the real world.
                    if (datetime.utcnow() - trade_time).days >= 2:
                        # After 2 days without API resolution, forcefully expire the orphan trade
                        resolve_trade(t.id, False)
                        logger.warning(f"Trade {t.id} forcibly expired out of system due to 2-day age limit.")
                        continue

            if t.exchange == 'polymarket':
                # Polymarket option ID format: PM_{market_id}_YES
                parts = t.option_id.split('_')
                if len(parts) >= 3:
                    market_id = parts[1]
                    url = f"https://gamma-api.polymarket.com/markets/{market_id}"
                    logger.info(f"Querying PM settlement: {url}")
                    r = requests.get(url, timeout=10, headers=headers)
                    if r.status_code == 200:
                        m = r.json()
                        if isinstance(m, list) and m:
                            m = m[0]
                            
                        if m.get("closed"):
                            prices = m.get("outcomePrices")
                            if isinstance(prices, str):
                                prices = json.loads(prices)
                            if not prices:
                                continue
                                
                            yes_price = float(prices[0])
                            no_price = float(prices[1])
                            
                            is_win = False
                            if t.option_type == 'YES' and yes_price > 0.85:
                                is_win = True
                            elif t.option_type == 'NO' and no_price > 0.85:
                                is_win = True
                            elif t.option_type == 'YES' and yes_price < 0.15:
                                is_win = False
                            elif t.option_type == 'NO' and no_price < 0.15:
                                is_win = False
                            else:
                                logger.info(f"PM {market_id} prices {yes_price}/{no_price} not skewed enough to settle.")
                                continue # Market not definitively skewed/resolved
                                
                            resolve_trade(t.id, is_win)
                            logger.info(f"Settled Polymarket {t.option_id} -> {'WIN' if is_win else 'LOSS'}")
                        else:
                            logger.info(f"PM Market {market_id} is not marked 'closed' yet. (active={m.get('active')})")
                    else:
                        logger.warning(f"PM Market {market_id} API returned HTTP {r.status_code}")
                            
            elif t.exchange == 'kalshi':
                # Kalshi option ID format: KALSHI_{ticker}_YES
                parts = t.option_id.split('_')
                if len(parts) >= 3:
                    # Recombine ticker if it has internal underscores
                    ticker = "_".join(parts[1:-1])
                    
                    try:
                        from exchanges.kalshi import get_kalshi_api
                        market_api = get_kalshi_api()
                        if not market_api:
                            continue
                            
                        resp = market_api.get_market(ticker)
                        if not hasattr(resp, 'market'):
                            continue
                            
                        m = resp.market
                        status = str(getattr(m, 'status', '')).lower()
                        logger.info(f"Kalshi {ticker} status: {status}")
                        
                        if status in ('finalized', 'settled', 'determined'):
                            result = str(getattr(m, 'result', '')).lower()
                            logger.info(f"Kalshi {ticker} result: {result}")
                            if result in ('yes', 'no'):
                                is_win = False
                                if t.option_type == 'YES' and result == 'yes':
                                    is_win = True
                                elif t.option_type == 'NO' and result == 'no':
                                    is_win = True
                                elif t.option_type == 'YES' and result == 'no':
                                    is_win = False
                                elif t.option_type == 'NO' and result == 'yes':
                                    is_win = False
                                
                                resolve_trade(t.id, is_win)
                                logger.info(f"Settled Kalshi {t.option_id} -> {'WIN' if is_win else 'LOSS'}")
                            else:
                                logger.info(f"Kalshi {ticker} result '{result}' not recognized as yes/no.")
                        else:
                            logger.info(f"Kalshi {ticker} not yet finalized.")
                    except Exception as e:
                        logger.error(f"Error fetching Kalshi market {ticker} via SDK: {e}")
                            
        except Exception as e:
            logger.error(f"Error settling trade {t.id} ({t.option_id}): {e}")
