"""
Step 1: Convert all local vector files → GeoJSON

Supported formats: .shp (Shapefile) and .gpkg (GeoPackage)

Folder structure expected in backend/input_shapefiles/:
  kadapa_boundary.shp/.gpkg    ← AOI boundary (required)
  solar_parks.shp/.gpkg        ← Solar park boundaries
  wind_turbines.shp/.gpkg      ← Wind turbine points or polygons
  re_combined.shp/.gpkg        ← Combined solar+wind RE boundaries

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

# Supported vector file extensions
VECTOR_EXTS = [".shp", ".gpkg"]

# Map: output filename → keyword to search in input filename
# Edit keywords if your filenames use different naming
RENEWABLE_LAYERS = {
    "solar_parks.geojson":   "solar",     # matches solar_parks.gpkg, solar.shp, etc.
    "wind_turbines.geojson": "wind",      # matches wind_turbines.gpkg, wind.shp, etc.
    "re_combined.geojson":   "combined",  # matches re_combined.gpkg, combined.shp, etc.
}


def find_vector_file(keyword: str) -> Path | None:
    """
    Find a vector file (.shp or .gpkg) whose stem contains keyword.
    .gpkg is preferred over .shp if both exist.
    """
    matches = []
    for ext in VECTOR_EXTS:
        matches += [f for f in SHP_DIR.glob(f"*{ext}") if keyword.lower() in f.stem.lower()]

    if not matches:
        return None

    # Prefer .gpkg over .shp
    gpkg_matches = [f for f in matches if f.suffix == ".gpkg"]
    chosen = gpkg_matches[0] if gpkg_matches else matches[0]

    if len(matches) > 1:
        print(f"  ⚠️  Multiple matches for '{keyword}': {[m.name for m in matches]}")
        print(f"       Using: {chosen.name}")
    return chosen


def find_aoi_file() -> Path:
    """
    Find AOI boundary file — any vector file NOT matching RE keywords.
    Prefers .gpkg over .shp.
    """
    re_keywords = ["solar", "wind", "combined", "turbine", "park"]
    all_files = []
    for ext in VECTOR_EXTS:
        all_files += list(SHP_DIR.glob(f"*{ext}"))

    candidates = [f for f in all_files if not any(kw in f.stem.lower() for kw in re_keywords)]
    if not candidates:
        candidates = all_files   # fallback: use any file
    if not candidates:
        print(f"❌ No vector files found in {SHP_DIR}")
        print(f"   Supported: .shp, .gpkg")
        sys.exit(1)

    # Prefer .gpkg
    gpkg_candidates = [f for f in candidates if f.suffix == ".gpkg"]
    chosen = gpkg_candidates[0] if gpkg_candidates else candidates[0]
    print(f"  ✅ AOI file: {chosen.name}")
    return chosen


def read_vector(filepath: Path) -> gpd.GeoDataFrame:
    """Read .shp or .gpkg into GeoDataFrame."""
    if filepath.suffix == ".gpkg":
        # GPKG may have multiple layers — read first layer by default
        import fiona
        layers = fiona.listlayers(str(filepath))
        if len(layers) > 1:
            print(f"  ⚠️  GPKG has {len(layers)} layers: {layers}")
            print(f"       Reading first layer: '{layers[0]}'")
        return gpd.read_file(str(filepath), layer=layers[0])
    else:
        return gpd.read_file(str(filepath))


def compat_union(gdf):
    """Compatible unary union — works on all geopandas versions."""
    try:
        return gdf.geometry.union_all()
    except AttributeError:
        return gdf.geometry.unary_union


def convert_aoi() -> dict:
    print("\n[AOI] Converting district boundary...")
    f = find_aoi_file()
    gdf = read_vector(f).to_crs("EPSG:4326")
    print(f"  Format  : {f.suffix.upper()}")
    print(f"  CRS     : {gdf.crs}")
    print(f"  Features: {len(gdf)}")
    print(f"  Geometry: {gdf.geometry.geom_type.unique().tolist()}")

    if len(gdf) > 1:
        print(f"  Dissolving {len(gdf)} features → single AOI...")
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


def convert_re_layer(out_filename: str, keyword: str, aoi_geom, label: str):
    """Convert one RE layer (.shp or .gpkg) → clipped GeoJSON."""
    print(f"\n[RE] Converting {label}...")
    filepath = find_vector_file(keyword)

    if filepath is None:
        print(f"  ⚠️  No file found matching keyword '{keyword}' — skipping")
        print(f"       Expected: *{keyword}*.shp or *{keyword}*.gpkg in {SHP_DIR}")
        return

    print(f"  Found: {filepath.name} ({filepath.suffix.upper()})")
    gdf = read_vector(filepath).to_crs("EPSG:4326")
    print(f"  Features: {len(gdf)} | Geometry: {gdf.geometry.geom_type.unique().tolist()}")

    # Clip to AOI
    before = len(gdf)
    gdf = gdf[gdf.geometry.intersects(aoi_geom)].copy()
    gdf["geometry"] = gdf["geometry"].intersection(aoi_geom)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    print(f"  Clipped: {before} → {len(gdf)} features within {AOI_NAME}")

    if len(gdf) == 0:
        print(f"  ⚠️  No features within AOI — check if your data covers {AOI_NAME} district")
        return

    gdf["layer_type"] = label
    gdf["geometry"]   = gdf["geometry"].simplify(tolerance=0.0005, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty].copy()

    out = OUTPUT / out_filename
    gdf.to_file(str(out), driver="GeoJSON")
    print(f"  ✅ {out_filename} ({round(out.stat().st_size/1024,1)} KB)")


if __name__ == "__main__":
    print("=" * 55)
    print(f"  Vector Converter — {AOI_NAME} District")
    print(f"  Supported formats: .shp, .gpkg")
    print("=" * 55)

    cfg = convert_aoi()

    aoi_gdf  = gpd.read_file(str(OUTPUT / "aoi_boundary.geojson"))
    aoi_geom = compat_union(aoi_gdf)

    print("\n" + "─" * 55)
    print("  Renewable Energy Layers")
    print("─" * 55)

    label_map = {
        "solar_parks.geojson":   "Solar Parks",
        "wind_turbines.geojson": "Wind Turbines",
        "re_combined.geojson":   "RE Combined Boundary",
    }
    for out_file, keyword in RENEWABLE_LAYERS.items():
        convert_re_layer(out_file, keyword, aoi_geom, label_map[out_file])

    print("\n" + "=" * 55)
    print("🎉 All conversions complete!")
    print("   Next: docker-compose up --build")
    print("=" * 55)
