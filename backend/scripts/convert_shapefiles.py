"""
Step 1: Convert your local AOI shapefile → GeoJSON

Place your shapefile in: backend/input_shapefiles/
Run: python backend/scripts/convert_shapefiles.py

Outputs:
  backend/data/aoi_boundary.geojson  ← used by all other scripts as clip boundary
"""

import geopandas as gpd
from pathlib import Path
import json
import sys

# ─────────────────────────────────────────────
# CONFIG — update SHP_PATH to your shapefile
# ─────────────────────────────────────────────
SHP_PATH = Path(__file__).parent.parent / "input_shapefiles"   # folder
OUTPUT   = Path(__file__).parent.parent / "data"
OUTPUT.mkdir(exist_ok=True)

AOI_NAME = "Kadapa"   # used in frontend title + popups


def find_shapefile(folder: Path) -> Path:
    """Auto-detect the first .shp file in the folder."""
    shps = list(folder.glob("*.shp"))
    if not shps:
        print(f"❌ No .shp files found in: {folder}")
        print(f"   Please place your shapefile in: {folder}")
        sys.exit(1)
    if len(shps) > 1:
        print(f"⚠️  Multiple .shp files found, using: {shps[0].name}")
        print(f"   Others: {[s.name for s in shps[1:]]}")
    else:
        print(f"✅ Found shapefile: {shps[0].name}")
    return shps[0]


def convert_boundary():
    shp_file = find_shapefile(SHP_PATH)

    print(f"\n[1/3] Reading shapefile...")
    gdf = gpd.read_file(str(shp_file))
    print(f"  CRS detected : {gdf.crs}")
    print(f"  Features     : {len(gdf)}")
    print(f"  Columns      : {list(gdf.columns)}")
    print(f"  Geometry type: {gdf.geometry.geom_type.unique().tolist()}")

    print(f"\n[2/3] Reprojecting to EPSG:4326...")
    gdf = gdf.to_crs("EPSG:4326")

    # Dissolve to single polygon if multiple features
    if len(gdf) > 1:
        print(f"  Dissolving {len(gdf)} features into single AOI boundary...")
        gdf = gdf.dissolve().reset_index(drop=True)

    # Add name property
    gdf["name"] = AOI_NAME
    gdf["district"] = AOI_NAME

    print(f"\n[3/3] Saving GeoJSON...")
    out_path = OUTPUT / "aoi_boundary.geojson"
    gdf[["name", "district", "geometry"]].to_file(str(out_path), driver="GeoJSON")
    size_kb = round(out_path.stat().st_size / 1024, 1)
    print(f"  ✅ Saved → aoi_boundary.geojson ({size_kb} KB)")

    # Print bounding box for reference
    bbox = gdf.total_bounds  # [minx, miny, maxx, maxy]
    print(f"\n  📦 Bounding Box:")
    print(f"     West : {bbox[0]:.4f}")
    print(f"     South: {bbox[1]:.4f}")
    print(f"     East : {bbox[2]:.4f}")
    print(f"     North: {bbox[3]:.4f}")
    print(f"     Center: {(bbox[1]+bbox[3])/2:.4f}°N, {(bbox[0]+bbox[2])/2:.4f}°E")

    # Save bbox as config for other scripts to read
    bbox_config = {
        "name": AOI_NAME,
        "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
        "center": [float((bbox[1]+bbox[3])/2), float((bbox[0]+bbox[2])/2)],
        "zoom": 10
    }
    config_path = OUTPUT / "aoi_config.json"
    with open(config_path, "w") as f:
        json.dump(bbox_config, f, indent=2)
    print(f"  ✅ Saved → aoi_config.json (used by all fetch scripts)")

    return bbox_config


if __name__ == "__main__":
    print("=" * 50)
    print(f"  AOI Shapefile Converter")
    print(f"  District: {AOI_NAME}")
    print("=" * 50)
    cfg = convert_boundary()
    print(f"\n🎉 Done! Now run:")
    print(f"   python backend/scripts/fetch_osm_data.py")
    print(f"   python backend/scripts/fetch_esa_lulc.py")
