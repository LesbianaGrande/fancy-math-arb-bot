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
            
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Arbitrage Execution Bundles</h2>
                
                {% for bundle_id, data in bundles.items() %}
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
                                    {% if t.status == 'OPEN' %}
                                        <span class="bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs font-bold tracking-wider">OPEN</span>
                                    {% elif t.status == 'RESOLVED_WIN' %}
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
            bundles[bid] = {"trades": [], "total_cost": 0.0}
        bundles[bid]["trades"].append(t)
        bundles[bid]["total_cost"] += t.cost
        
    session.close()
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "wallet": wallet, 
        "bundles": bundles
    })

if __name__ == "__main__":
    import paper_db
    paper_db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
