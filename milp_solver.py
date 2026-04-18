import pulp
import logging
from market_parser import get_state_space

logger = logging.getLogger(__name__)

def find_arbitrage(options_data, max_budget=20.0, min_roi=1.12):
    """
    Uses Mixed-Integer Linear Programming to construct an arbitrage portfolio.
    Enforces a strict min_roi (default 12%), scales constraints across disjoint sets.
    """
    if not options_data: 
        return None
        
    from paper_db import get_previous_bundles
    prev_bundles = get_previous_bundles()
    
    bounds_list = [opt['bounds'] for opt in options_data]
    states = get_state_space(bounds_list)
    
    prob = pulp.LpProblem("Arbitrage_Finder", pulp.LpMaximize)
    
    shares_vars = {}
    y_vars = {}
    
    # 1. Initialize Variables per Matrix Column
    for opt in options_data:
        oid = opt['id']
        exc = opt['exchange']
        
        y_vars[oid] = pulp.LpVariable(f"Y_{oid}", cat='Binary')
        
        if exc == "kalshi":
            shares_vars[oid] = pulp.LpVariable(f"K_{oid}", lowBound=0, cat='Integer')
            # Constraints: Kalshi must buy at least 1 share if picked
            prob += shares_vars[oid] >= 1.0 * y_vars[oid], f"K_min_spend_{oid}"
            # Link constraint: if shares > 0, binary Y MUST be 1
            M = (max_budget / max(opt['price'], 0.0001)) + 5
            prob += shares_vars[oid] <= M * y_vars[oid], f"K_link_{oid}"
            
        elif exc == "polymarket":
            shares_vars[oid] = pulp.LpVariable(f"P_{oid}", lowBound=0, cat='Continuous')
            
            # Constraints: Polymarket must have >= $1 minimum spend if picked
            prob += shares_vars[oid] * opt['price'] >= 1.0 * y_vars[oid], f"PM_min_spend_{oid}"
            # M-constraint to shut off variable if Y is 0
            M = (max_budget / max(opt['price'], 0.0001)) + 5
            prob += shares_vars[oid] <= M * y_vars[oid], f"PM_link_{oid}"

    # 1.5 Evaluate Database Tabu Cuts to force combination diversification
    for idx, bundle in enumerate(prev_bundles):
        y_in_bundle = [y_vars[oid] for oid in bundle if oid in y_vars]
        y_out_bundle = [y for oid, y in y_vars.items() if oid not in bundle]
        
        # Only inject cut if the entire puzzle configuration is active on the board today
        if len(y_in_bundle) == len(bundle):
            prob += pulp.lpSum(y_in_bundle) - pulp.lpSum(y_out_bundle) <= len(bundle) - 1, f"Tabu_Cut_{idx}"

    # 2. Total Cost definition & max budget boundary
    total_cost = pulp.lpSum(shares_vars[opt['id']] * opt['price'] for opt in options_data)
    prob += total_cost <= max_budget, "Global_Max_Budget"
    
    # 3. Minimum Payout definition (The objective variable)
    worst_payout = pulp.LpVariable("Lowest_Guaranteed_Payout", lowBound=0, cat='Continuous')
    
    # 4. Map Payout Matrix Row constraints
    total_state_payouts = []
    for T in states:
        payout_in_state_T = []
        for opt in options_data:
            b_min, b_max = opt['bounds']
            
            in_range = True
            if b_min is not None and T < b_min: in_range = False
            if b_max is not None and T > b_max: in_range = False
                
            pays = in_range if opt['type'] == 'YES' else not in_range
                
            if pays:
                payout_in_state_T.append(shares_vars[opt['id']] * 1.0) 
        
        state_sum = pulp.lpSum(payout_in_state_T)
        prob += state_sum >= worst_payout, f"Coverage_T_{T}"
        total_state_payouts.append(state_sum)
    
    # 5. Core Mathematical Invariant: Worst case must exceed Return Profile floor
    prob += worst_payout >= total_cost * min_roi, f"Requires_Min_ROI_{int(min_roi*100)}"
    
    # 6. Objective: Maximize Total Upside Area (Lottery tickets)
    # By maximizing the sum of all state payouts, the solver will aggressively buy cheap, overlapping
    # "lottery ticket" options to raise the mathematical ceiling, as long as the guaranteed minimum floor holds.
    prob += pulp.lpSum(total_state_payouts) - total_cost, "Maximize_Upside"
    
    # Execute LP solver natively without streaming to terminal
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    
    if pulp.LpStatus[prob.status] == "Optimal":
        cost_val = pulp.value(total_cost)
        if not cost_val or cost_val <= 0.01:
            return None # LP evaluated to doing nothing.
            
        payout_val = pulp.value(worst_payout)
        
        trades = []
        for opt in options_data:
            var = shares_vars[opt['id']]
            if var.varValue and var.varValue > 0:
                trades.append({
                    "id": opt['id'],
                    "exchange": opt["exchange"],
                    "qty": round(var.varValue, 3), 
                    "price": opt["price"],
                    "type": opt["type"],
                    "bounds": opt["bounds"],
                    "city": opt.get("city", "Unknown"),
                    "market_date": opt.get("market_date", "Unknown")
                })
                
        logger.info(f"MILP Engine Validated Path: Cost: ${cost_val:.2f} -> Guaranteed Return: ${payout_val:.2f}")
        return {
            "status": "Found",
            "cost": cost_val,
            "worst_payout": payout_val,
            "profit": payout_val - cost_val,
            "roi": (payout_val - cost_val) / cost_val,
            "trades": trades
        }
    
    return None
