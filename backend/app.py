"""
Kadapa Geospatial Platform — FastAPI Backend
Serves GeoJSON for boundary, ESA LULC, OSM power/roads,
and existing renewable energy sites.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import json
from pathlib import Path

app = FastAPI(
    title="Kadapa Geospatial Platform",
    description="Kadapa district — LULC, power infrastructure, roads & renewable energy sites",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR     = Path(__file__).parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def geojson_response(filename: str):
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found. Run the data prep scripts first.",
        )
    return FileResponse(str(filepath), media_type="application/geo+json")


# ─────────────────────────────────────────────
# Health & Stats
# ─────────────────────────────────────────────
ALL_FILES = {
    "boundary":       "aoi_boundary.geojson",
    "lulc":           "lulc_esa.geojson",
    "power_lines":    "power_lines.geojson",
    "substations":    "substations.geojson",
    "roads":          "roads.geojson",
    "solar_parks":    "solar_parks.geojson",
    "wind_turbines":  "wind_turbines.geojson",
    "re_combined":    "re_combined.geojson",
}


@app.get("/api/health")
async def health():
    status = {k: (DATA_DIR / v).exists() for k, v in ALL_FILES.items()}
    all_ready = all(status.values())
    return JSONResponse(
        content={"status": "ok" if all_ready else "partial", "layers": status},
        status_code=200,
    )


@app.get("/api/stats")
async def get_stats():
    stats = {}
    for name, filename in ALL_FILES.items():
        fp = DATA_DIR / filename
        if fp.exists():
            with open(fp) as f:
                data = json.load(f)
            stats[name] = {
                "features": len(data.get("features", [])),
                "size_kb": round(fp.stat().st_size / 1024, 1),
            }
        else:
            stats[name] = {"features": 0, "size_kb": 0, "missing": True}
    return JSONResponse(content=stats)


# ─────────────────────────────────────────────
# Base Layers
# ─────────────────────────────────────────────
@app.get("/api/boundary",    summary="AOI Boundary")
async def get_boundary():    return geojson_response("aoi_boundary.geojson")

@app.get("/api/lulc",        summary="ESA WorldCover LULC")
async def get_lulc():        return geojson_response("lulc_esa.geojson")

@app.get("/api/power-lines", summary="OSM Power Lines")
async def get_power_lines(): return geojson_response("power_lines.geojson")

@app.get("/api/substations", summary="OSM Substations")
async def get_substations(): return geojson_response("substations.geojson")

@app.get("/api/roads",       summary="OSM Roads")
async def get_roads():       return geojson_response("roads.geojson")


# ─────────────────────────────────────────────
# Renewable Energy Sites
# ─────────────────────────────────────────────
@app.get("/api/solar-parks",   summary="Solar Park Boundaries")
async def get_solar_parks():   return geojson_response("solar_parks.geojson")

@app.get("/api/wind-turbines", summary="Wind Turbine Locations")
async def get_wind_turbines(): return geojson_response("wind_turbines.geojson")

@app.get("/api/re-combined",   summary="Combined RE Site Boundaries")
async def get_re_combined():   return geojson_response("re_combined.geojson")


# ─────────────────────────────────────────────
# Serve frontend — MUST be last
# ─────────────────────────────────────────────
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
