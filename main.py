import logging
from scheduler import run_loop, should_scan
from milp_solver import find_arbitrage
from paper_db import execute_trade, init_db
from exchanges.polymarket import fetch_polymarket_events
from exchanges.kalshi import fetch_kalshi_events

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FancyMathBot")

def scan_markets():
    logger.info("Starting live market scan over API pools...")
    
    # Matching Polymarket slugs to Kalshi Tickers based on your target pairs
    cities = [
        {"poly": "highest-temperature-in-los-angeles-on-april-17-2026", "kalshi": "kxhighlax-26apr17"},
        {"poly": "highest-temperature-in-nyc-on-april-17-2026", "kalshi": "kxhighny-26apr17"},
        {"poly": "highest-temperature-in-chicago-on-april-17-2026", "kalshi": "kxhighchi-26apr17"}
        # Add more pairs here as they are released
    ]
    
    for city in cities:
        live_books = []
        poly_options = fetch_polymarket_events(city['poly'])
        kalshi_options = fetch_kalshi_events(city['kalshi'])
        
        live_books.extend(poly_options)
        live_books.extend(kalshi_options)
        
        if not live_books:
            continue
            
        result = find_arbitrage(live_books, max_budget=20.0, min_roi=1.12)
        
        if result:
            logger.info(f"Arbitrage identified! ROI: {result['roi']*100:.2f}%")
            success = execute_trade(result['trades'])
            if success:
                logger.info("Successfully executed trades and deducted from paper wallet.")
            else:
                logger.warning("Insufficient funds in paper wallet to execute trades.")
        else:
            logger.info("No viable arbitrage mathematically found on live boards.")

if __name__ == "__main__":
    logger.info("Initializing Fancy Math Arbitrage Bot...")
    init_db()
    # Execute actual continuous loop against APIs
    run_loop(scan_markets)
