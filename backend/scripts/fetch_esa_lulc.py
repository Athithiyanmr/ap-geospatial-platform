"""
Step 3: Fetch ESA WorldCover 2021 LULC clipped to your AOI

Reads: backend/data/aoi_config.json  (created by convert_shapefiles.py)
       backend/data/aoi_boundary.geojson
Outputs:
  backend/data/lulc_esa.geojson

Usage:
  python backend/scripts/fetch_esa_lulc.py

Note: Downloads COG tiles from Microsoft Planetary Computer (free, no API key).
      For Kadapa district, this takes ~3-5 minutes.
"""

import json
import sys
import os
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge as rasterio_merge
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape, mapping
import pystac_client
import planetary_computer

DATA_DIR      = Path(__file__).parent.parent / "data"
CONFIG_FILE   = DATA_DIR / "aoi_config.json"
BOUNDARY_FILE = DATA_DIR / "aoi_boundary.geojson"
OUT_FILE      = DATA_DIR / "lulc_esa.geojson"

ESA_CLASSES = {
    10:  {"label": "Tree cover",        "color": "#006400"},
    20:  {"label": "Shrubland",         "color": "#ffbb22"},
    30:  {"label": "Grassland",         "color": "#ffff4c"},
    40:  {"label": "Cropland",          "color": "#f096ff"},
    50:  {"label": "Built-up",          "color": "#fa0000"},
    60:  {"label": "Bare / sparse veg", "color": "#b4b4b4"},
    80:  {"label": "Water bodies",      "color": "#0064c8"},
    90:  {"label": "Herbaceous wetland","color": "#0096a0"},
    95:  {"label": "Mangroves",         "color": "#00cf75"},
}


def compat_union(gdf):
    """Works on all geopandas versions — unary_union < 0.14, union_all >= 0.14."""
    try:
        return gdf.geometry.union_all()
    except AttributeError:
        return gdf.geometry.unary_union


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print("❌ aoi_config.json not found.")
        print("   Run first: python backend/scripts/convert_shapefiles.py")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_aoi_geometry():
    gdf = gpd.read_file(str(BOUNDARY_FILE)).to_crs("EPSG:4326")
    return [mapping(geom) for geom in gdf.geometry], gdf


def fetch_tiles(bbox: list):
    print("  Connecting to Planetary Computer STAC...")
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    search = catalog.search(collections=["esa-worldcover"], bbox=bbox)
    items = list(search.items())
    print(f"  Found {len(items)} ESA WorldCover tile(s) for AOI")
    if not items:
        print("  ❌ No tiles found. Check your bbox.")
        sys.exit(1)
    return items


def download_and_clip(items, bbox: list, aoi_geoms: list):
    tmp_files = []
    src_files = []

    for item in items:
        href = item.assets["map"].href
        tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        tmp_files.append(tmp.name)
        tmp.close()
        print(f"  ⬇️  Downloading: {item.id}")
        urllib.request.urlretrieve(href, tmp.name)
        src_files.append(rasterio.open(tmp.name))

    print("  Merging tiles...")
    merged_data, merged_transform = rasterio_merge(
        src_files,
        bounds=(bbox[0], bbox[1], bbox[2], bbox[3])
    )
    crs = src_files[0].crs

    for src in src_files:
        src.close()
    for f in tmp_files:
        try:
            os.unlink(f)
        except Exception:
            pass

    return merged_data[0], merged_transform, crs


def vectorise_and_clip(data, transform, crs, aoi_gdf):
    print("  Vectorising raster (this takes 2-5 min for district scale)...")
    features = []
    mask_arr = data != 0

    for geom, val in shapes(data, mask=mask_arr, transform=transform):
        class_val = int(val)
        if class_val in ESA_CLASSES:
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "class_value": class_val,
                    "class_label": ESA_CLASSES[class_val]["label"],
                    "color": ESA_CLASSES[class_val]["color"],
                },
            })

    print(f"  Raw polygons generated: {len(features)}")

    gdf = gpd.GeoDataFrame.from_features(features, crs=crs)
    gdf = gdf.to_crs("EPSG:4326")

    # ✅ Fixed: compatible with all geopandas versions
    print("  Clipping to AOI boundary...")
    aoi_union = compat_union(aoi_gdf)
    gdf = gdf[gdf.geometry.intersects(aoi_union)].copy()
    gdf["geometry"] = gdf["geometry"].intersection(aoi_union)
    gdf = gdf[~gdf.geometry.is_empty].copy()

    print("  Dissolving by LULC class...")
    gdf_dissolved = gdf.dissolve(by="class_value").reset_index()
    gdf_dissolved["class_label"] = gdf_dissolved["class_value"].map(
        lambda v: ESA_CLASSES.get(v, {}).get("label", "Unknown")
    )
    gdf_dissolved["color"] = gdf_dissolved["class_value"].map(
        lambda v: ESA_CLASSES.get(v, {}).get("color", "#888888")
    )

    gdf_dissolved["geometry"] = gdf_dissolved["geometry"].simplify(
        tolerance=0.001, preserve_topology=True
    )
    gdf_dissolved = gdf_dissolved[~gdf_dissolved.geometry.is_empty]

    return gdf_dissolved


if __name__ == "__main__":
    print("=" * 50)
    print("  ESA WorldCover Fetcher — AOI Clipped")
    print("=" * 50)

    cfg  = load_config()
    bbox = cfg["bbox"]
    print(f"  AOI : {cfg['name']}")
    print(f"  BBox: {bbox}")

    aoi_geoms, aoi_gdf = load_aoi_geometry()

    print("\n[1/3] Searching ESA WorldCover tiles...")
    items = fetch_tiles(bbox)

    print("\n[2/3] Downloading & merging tiles...")
    data, transform, crs = download_and_clip(items, bbox, aoi_geoms)

    print("\n[3/3] Vectorising & clipping to AOI...")
    gdf_final = vectorise_and_clip(data, transform, crs, aoi_gdf)

    gdf_final.to_file(str(OUT_FILE), driver="GeoJSON")
    size_kb = round(OUT_FILE.stat().st_size / 1024, 1)
    print(f"\n  ✅ {len(gdf_final)} LULC classes → lulc_esa.geojson ({size_kb} KB)")

    print("\n  LULC class breakdown:")
    for _, row in gdf_final.iterrows():
        print(f"    [{row['class_value']:>3}] {row['class_label']}")

    print(f"\n🎉 ESA LULC ready for {cfg['name']}!")
    print("   Next: docker-compose up --build")
