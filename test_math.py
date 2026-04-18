import logging
from milp_solver import find_arbitrage

logging.basicConfig(level=logging.INFO)

test_data = [
    {"id": "opt1", "exchange": "polymarket", "price": 0.03, "bounds": (None, 64), "type": "YES"},
    {"id": "opt2", "exchange": "kalshi", "price": 0.19, "bounds": (67, None), "type": "YES"},
    {"id": "opt3", "exchange": "polymarket", "price": 0.68, "bounds": (68, 69), "type": "NO"}
]

if __name__ == "__main__":
    print("Testing MILP solver with Double Payout Edge Case...")
    res = find_arbitrage(test_data, max_budget=20.0, min_roi=1.12)
    if res:
        print("ARBITRAGE FOUND:")
        print(f"Total Cost: ${res['cost']:.2f}")
        print(f"Worst Payout: ${res['worst_payout']:.2f}")
        print(f"ROI: {res['roi']*100:.2f}%")
        print("Trades:")
        for t in res['trades']:
            print(f"  - {t['exchange']} [{t['type']}] {t['bounds']} | Qty: {t['qty']} @ ${t['price']:.2f}")
    else:
        print("NO ARBITRAGE FOUND.")
