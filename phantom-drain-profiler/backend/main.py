"""Non-Invasive Phantom Drain Appliance Profiler - backend.

Run:  uvicorn main:app --reload --port 8000
The simulator feeds fake appliances. A real ESP32 can POST to /api/readings.
Set SIMULATE=0 to disable the simulator.
"""
import asyncio
import os
import random
import sqlite3
import time
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB = os.path.join(os.path.dirname(__file__), "profiler.db")
SIMULATE = os.getenv("SIMULATE", "1") == "1"

OFF_W = 2.0        # below this: appliance is really off
ACTIVE_W = 15.0    # above this: appliance is in use; in between = standby (phantom)
TARIFF = 8.0       # INR per kWh

# name: (active watts, standby watts)
APPLIANCES = {
    "Television": (90, 6),
    "Set-top Box": (18, 11),
    "Laptop Charger": (60, 3.5),
    "Microwave Oven": (1100, 3),
    "Washing Machine": (450, 4.5),
    "Phone Charger": (10, 0.6),
}
state = {name: "standby" for name in APPLIANCES}


def classify(w: float) -> str:
    return "off" if w < OFF_W else "standby" if w < ACTIVE_W else "active"


def conn():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():
    with closing(conn()) as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS readings("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, appliance TEXT, "
            "power_w REAL, status TEXT)"
        )
        c.execute("CREATE INDEX IF NOT EXISTS ix ON readings(appliance, ts)")
        c.commit()


def sample(name: str) -> float:
    act, sb = APPLIANCES[name]
    if random.random() < 0.04:
        state[name] = random.choices(["active", "standby", "off"], [3, 5, 2])[0]
    s = state[name]
    if s == "active":
        return act * random.uniform(0.8, 1.1)
    if s == "standby":
        return sb * random.uniform(0.85, 1.15)
    return random.uniform(0, 0.3)


def insert(rows):
    with closing(conn()) as c:
        c.executemany(
            "INSERT INTO readings(ts, appliance, power_w, status) VALUES(?,?,?,?)", rows
        )
        c.commit()


def backfill(points=360, step=20):
    now = time.time()
    rows = []
    for i in range(points):
        for name in APPLIANCES:
            w = sample(name)
            rows.append((now - (points - i) * step, name, round(w, 2), classify(w)))
    insert(rows)


async def simulator():
    while True:
        now = time.time()
        rows = []
        for name in APPLIANCES:
            w = sample(name)
            rows.append((now, name, round(w, 2), classify(w)))
        insert(rows)
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app):
    init_db()
    task = None
    if SIMULATE:
        with closing(conn()) as c:
            empty = c.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == 0
        if empty:
            backfill()
        task = asyncio.create_task(simulator())
    yield
    if task:
        task.cancel()


app = FastAPI(title="Phantom Drain Profiler", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Reading(BaseModel):
    appliance: str
    power_w: float


@app.post("/api/readings")
def ingest(r: Reading):
    insert([(time.time(), r.appliance, r.power_w, classify(r.power_w))])
    return {"status": classify(r.power_w)}


@app.get("/api/appliances")
def appliances():
    with closing(conn()) as c:
        rows = c.execute(
            "SELECT appliance, power_w, status, ts FROM readings WHERE id IN "
            "(SELECT MAX(id) FROM readings GROUP BY appliance) ORDER BY appliance"
        ).fetchall()
    return [{"name": a, "power_w": p, "status": s, "ts": t} for a, p, s, t in rows]


@app.get("/api/history/{name}")
def history(name: str, limit: int = 150):
    with closing(conn()) as c:
        rows = c.execute(
            "SELECT ts, power_w, status FROM readings WHERE appliance=? "
            "ORDER BY id DESC LIMIT ?", (name, limit)
        ).fetchall()
    return [{"ts": t, "power_w": p, "status": s} for t, p, s in reversed(rows)]


@app.get("/api/summary")
def summary():
    """Phantom load now, and projected yearly energy and cost from standby samples."""
    with closing(conn()) as c:
        stats = c.execute(
            "SELECT appliance, COUNT(*), "
            "SUM(status='standby'), AVG(CASE WHEN status='standby' THEN power_w END) "
            "FROM readings GROUP BY appliance"
        ).fetchall()
    per, now_w, annual = [], 0.0, 0.0
    latest = {a["name"]: a for a in appliances()}
    for name, n, n_sb, avg_sb in stats:
        frac = (n_sb or 0) / n if n else 0
        kwh = (avg_sb or 0) * frac * 8760 / 1000
        cur = latest.get(name)
        if cur and cur["status"] == "standby":
            now_w += cur["power_w"]
        annual += kwh
        per.append({"name": name, "standby_share": round(frac * 100, 1),
                    "avg_standby_w": round(avg_sb or 0, 2), "annual_kwh": round(kwh, 1)})
    return {"phantom_now_w": round(now_w, 1), "annual_kwh": round(annual, 1),
            "annual_cost_inr": round(annual * TARIFF), "tariff_inr_per_kwh": TARIFF,
            "per_appliance": per}
