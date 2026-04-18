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
    
    # Dynamically generate active markets based on timezone cutoff logic
    import datetime
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    
    dates_to_scan = []
    if should_scan(today.strftime("%Y-%m-%d"), "America/New_York"):
         dates_to_scan.append(today)
    if should_scan(tomorrow.strftime("%Y-%m-%d"), "America/New_York"):
         dates_to_scan.append(tomorrow)
         
    CITY_MAPPINGS = {
        "los-angeles": "KXHIGHLAX",
        "nyc": "KXHIGHNY",
        "chicago": "KXHIGHCHI",
        "miami": "KXHIGHMIA",
        "austin": "KXHIGHAUS",
        "houston": "KXHIGHHOU",
        "philadelphia": "KXHIGHPHIL",
        "denver": "KXHIGHDEN",
        "san-francisco": "KXHIGHTSFO",
        "boston": "KXHIGHTBOS",
        "las-vegas": "KXHIGHTLV",
        "washington-dc": "KXHIGHTDC",
        "phoenix": "KXHIGHTPHX",
        "san-antonio": "KXHIGHTSATX",
        "new-orleans": "KXHIGHTNOLA",
        "oklahoma-city": "KXHIGHTOKC",
        "dallas": "KXHIGHTDAL",
        "seattle": "KXHIGHTSEA",
        "atlanta": "KXHIGHTATL",
        "minneapolis": "KXHIGHTMIN"
    }
         
    cities = []
    for d in dates_to_scan:
        poly_date = f"{d.strftime('%B').lower()}-{d.day}-{d.year}"
        kalshi_date = f"{d.strftime('%y')}{d.strftime('%b').upper()}{d.day:02d}"
        
        for poly_city, kalshi_code in CITY_MAPPINGS.items():
            cities.append({
                "poly": f"highest-temperature-in-{poly_city}-on-{poly_date}", 
                "kalshi": f"{kalshi_code}-{kalshi_date}"
            })
    
    for city in cities:
        logger.info(f"Scanning Target Pair: {city['poly']} <-> {city['kalshi']}")
        live_books = []
        
        # Scrape PM
        poly_options = fetch_polymarket_events(city['poly'])
        logger.info(f" -> Grabbed {len(poly_options)} PM option limits")
        
        # Scrape Kalshi
        kalshi_options = fetch_kalshi_events(city['kalshi'])
        logger.info(f" -> Grabbed {len(kalshi_options)} Kalshi option limits")
        
        live_books.extend(poly_options)
        live_books.extend(kalshi_options)
        
        if not poly_options or not kalshi_options:
            logger.warning(" -> Lacking bilateral cross-exchange data overlapping for this market target. Skipping arbitrage engine.")
            continue
            
        logger.info(f" -> Injecting {len(live_books)} total options into the MILP Matrix...")
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
