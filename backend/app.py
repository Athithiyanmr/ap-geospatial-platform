"""
AP Geospatial Platform — FastAPI Backend
Serves GeoJSON data for AP boundary, ESA LULC, OSM power/roads.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import json
import os
from pathlib import Path

app = FastAPI(
    title="AP Geospatial Platform",
    description="Andhra Pradesh land cover, power infrastructure & roads",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def geojson_response(filename: str):
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found. Run the fetch scripts first: python scripts/fetch_osm_data.py",
        )
    return FileResponse(str(filepath), media_type="application/geo+json")


@app.get("/api/health")
async def health():
    files = [
        "ap_boundary.geojson",
        "ap_districts.geojson",
        "lulc_esa.geojson",
        "power_lines.geojson",
        "substations.geojson",
        "roads.geojson",
    ]
    status = {f: (DATA_DIR / f).exists() for f in files}
    all_ready = all(status.values())
    return JSONResponse(
        content={"status": "ok" if all_ready else "partial", "data_files": status},
        status_code=200,
    )


@app.get("/api/boundary", summary="AP State Boundary")
async def get_boundary():
    return geojson_response("ap_boundary.geojson")


@app.get("/api/districts", summary="AP District Boundaries")
async def get_districts():
    return geojson_response("ap_districts.geojson")


@app.get("/api/lulc", summary="ESA WorldCover LULC")
async def get_lulc():
    return geojson_response("lulc_esa.geojson")


@app.get("/api/power-lines", summary="OSM Power Transmission Lines")
async def get_power_lines():
    return geojson_response("power_lines.geojson")


@app.get("/api/substations", summary="OSM Substations")
async def get_substations():
    return geojson_response("substations.geojson")


@app.get("/api/roads", summary="OSM Major Roads")
async def get_roads():
    return geojson_response("roads.geojson")


@app.get("/api/stats", summary="Dataset Statistics")
async def get_stats():
    stats = {}
    for name, filename in [
        ("boundary", "ap_boundary.geojson"),
        ("districts", "ap_districts.geojson"),
        ("lulc", "lulc_esa.geojson"),
        ("power_lines", "power_lines.geojson"),
        ("substations", "substations.geojson"),
        ("roads", "roads.geojson"),
    ]:
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


# Serve frontend static files — must be last
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
