import os
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class Wallet(Base):
    __tablename__ = 'wallet'
    id = Column(Integer, primary_key=True)
    balance = Column(Float, default=10000.0)

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    bundle_id = Column(String, default="Legacy") # Groups legs of an arbitrage
    city = Column(String, default="Unknown")
    market_date = Column(String, default="Unknown")
    exchange = Column(String)
    option_id = Column(String)
    option_type = Column(String) # YES / NO
    bounds_str = Column(String) # String representation of bounds
    qty = Column(Float)
    price = Column(Float)
    cost = Column(Float)
    payout_per_share = Column(Float, default=1.0)
    status = Column(String, default="OPEN") # OPEN, RESOLVED_WIN, RESOLVED_LOSS
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine('sqlite:///paper_trading.db')
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    w = session.query(Wallet).first()
    if not w:
        w = Wallet(balance=10000.0)
        session.add(w)
        session.commit()
    session.close()

def execute_trade(trades_list):
    """
    Executes a list of trades if the wallet has sufficient funds.
    """
    session = SessionLocal()
    total_cost = sum(t["qty"] * t["price"] for t in trades_list)
    
    wallet = session.query(Wallet).first()
    if wallet.balance < total_cost:
        session.close()
        return False
        
    wallet.balance -= total_cost
    
    import uuid
    bundle_id = str(uuid.uuid4())[:8]
    for t in trades_list:
        tr = Trade(
            bundle_id=bundle_id,
            city=t.get("city", "Unknown"),
            market_date=t.get("market_date", "Unknown"),
            exchange=t["exchange"],
            option_id=t["id"],
            option_type=t["type"],
            bounds_str=f"{t['bounds'][0]}_{t['bounds'][1]}",
            qty=t["qty"],
            price=t["price"],
            cost=t["qty"] * t["price"]
        )
        session.add(tr)
        
    session.commit()
    session.close()
    return True

def resolve_trade(trade_id, is_win):
    session = SessionLocal()
    tr = session.query(Trade).filter_by(id=trade_id).first()
    if tr and tr.status == "OPEN":
        tr.status = "RESOLVED_WIN" if is_win else "RESOLVED_LOSS"
        if is_win:
            wallet = session.query(Wallet).first()
            wallet.balance += (tr.qty * tr.payout_per_share)
        session.commit()
    session.close()
