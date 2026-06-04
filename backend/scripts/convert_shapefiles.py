"""
Step 1: Convert all local shapefiles → GeoJSON

Folder structure expected in backend/input_shapefiles/:
  kadapa_boundary.*          ← AOI boundary (required)
  solar_parks.*              ← Solar park boundaries
  wind_turbines.*            ← Wind turbine points or polygons
  re_combined_boundary.*     ← Combined solar+wind RE boundaries

Run: python backend/scripts/convert_shapefiles.py

Outputs in backend/data/:
  aoi_boundary.geojson
  aoi_config.json
  solar_parks.geojson
  wind_turbines.geojson
  re_combined.geojson
"""

import geopandas as gpd
from pathlib import Path
import json
import sys

# ─────────────────────────────────────────────
SHP_DIR  = Path(__file__).parent.parent / "input_shapefiles"
OUTPUT   = Path(__file__).parent.parent / "data"
OUTPUT.mkdir(exist_ok=True)
AOI_NAME = "Kadapa"

# ─────────────────────────────────────────────
# Map: output filename → search keyword in input filename
# Edit these if your filenames are different
RENEWABLE_LAYERS = {
    "solar_parks.geojson":   "solar",      # matches solar_parks.shp, solar.shp, etc.
    "wind_turbines.geojson": "wind",       # matches wind_turbines.shp, wind.shp, etc.
    "re_combined.geojson":   "combined",   # matches re_combined.shp, combined.shp, etc.
}


def find_shp_by_keyword(keyword: str) -> Path | None:
    """Find a .shp file whose name contains the keyword (case-insensitive)."""
    matches = [f for f in SHP_DIR.glob("*.shp") if keyword.lower() in f.stem.lower()]
    if not matches:
        return None
    if len(matches) > 1:
        print(f"  ⚠️  Multiple matches for '{keyword}': {[m.name for m in matches]}, using first")
    return matches[0]


def find_aoi_shp() -> Path:
    """Find the AOI boundary shapefile — any .shp not matching renewable keywords."""
    all_shps = list(SHP_DIR.glob("*.shp"))
    re_keywords = ["solar", "wind", "combined", "turbine", "park"]
    candidates = [f for f in all_shps if not any(kw in f.stem.lower() for kw in re_keywords)]
    if not candidates:
        # fallback: use first shp
        candidates = all_shps
    if not candidates:
        print(f"❌ No .shp files found in {SHP_DIR}")
        sys.exit(1)
    print(f"  ✅ AOI shapefile : {candidates[0].name}")
    return candidates[0]


def aoi_union(gdf):
    """Compatible unary union across geopandas versions."""
    try:
        return gdf.geometry.union_all()
    except AttributeError:
        return gdf.geometry.unary_union


def convert_aoi() -> dict:
    print("\n[AOI] Converting district boundary...")
    shp = find_aoi_shp()
    gdf = gpd.read_file(str(shp)).to_crs("EPSG:4326")
    print(f"  CRS: {gdf.crs} | Features: {len(gdf)} | Geom: {gdf.geometry.geom_type.unique().tolist()}")

    if len(gdf) > 1:
        gdf = gdf.dissolve().reset_index(drop=True)

    gdf["name"]     = AOI_NAME
    gdf["district"] = AOI_NAME
    out = OUTPUT / "aoi_boundary.geojson"
    gdf[["name", "district", "geometry"]].to_file(str(out), driver="GeoJSON")
    print(f"  ✅ aoi_boundary.geojson ({round(out.stat().st_size/1024,1)} KB)")

    bbox = gdf.total_bounds
    cfg = {
        "name": AOI_NAME,
        "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
        "center": [float((bbox[1]+bbox[3])/2), float((bbox[0]+bbox[2])/2)],
        "zoom": 10
    }
    with open(OUTPUT / "aoi_config.json", "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"  ✅ aoi_config.json saved")
    print(f"  📦 BBox  : {[round(x,4) for x in cfg['bbox']]}")
    print(f"  📍 Center: {cfg['center'][0]:.4f}°N, {cfg['center'][1]:.4f}°E")
    return cfg


def convert_renewable_layer(out_filename: str, keyword: str, aoi_geom, label: str):
    """Convert one renewable energy shapefile → clipped GeoJSON."""
    print(f"\n[RE] Converting {label}...")
    shp = find_shp_by_keyword(keyword)

    if shp is None:
        print(f"  ⚠️  No shapefile found matching keyword '{keyword}' — skipping")
        print(f"       Expected a file like: *{keyword}*.shp in {SHP_DIR}")
        return

    print(f"  Found: {shp.name}")
    gdf = gpd.read_file(str(shp)).to_crs("EPSG:4326")
    print(f"  Features: {len(gdf)} | Geom: {gdf.geometry.geom_type.unique().tolist()}")

    # Clip to AOI
    before = len(gdf)
    gdf = gdf[gdf.geometry.intersects(aoi_geom)].copy()
    gdf["geometry"] = gdf["geometry"].intersection(aoi_geom)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    print(f"  Clipped: {before} → {len(gdf)} features within Kadapa")

    if len(gdf) == 0:
        print(f"  ⚠️  No features within AOI — check if your data covers Kadapa district")
        return

    # Add type tag
    gdf["layer_type"] = label

    # Simplify for web
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.0005, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty].copy()

    out = OUTPUT / out_filename
    gdf.to_file(str(out), driver="GeoJSON")
    print(f"  ✅ {out_filename} ({round(out.stat().st_size/1024,1)} KB)")


if __name__ == "__main__":
    print("=" * 55)
    print(f"  Shapefile Converter — {AOI_NAME} District")
    print("=" * 55)

    # Step 1: AOI boundary
    cfg = convert_aoi()

    # Load AOI geometry for clipping
    aoi_gdf = gpd.read_file(str(OUTPUT / "aoi_boundary.geojson"))
    aoi_geom = aoi_union(aoi_gdf)

    # Step 2: Renewable energy layers
    print("\n" + "─" * 55)
    print("  Renewable Energy Layers")
    print("─" * 55)
    for out_file, keyword in RENEWABLE_LAYERS.items():
        label_map = {
            "solar_parks.geojson":   "Solar Parks",
            "wind_turbines.geojson": "Wind Turbines",
            "re_combined.geojson":   "RE Combined Boundary",
        }
        convert_renewable_layer(out_file, keyword, aoi_geom, label_map[out_file])

    print("\n" + "=" * 55)
    print("🎉 All conversions complete!")
    print("   Next steps:")
    print("   1. python backend/scripts/fetch_osm_data.py")
    print("   2. python backend/scripts/fetch_esa_lulc.py")
    print("   3. docker-compose up --build")
    print("=" * 55)
