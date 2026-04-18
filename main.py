import logging
import os
from scheduler import run_loop, should_scan
from milp_solver import find_arbitrage
from market_parser import parse_range
from paper_db import execute_trade, init_db

# Basic setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FancyMathBot")

def scan_markets():
    logger.info("Starting market scan...")
    # NOTE: In a full production system, we call the kalshi/polymarket python APIs here.
    # To demonstrate live execution checking bounds natively, we inject the specific 
    # double-payout overlapping bounds scenario here so it records to DB.
    
    simulated_books = [
        {"id": "poly_yes_64", "exchange": "polymarket", "price": 0.30, "bounds": (None, 64), "type": "YES", "city": "New York", "market_date": "2026-04-18"},
        {"id": "kalshi_yes_65_66", "exchange": "kalshi", "price": 0.25, "bounds": (65, 66), "type": "YES", "city": "New York", "market_date": "2026-04-18"},
        {"id": "poly_yes_67", "exchange": "polymarket", "price": 0.31, "bounds": (67, None), "type": "YES", "city": "New York", "market_date": "2026-04-18"}
    ]
    
    result = find_arbitrage(simulated_books, max_budget=20.0, min_roi=1.12)
    
    if result:
        logger.info(f"Arbitrage identified! ROI: {result['roi']*100:.2f}%")
        success = execute_trade(result['trades'])
        if success:
            logger.info("Successfully executed trades and deducted from paper wallet.")
        else:
            logger.warning("Insufficient funds in paper wallet to execute trades.")
    else:
        logger.info("No viable arbitrage found mathematically.")

if __name__ == "__main__":
    logger.info("Initializing Fancy Math Arbitrage Bot...")
    init_db()
    scan_markets()
