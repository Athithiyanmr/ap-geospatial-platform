"""
Step 2: Fetch OSM data clipped to your AOI (Kadapa district)

Reads: backend/data/aoi_config.json  (created by convert_shapefiles.py)
Outputs:
  backend/data/power_lines.geojson
  backend/data/substations.geojson
  backend/data/roads.geojson

Usage:
  python backend/scripts/fetch_osm_data.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import osmnx as ox

DATA_DIR      = Path(__file__).parent.parent / "data"
CONFIG_FILE   = DATA_DIR / "aoi_config.json"
BOUNDARY_FILE = DATA_DIR / "aoi_boundary.geojson"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print("❌ aoi_config.json not found.")
        print("   Run first: python backend/scripts/convert_shapefiles.py")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    print(f"  AOI  : {cfg['name']}")
    print(f"  BBox : {cfg['bbox']}")
    return cfg


def load_aoi_geometry():
    """Load AOI polygon — compatible with all geopandas versions."""
    gdf = gpd.read_file(str(BOUNDARY_FILE))
    # unary_union works on all geopandas versions; union_all requires >=0.14
    try:
        return gdf.geometry.union_all()
    except AttributeError:
        return gdf.geometry.unary_union


def bbox_to_osmnx(bbox: list) -> tuple:
    """Convert [W, S, E, N] → osmnx (N, S, E, W)."""
    return (bbox[3], bbox[1], bbox[2], bbox[0])


def save_geojson(gdf: gpd.GeoDataFrame, filename: str, label: str):
    gdf = gdf.copy().to_crs("EPSG:4326")
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.0005, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    out = DATA_DIR / filename
    gdf.to_file(str(out), driver="GeoJSON")
    size_kb = round(out.stat().st_size / 1024, 1)
    print(f"  ✅ {label}: {len(gdf)} features → {filename} ({size_kb} KB)")


def fetch_power_lines(bbox: list, aoi_geom):
    print("\n[1/3] Fetching power lines...")
    tags = {"power": ["line", "minor_line"]}
    try:
        gdf = ox.features_from_bbox(*bbox_to_osmnx(bbox), tags=tags)
        gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
        gdf = gdf[gdf.geometry.intersects(aoi_geom)].copy()
        keep = [c for c in ["name", "voltage", "cables", "operator", "geometry"] if c in gdf.columns]
        gdf = gdf[keep].reset_index(drop=True)
        if "voltage" in gdf.columns:
            gdf["voltage"] = (
                gdf["voltage"].astype(str)
                .str.extract(r"(\d+)", expand=False)
                .astype(float, errors="ignore")
            )
        save_geojson(gdf, "power_lines.geojson", "Power lines")
    except Exception as e:
        print(f"  ⚠️  Power lines fetch failed: {e}")


def fetch_substations(bbox: list, aoi_geom):
    print("\n[2/3] Fetching substations...")
    tags = {"power": "substation"}
    try:
        gdf = ox.features_from_bbox(*bbox_to_osmnx(bbox), tags=tags)
        gdf = gdf.copy()
        gdf["geometry"] = gdf["geometry"].apply(
            lambda g: g.centroid if g.geom_type in ["Polygon", "MultiPolygon"] else g
        )
        gdf = gdf[gdf.geometry.within(aoi_geom)].copy()
        keep = [c for c in ["name", "voltage", "substation", "operator", "geometry"] if c in gdf.columns]
        gdf = gdf[keep].reset_index(drop=True)
        save_geojson(gdf, "substations.geojson", "Substations")
    except Exception as e:
        print(f"  ⚠️  Substations fetch failed: {e}")


def fetch_roads(bbox: list, aoi_geom):
    print("\n[3/3] Fetching major roads...")
    tags = {"highway": ["motorway", "trunk", "primary", "secondary"]}
    try:
        gdf = ox.features_from_bbox(*bbox_to_osmnx(bbox), tags=tags)
        gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
        gdf = gdf[gdf.geometry.intersects(aoi_geom)].copy()
        keep = [c for c in ["name", "highway", "ref", "maxspeed", "geometry"] if c in gdf.columns]
        gdf = gdf[keep].reset_index(drop=True)
        save_geojson(gdf, "roads.geojson", "Roads")
    except Exception as e:
        print(f"  ⚠️  Roads fetch failed: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("  OSM Data Fetcher — AOI Clipped")
    print("=" * 50)

    cfg     = load_config()
    bbox    = cfg["bbox"]
    aoi_geom = load_aoi_geometry()

    print(f"\n  Clipping all data to: {cfg['name']} boundary\n")

    fetch_power_lines(bbox, aoi_geom)
    fetch_substations(bbox, aoi_geom)
    fetch_roads(bbox, aoi_geom)

    print("\n🎉 OSM data ready!")
    print("   Next: python backend/scripts/fetch_esa_lulc.py")
