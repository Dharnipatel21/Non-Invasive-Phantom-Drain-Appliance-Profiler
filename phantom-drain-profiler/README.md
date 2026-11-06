# Non-Invasive Phantom Drain Appliance Profiler

Monitors appliance power and flags standby (phantom) drain. Classification (same in firmware and backend):

| Power | State |
|---|---|
| < 2 W | off |
| 2 to 15 W | standby (phantom drain) |
| > 15 W | active |

## Structure

- `backend/` FastAPI + SQLite, with a built-in simulator of six household appliances
- `frontend/` React + Tailwind (CDN) dashboard
- `firmware/` ESP32 Arduino sketch (potentiometer simulates a current sensor, OLED + LEDs)

## Run the simulation (no hardware)

Backend:

```
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000
```

Frontend (second terminal):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. On first start the backend backfills about two hours of data so the charts are populated for screenshots. Delete `backend/profiler.db` to reset.

## Connect the ESP32

1. Wire it as described at the top of `firmware/phantom_profiler/phantom_profiler.ino`.
2. Set WiFi credentials and `SERVER_URL` (your computer's LAN IP) in the sketch, then upload it.
3. Start the backend with `uvicorn main:app --host 0.0.0.0 --port 8000`.
4. The "ESP32 Prototype" appliance appears on the dashboard. Turn the potentiometer to move between off, standby and active.

Set `SIMULATE=0` before starting the backend to disable the fake appliances and show only real data.

## API

- `POST /api/readings` body `{"appliance": "...", "power_w": 5.2}`
- `GET /api/appliances` latest reading and status per appliance
- `GET /api/history/{name}?limit=150`
- `GET /api/summary` phantom load now, projected kWh/year and cost (tariff set in `backend/main.py`)
