import time
import pytz
from datetime import datetime, timedelta

def should_scan(market_date_str, city_timezone="America/New_York"):
    """
    market_date_str: "2026-04-17"
    city_timezone: e.g. "America/Los_Angeles"
    Returns True if we should scan this market based on 2 PM local time logic.
    """
    tz = pytz.timezone(city_timezone)
    now = datetime.now(tz)
    
    market_date = datetime.strptime(market_date_str, "%Y-%m-%d").date()
    today_date = now.date()
    
    # 1. Always scan "tomorrow's" markets
    if market_date > today_date:
        return True
    
    # 2. Today's markets until exactly 2PM local time
    if market_date == today_date:
        if now.hour < 14:
            return True
            
    return False

def run_loop(execute_callback):
    """
    Infinite scheduler loop.
    execute_callback should trigger the exchange fetch -> MILP solver -> execute_trade
    """
    while True:
        execute_callback()
        time.sleep(300) # scan every 5 minutes
