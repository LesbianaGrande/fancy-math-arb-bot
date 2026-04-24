from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from paper_db import SessionLocal, Wallet, Trade
import uvicorn
import os
from contextlib import asynccontextmanager
import threading
from main import scan_markets
from scheduler import run_loop
from collections import OrderedDict

def bot_thread():
    run_loop(scan_markets)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start bot thread
    import paper_db
    paper_db.init_db()
    thread = threading.Thread(target=bot_thread, daemon=True)
    thread.start()
    yield

app = FastAPI(title="Fancy Math Arbitrage Dashboard", lifespan=lifespan)
os.makedirs("templates", exist_ok=True)

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write('''
    <html>
        <head>
            <title>Fancy Math Arb Bot</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-100 p-8">
            <h1 class="text-3xl font-bold mb-4 flex items-center">
                <span class="text-blue-600 mr-2">➗ Fancy Math</span> Arb Bot 
            </h1>
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 mb-6">
                <p class="text-sm text-gray-500 uppercase tracking-widest font-semibold mb-1">Paper Wallet Balance</p>
                <h2 class="text-4xl font-black text-emerald-600">${{ "%.2f"|format(wallet.balance) }}</h2>
            </div>
            
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden p-6 mb-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Open Arbitrage Bundles</h2>
                {% if open_bundles|length == 0 %}
                    <p class="text-gray-500 italic">No open trades currently.</p>
                {% endif %}
                {% for bundle_id, data in open_bundles.items() %}
                <div class="mb-6 border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                    <div class="bg-gray-800 text-white px-4 py-3 flex justify-between items-center">
                        <div class="flex items-center">
                            <span class="font-bold text-sm tracking-widest text-gray-400 mr-4">ID: {{ bundle_id }}</span>
                            {% if data.trades|length > 0 %}
                            <span class="px-2 py-1 bg-gray-700 rounded text-xs font-bold text-blue-200 tracking-wide uppercase shadow-inner">📍 {{ data.trades[0].city }} &bull; {{ data.trades[0].market_date }}</span>
                            {% endif %}
                        </div>
                        <span class="font-bold">Total Matrix Cost: <span class="text-green-400">${{ "%.2f"|format(data.total_cost) }}</span></span>
                    </div>
                    <table class="w-full text-left text-sm bg-white">
                        <thead class="bg-gray-100 text-gray-500 uppercase text-xs">
                            <tr>
                                <th class="px-4 py-2">Exchange</th>
                                <th class="px-4 py-2">Direction</th>
                                <th class="px-4 py-2">Math Bounds</th>
                                <th class="px-4 py-2">Qty Bought</th>
                                <th class="px-4 py-2">Leg Cost</th>
                                <th class="px-4 py-2">Status</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-100">
                            {% for t in data.trades %}
                            <tr class="hover:bg-gray-50">
                                <td class="px-4 py-3 font-semibold {% if t.exchange == 'polymarket' %}text-blue-600{% else %}text-indigo-600{% endif %}">{{ t.exchange | capitalize }}</td>
                                <td class="px-4 py-3 font-bold {% if t.option_type == 'YES' %}text-emerald-600{% else %}text-rose-500{% endif %}">{{ t.option_type }}</td>
                                <td class="px-4 py-3 font-mono text-gray-600">{{ t.bounds_str | replace("None", "∞") | replace("_", " TO ") }}</td>
                                <td class="px-4 py-3">{{ "%.3f"|format(t.qty) }}</td>
                                <td class="px-4 py-3">${{ "%.2f"|format(t.cost) }}</td>
                                <td class="px-4 py-3">
                                    <span class="bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs font-bold tracking-wider">OPEN</span>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% endfor %}
            </div>

            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Settled Trades</h2>
                {% if settled_bundles|length == 0 %}
                    <p class="text-gray-500 italic">No settled trades yet.</p>
                {% endif %}
                {% for bundle_id, data in settled_bundles.items() %}
                <div class="mb-6 border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                    <div class="bg-gray-800 text-white px-4 py-3 flex justify-between items-center">
                        <div class="flex items-center">
                            <span class="font-bold text-sm tracking-widest text-gray-400 mr-4">ID: {{ bundle_id }}</span>
                            {% if data.trades|length > 0 %}
                            <span class="px-2 py-1 bg-gray-700 rounded text-xs font-bold text-blue-200 tracking-wide uppercase shadow-inner">📍 {{ data.trades[0].city }} &bull; {{ data.trades[0].market_date }}</span>
                            {% endif %}
                        </div>
                        <div class="flex space-x-6 items-center">
                            <span class="text-sm font-semibold text-gray-300">Cost: ${{ "%.2f"|format(data.total_cost) }}</span>
                            <span class="font-bold">Net Profit: 
                                {% set net = data.total_payout - data.total_cost %}
                                {% if net > 0 %}
                                    <span class="text-emerald-400">+${{ "%.2f"|format(net) }}</span>
                                {% else %}
                                    <span class="text-rose-400">-${{ "%.2f"|format(net|abs) }}</span>
                                {% endif %}
                            </span>
                        </div>
                    </div>
                    <table class="w-full text-left text-sm bg-white">
                        <thead class="bg-gray-100 text-gray-500 uppercase text-xs">
                            <tr>
                                <th class="px-4 py-2">Exchange</th>
                                <th class="px-4 py-2">Direction</th>
                                <th class="px-4 py-2">Math Bounds</th>
                                <th class="px-4 py-2">Cost</th>
                                <th class="px-4 py-2">Payout</th>
                                <th class="px-4 py-2">Leg P/L</th>
                                <th class="px-4 py-2">Result</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-100">
                            {% for t in data.trades %}
                            <tr class="hover:bg-gray-50">
                                <td class="px-4 py-3 font-semibold {% if t.exchange == 'polymarket' %}text-blue-600{% else %}text-indigo-600{% endif %}">{{ t.exchange | capitalize }}</td>
                                <td class="px-4 py-3 font-bold {% if t.option_type == 'YES' %}text-emerald-600{% else %}text-rose-500{% endif %}">{{ t.option_type }}</td>
                                <td class="px-4 py-3 font-mono text-gray-600">{{ t.bounds_str | replace("None", "∞") | replace("_", " TO ") }}</td>
                                <td class="px-4 py-3">${{ "%.2f"|format(t.cost) }}</td>
                                {% set leg_payout = (t.qty * t.payout_per_share) if t.status == 'RESOLVED_WIN' else 0 %}
                                <td class="px-4 py-3">${{ "%.2f"|format(leg_payout) }}</td>
                                <td class="px-4 py-3 font-bold">
                                    {% set leg_pl = leg_payout - t.cost %}
                                    {% if leg_pl > 0 %}
                                        <span class="text-emerald-600">+${{ "%.2f"|format(leg_pl) }}</span>
                                    {% else %}
                                        <span class="text-rose-600">-${{ "%.2f"|format(leg_pl|abs) }}</span>
                                    {% endif %}
                                </td>
                                <td class="px-4 py-3">
                                    {% if t.status == 'RESOLVED_WIN' %}
                                        <span class="bg-emerald-100 text-emerald-800 px-2 py-1 rounded text-xs font-bold tracking-wider">WIN</span>
                                    {% else %}
                                        <span class="bg-red-100 text-red-800 px-2 py-1 rounded text-xs font-bold tracking-wider">LOSS</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% endfor %}
            </div>
        </body>
    </html>
    ''')

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    session = SessionLocal()
    wallet = session.query(Wallet).first()
    all_trades = session.query(Trade).order_by(Trade.timestamp.desc()).limit(200).all()
    
    if not wallet: 
        wallet = Wallet(balance=0)
        
    bundles = OrderedDict()
    for t in all_trades:
        bid = t.bundle_id or "Legacy_Orphan"
        if bid not in bundles:
            bundles[bid] = {"trades": [], "total_cost": 0.0, "total_payout": 0.0, "is_open": False}
        bundles[bid]["trades"].append(t)
        bundles[bid]["total_cost"] += t.cost
        
        if t.status == 'OPEN':
            bundles[bid]["is_open"] = True
        elif t.status == 'RESOLVED_WIN':
            bundles[bid]["total_payout"] += (t.qty * t.payout_per_share)
            
    open_bundles = OrderedDict()
    settled_bundles = OrderedDict()
    
    for bid, data in bundles.items():
        if data["is_open"]:
            open_bundles[bid] = data
        else:
            settled_bundles[bid] = data
            
    session.close()
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "wallet": wallet, 
        "open_bundles": open_bundles,
        "settled_bundles": settled_bundles
    })

if __name__ == "__main__":
    import paper_db
    paper_db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
