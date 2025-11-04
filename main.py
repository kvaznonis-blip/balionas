from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import requests, math, time

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# ===== Konstanta =====
DEFAULT_DIR = 315.0   # iš pietryčių į šiaurės vakarus
DEFAULT_SPD = 10.0
EARTH_M = 111320      # 1° ~ 111.32 km
CACHE_TTL = 600       # cache 10 min

# ===== Paprastas cache (vėjo duomenims) =====
wind_cache = {}

def get_wind(lat, lon):
    """Grąžina vėjo greitį ir kryptį, naudodamas cache ir du šaltinius."""
    key = (round(lat, 2), round(lon, 2))
    now = time.time()
    if key in wind_cache and now - wind_cache[key]["t"] < CACHE_TTL:
        return wind_cache[key]["ws"], wind_cache[key]["wd"], wind_cache[key]["src"]

    # 1️⃣ Open-Meteo
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=windspeed_100m,winddirection_100m"
        r = requests.get(url, timeout=4)
        j = r.json()
        ws = j["hourly"]["windspeed_100m"][-1]
        wd = j["hourly"]["winddirection_100m"][-1]
        wind_cache[key] = {"ws": ws, "wd": wd, "src": "Open-Meteo", "t": now}
        return ws, wd, "Open-Meteo"
    except Exception:
        pass

    # 2️⃣ „fallback“ (antras bandymas su alternatyviais laukų vardais tame pačiame API)
    try:
        url2 = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=wind_speed_100m,wind_direction_100m"
        r2 = requests.get(url2, timeout=4)
        j2 = r2.json()
        ws = j2["hourly"]["wind_speed_100m"][-1]
        wd = j2["hourly"]["wind_direction_100m"][-1]
        wind_cache[key] = {"ws": ws, "wd": wd, "src": "Open-Meteo(alt)", "t": now}
        return ws, wd, "Open-Meteo(alt)"
    except Exception:
        pass

    # 3️⃣ Default
    wind_cache[key] = {"ws": DEFAULT_SPD, "wd": DEFAULT_DIR, "src": "Default", "t": now}
    return DEFAULT_SPD, DEFAULT_DIR, "Default"

def step_xy(lat, lon, ws, wd, dt, reverse=False):
    """Vienas žingsnis pagal vėjo kryptį (wd) – kur PUČIA."""
    vx = ws * math.sin(math.radians(wd))
    vy = ws * math.cos(math.radians(wd))
    if reverse:
        vx, vy = -vx, -vy
    lon += vx * dt / EARTH_M
    lat += vy * dt / EARTH_M
    return lat, lon

# ===== Trajektorijos =====
@app.post("/trajectory_t1")
async def trajectory_t1(req: Request):
    d = await req.json()
    lat, lon, alt, spd = d["lat"], d["lon"], d["altitude"], d["speed"]
    ws, wd, src = get_wind(lat, lon)
    dt, steps = 15, 50
    traj = []
    for _ in range(steps):
        lat, lon = step_xy(lat, lon, ws, wd, dt)
        traj.append({"lat": lat, "lon": lon, "alt": alt})
    return JSONResponse({"trajectory": traj, "src": src})

@app.post("/trajectory_t2")
async def trajectory_t2(req: Request):
    d = await req.json()
    lat, lon, alt, spd = d["lat"], d["lon"], d["altitude"], d["speed"]
    v_vert = spd if spd > 0 else 2.5
    dt = 15
    h = alt
    traj = []
    ws, wd, src = get_wind(lat, lon)  # vienas kvietimas
    while h > 0:
        lat, lon = step_xy(lat, lon, ws, wd, dt)
        h -= v_vert * dt
        traj.append({"lat": lat, "lon": lon, "alt": max(h, 0)})
    return JSONResponse({"trajectory": traj, "src": src})

@app.post("/trajectory_t3")
async def trajectory_t3(req: Request):
    d = await req.json()
    lat, lon, alt, spd = d["lat"], d["lon"], d["altitude"], d["speed"]
    mass = 55.0
    v_vert = spd if spd > 0 else 2.5
    dt = 15
    h = alt
    traj = []
    ws, wd, src = get_wind(lat, lon)  # vienas kvietimas
    while h > 0:
        lat, lon = step_xy(lat, lon, ws, wd, dt)
        h -= v_vert * dt * (1 + 0.0001 * (mass - 55))
        traj.append({"lat": lat, "lon": lon, "alt": max(h, 0)})
    return JSONResponse({"trajectory": traj, "src": src})

# ===== Reverse (atgalinės) =====
@app.post("/trajectory_t1r")
async def trajectory_t1r(req: Request):
    d = await req.json()
    lat, lon, alt, spd = d["lat"], d["lon"], d["altitude"], d["speed"]
    ws, wd, src = get_wind(lat, lon)
    dt, steps = 15, 50
    traj = []
    for _ in range(steps):
        lat, lon = step_xy(lat, lon, ws, wd, dt, reverse=True)
        traj.append({"lat": lat, "lon": lon, "alt": alt})
    return JSONResponse({"trajectory": traj, "src": src})

@app.post("/trajectory_t2r")
async def trajectory_t2r(req: Request):
    d = await req.json()
    lat, lon, alt, spd = d["lat"], d["lon"], d["altitude"], d["speed"]
    v_vert = spd if spd > 0 else 2.5
    dt = 15
    h = alt
    traj = []
    ws, wd, src = get_wind(lat, lon)
    while h > 0:
        lat, lon = step_xy(lat, lon, ws, wd, dt, reverse=True)
        h -= v_vert * dt
        traj.append({"lat": lat, "lon": lon, "alt": max(h, 0)})
    return JSONResponse({"trajectory": traj, "src": src})

@app.post("/trajectory_t3r")
async def trajectory_t3r(req: Request):
    d = await req.json()
    lat, lon, alt, spd = d["lat"], d["lon"], d["altitude"], d["speed"]
    mass = 55.0
    v_vert = spd if spd > 0 else 2.5
    dt = 15
    h = alt
    traj = []
    ws, wd, src = get_wind(lat, lon)
    while h > 0:
        lat, lon = step_xy(lat, lon, ws, wd, dt, reverse=True)
        h -= v_vert * dt * (1 + 0.0001 * (mass - 55))
        traj.append({"lat": lat, "lon": lon, "alt": max(h, 0)})
    return JSONResponse({"trajectory": traj, "src": src})

# ===== Vėjo gridas žemėlapiui =====
@app.post("/windgrid")
async def windgrid(req: Request):
    d = await req.json()
    north, south, east, west = map(float, (d["north"], d["south"], d["east"], d["west"]))
    lat_step = (north - south) / 6
    lon_step = (east - west) / 6
    points = []
    for iy in range(7):
        lat = south + iy * lat_step
        for ix in range(7):
            lon = west + ix * lon_step
            ws, wd, src = get_wind(lat, lon)
            points.append({"lat": lat, "lon": lon, "dir_deg": wd, "speed_ms": ws, "src": src})
    return JSONResponse({"points": points})

# ===== Root =====
@app.get("/")
async def root():
    return {"message": "Serveris veikia! Atidaryk /static/index.html"}
