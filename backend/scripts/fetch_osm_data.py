"""
Fetch Andhra Pradesh OSM data:
  - State boundary
  - District boundaries (admin_level=5)
  - Power transmission lines
  - Substations
  - Major roads (motorway, trunk, primary, secondary)

Usage:
  pip install osmnx geopandas shapely
  python backend/scripts/fetch_osm_data.py
"""

import os
import json
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.geometry import mapping

OUTPUT = Path(__file__).parent.parent / "data"
OUTPUT.mkdir(exist_ok=True)

PLACE = "Andhra Pradesh, India"


def save_geojson(gdf: gpd.GeoDataFrame, filename: str, label: str):
    """Simplify, drop nulls, save as GeoJSON."""
    gdf = gdf.copy()
    # Simplify geometry for web display (tolerance ~100 m at equator)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.001, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty]
    gdf = gdf.to_crs("EPSG:4326")
    out_path = OUTPUT / filename
    gdf.to_file(str(out_path), driver="GeoJSON")
    size_kb = round(out_path.stat().st_size / 1024, 1)
    print(f"  ✅ {label}: {len(gdf)} features — {size_kb} KB → {filename}")


def fetch_state_boundary():
    print("\n[1/5] Fetching AP state boundary...")
    gdf = ox.geocode_to_gdf(PLACE)
    gdf = gdf[["display_name", "geometry"]]
    gdf["name"] = "Andhra Pradesh"
    save_geojson(gdf, "ap_boundary.geojson", "State boundary")


def fetch_districts():
    print("\n[2/5] Fetching district boundaries (admin_level=5)...")
    tags = {"admin_level": "5", "boundary": "administrative"}
    gdf = ox.features_from_place(PLACE, tags=tags)
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    # Keep useful columns only
    keep = [c for c in ["name", "name:en", "geometry"] if c in gdf.columns]
    gdf = gdf[keep].reset_index(drop=True)
    save_geojson(gdf, "ap_districts.geojson", "Districts")


def fetch_power_lines():
    print("\n[3/5] Fetching OSM power lines...")
    tags = {"power": ["line", "minor_line"]}
    gdf = ox.features_from_place(PLACE, tags=tags)
    gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    keep = [c for c in ["name", "voltage", "cables", "operator", "geometry"] if c in gdf.columns]
    gdf = gdf[keep].reset_index(drop=True)
    # Convert voltage to numeric for styling
    if "voltage" in gdf.columns:
        gdf["voltage"] = (
            gdf["voltage"]
            .astype(str)
            .str.extract(r"(\d+)", expand=False)
            .astype(float, errors="ignore")
        )
    save_geojson(gdf, "power_lines.geojson", "Power lines")


def fetch_substations():
    print("\n[4/5] Fetching OSM substations...")
    tags = {"power": "substation"}
    gdf = ox.features_from_place(PLACE, tags=tags)
    # Substations can be polygons or points; convert polygons to centroids for display
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: g.centroid if g.geom_type in ["Polygon", "MultiPolygon"] else g
    )
    keep = [c for c in ["name", "voltage", "substation", "operator", "geometry"] if c in gdf.columns]
    gdf = gdf[keep].reset_index(drop=True)
    save_geojson(gdf, "substations.geojson", "Substations")


def fetch_roads():
    print("\n[5/5] Fetching OSM major roads...")
    tags = {"highway": ["motorway", "trunk", "primary", "secondary"]}
    gdf = ox.features_from_place(PLACE, tags=tags)
    gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    keep = [c for c in ["name", "highway", "ref", "maxspeed", "geometry"] if c in gdf.columns]
    gdf = gdf[keep].reset_index(drop=True)
    save_geojson(gdf, "roads.geojson", "Roads")


if __name__ == "__main__":
    print("═" * 50)
    print("  AP OSM Data Fetcher")
    print("  Place:", PLACE)
    print("  Output:", OUTPUT)
    print("═" * 50)

    fetch_state_boundary()
    fetch_districts()
    fetch_power_lines()
    fetch_substations()
    fetch_roads()

    print("\n🎉 All OSM data fetched successfully!")
    print(f"   Files saved to: {OUTPUT}")
