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

with open("templates/index.html", "w") as f:
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
            
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
                    <h2 class="text-lg font-bold text-gray-800">Trade Ledger</h2>
                </div>
                <table class="w-full text-left">
                    <thead class="bg-gray-50 text-gray-500 text-xs uppercase">
                        <tr>
                            <th class="px-6 py-3">ID</th>
                            <th class="px-6 py-3">Exchange</th>
                            <th class="px-6 py-3">Bounds</th>
                            <th class="px-6 py-3">Qty</th>
                            <th class="px-6 py-3">Cost</th>
                            <th class="px-6 py-3">Status</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200 text-sm">
                        {% for t in trades %}
                        <tr class="hover:bg-gray-50">
                            <td class="px-6 py-4 font-mono text-gray-500">#{{ t.id }}</td>
                            <td class="px-6 py-4 font-semibold {% if t.exchange == 'polymarket' %}text-blue-600{% else %}text-indigo-600{% endif %}">{{ t.exchange | capitalize }}</td>
                            <td class="px-6 py-4">{{ t.bounds_str }}</td>
                            <td class="px-6 py-4">{{ "%.2f"|format(t.qty) }}</td>
                            <td class="px-6 py-4 font-medium">${{ "%.2f"|format(t.cost) }}</td>
                            <td class="px-6 py-4">
                                {% if t.status == 'OPEN' %}
                                    <span class="bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs font-bold">OPEN</span>
                                {% elif t.status == 'RESOLVED_WIN' %}
                                    <span class="bg-emerald-100 text-emerald-800 px-2 py-1 rounded text-xs font-bold">WIN</span>
                                {% else %}
                                    <span class="bg-red-100 text-red-800 px-2 py-1 rounded text-xs font-bold">LOSS</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </body>
    </html>
    ''')

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    session = SessionLocal()
    wallet = session.query(Wallet).first()
    trades = session.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
    
    if not wallet: 
        wallet = Wallet(balance=0)
        
    session.close()
    return templates.TemplateResponse("index.html", {"request": request, "wallet": wallet, "trades": trades})

if __name__ == "__main__":
    import paper_db
    paper_db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
