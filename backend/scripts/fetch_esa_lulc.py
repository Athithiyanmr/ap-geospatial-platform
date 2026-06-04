"""
Fetch ESA WorldCover 2021 (v200) for Andhra Pradesh
via Microsoft Planetary Computer STAC API.

Outputs: backend/data/lulc_esa.geojson
  — Vectorised polygons per LULC class, clipped to AP boundary.

Usage:
  pip install pystac-client planetary-computer rioxarray rasterio geopandas
  python backend/scripts/fetch_esa_lulc.py

Note: For large states, the raster-to-vector step can take 5-15 minutes.
Alternative: Use gee_export_lulc.js to export from Google Earth Engine.
"""

import os
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask as rasterio_mask
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape, mapping
import pystac_client
import planetary_computer

OUTPUT = Path(__file__).parent.parent / "data"
BOUNDARY_FILE = OUTPUT / "ap_boundary.geojson"
OUT_FILE = OUTPUT / "lulc_esa.geojson"

# AP bounding box [west, south, east, north]
AP_BBOX = [76.7, 12.6, 84.8, 19.9]

ESA_CLASSES = {
    10: {"label": "Tree cover",            "color": "#006400"},
    20: {"label": "Shrubland",              "color": "#ffbb22"},
    30: {"label": "Grassland",              "color": "#ffff4c"},
    40: {"label": "Cropland",               "color": "#f096ff"},
    50: {"label": "Built-up",               "color": "#fa0000"},
    60: {"label": "Bare / sparse veg",      "color": "#b4b4b4"},
    70: {"label": "Snow and ice",           "color": "#f0f0f0"},
    80: {"label": "Water bodies",           "color": "#0064c8"},
    90: {"label": "Herbaceous wetland",     "color": "#0096a0"},
    95: {"label": "Mangroves",              "color": "#00cf75"},
    100:{"label": "Moss and lichen",        "color": "#fae6a0"},
}


def get_ap_geometry():
    """Load AP boundary geometry for masking."""
    if not BOUNDARY_FILE.exists():
        raise FileNotFoundError(
            "ap_boundary.geojson not found. Run fetch_osm_data.py first."
        )
    gdf = gpd.read_file(str(BOUNDARY_FILE))
    return [mapping(geom) for geom in gdf.geometry]


def fetch_tiles():
    """Search and sign ESA WorldCover tiles from Planetary Computer."""
    print("  Connecting to Planetary Computer STAC...")
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    search = catalog.search(
        collections=["esa-worldcover"],
        bbox=AP_BBOX,
    )
    items = list(search.items())
    print(f"  Found {len(items)} ESA WorldCover tile(s)")
    return items


def download_and_merge(items):
    """Download COG tiles, merge into single raster clipped to AP."""
    import urllib.request, tempfile

    ap_geoms = get_ap_geometry()
    src_files = []
    tmp_files = []

    for item in items:
        href = item.assets["map"].href
        tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        tmp_files.append(tmp.name)
        print(f"  Downloading tile: {item.id} ...")
        urllib.request.urlretrieve(href, tmp.name)
        src_files.append(rasterio.open(tmp.name))

    # Merge all tiles
    print("  Merging tiles...")
    merged_data, merged_transform = merge(src_files, bounds=(
        AP_BBOX[0], AP_BBOX[1], AP_BBOX[2], AP_BBOX[3]
    ))
    merged_crs = src_files[0].crs

    # Close file handles
    for src in src_files:
        src.close()

    return merged_data[0], merged_transform, merged_crs, ap_geoms, tmp_files


def vectorise(data, transform, crs):
    """Convert raster to vector polygons grouped by LULC class."""
    print("  Vectorising raster to polygons (this may take a few minutes)...")
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

    print(f"  Generated {len(features)} polygon features")
    return features


def simplify_and_save(features, crs):
    """Dissolve by class, simplify for web, save GeoJSON."""
    print("  Simplifying and dissolving by class...")
    gdf = gpd.GeoDataFrame.from_features(features, crs=crs)
    gdf = gdf.to_crs("EPSG:4326")

    # Dissolve per class to reduce feature count
    gdf_dissolved = gdf.dissolve(by="class_value").reset_index()
    gdf_dissolved["class_label"] = gdf_dissolved["class_value"].map(
        lambda v: ESA_CLASSES.get(v, {}).get("label", "Unknown")
    )
    gdf_dissolved["color"] = gdf_dissolved["class_value"].map(
        lambda v: ESA_CLASSES.get(v, {}).get("color", "#888888")
    )

    # Simplify geometry for web display (~500 m tolerance)
    gdf_dissolved["geometry"] = gdf_dissolved["geometry"].simplify(
        tolerance=0.005, preserve_topology=True
    )
    gdf_dissolved = gdf_dissolved[~gdf_dissolved.geometry.is_empty]

    gdf_dissolved.to_file(str(OUT_FILE), driver="GeoJSON")
    size_kb = round(OUT_FILE.stat().st_size / 1024, 1)
    print(f"  ✅ Saved {len(gdf_dissolved)} LULC class polygons — {size_kb} KB → lulc_esa.geojson")


if __name__ == "__main__":
    print("═" * 50)
    print("  ESA WorldCover Fetcher (Andhra Pradesh)")
    print("═" * 50)

    items = fetch_tiles()
    data, transform, crs, ap_geoms, tmp_files = download_and_merge(items)
    features = vectorise(data, transform, crs)
    simplify_and_save(features, crs)

    # Cleanup temp files
    import os
    for f in tmp_files:
        try:
            os.unlink(f)
        except Exception:
            pass

    print("\n🎉 ESA LULC data ready!")
