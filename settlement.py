import logging
import requests
from paper_db import SessionLocal, Trade, resolve_trade
import json

logger = logging.getLogger("SettlementEngine")

def settle_open_trades():
    session = SessionLocal()
    # Query all trades that are OPEN
    open_trades = session.query(Trade).filter(Trade.status == 'OPEN').all()
    session.close() # Close session so we don't hold a lock during slow API calls
    
    if not open_trades:
        return
        
    logger.info(f"Checking settlement status for {len(open_trades)} OPEN trades...")
    
    for t in open_trades:
        try:
            if t.exchange == 'polymarket':
                # Polymarket option ID format: PM_{market_id}_YES
                parts = t.option_id.split('_')
                if len(parts) >= 3:
                    market_id = parts[1]
                    url = f"https://gamma-api.polymarket.com/markets/{market_id}"
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        m = r.json()
                        if m.get("closed"):
                            prices = m.get("outcomePrices")
                            if isinstance(prices, str):
                                prices = json.loads(prices)
                            if not prices:
                                continue
                                
                            yes_price = float(prices[0])
                            no_price = float(prices[1])
                            
                            is_win = False
                            if t.option_type == 'YES' and yes_price > 0.99:
                                is_win = True
                            elif t.option_type == 'NO' and no_price > 0.99:
                                is_win = True
                            elif t.option_type == 'YES' and yes_price < 0.01:
                                is_win = False
                            elif t.option_type == 'NO' and no_price < 0.01:
                                is_win = False
                            else:
                                continue # Market not definitively skewed/resolved
                                
                            resolve_trade(t.id, is_win)
                            logger.info(f"Settled Polymarket {t.option_id} -> {'WIN' if is_win else 'LOSS'}")
                            
            elif t.exchange == 'kalshi':
                # Kalshi option ID format: KALSHI_{ticker}_YES
                parts = t.option_id.split('_')
                if len(parts) >= 3:
                    # Recombine ticker if it has internal underscores
                    ticker = "_".join(parts[1:-1])
                    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}"
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        m = data.get('market', {})
                        if m.get('status') in ('finalized', 'settled'):
                            result = m.get('result', '').lower()
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
                            
        except Exception as e:
            logger.error(f"Error settling trade {t.id} ({t.option_id}): {e}")
