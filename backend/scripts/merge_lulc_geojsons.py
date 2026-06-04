"""
Merge individual ESA LULC GeoJSON files (exported from GEE)
into a single lulc_esa.geojson.

Usage:
  Place all AP_ESA_LULC_*.geojson files in backend/data/gee_exports/
  then run:
    python backend/scripts/merge_lulc_geojsons.py
"""

import geopandas as gpd
from pathlib import Path

INPUT_DIR = Path(__file__).parent.parent / "data" / "gee_exports"
OUT_FILE = Path(__file__).parent.parent / "data" / "lulc_esa.geojson"

ESA_COLORS = {
    10: "#006400",
    20: "#ffbb22",
    30: "#ffff4c",
    40: "#f096ff",
    50: "#fa0000",
    60: "#b4b4b4",
    80: "#0064c8",
    90: "#0096a0",
    95: "#00cf75",
}


def merge_geojsons():
    files = list(INPUT_DIR.glob("AP_ESA_LULC_*.geojson"))
    if not files:
        print(f"No GeoJSON files found in {INPUT_DIR}")
        print("  Expected files like: AP_ESA_LULC_Cropland.geojson")
        return

    print(f"Found {len(files)} LULC class files:")
    gdfs = []
    for f in sorted(files):
        gdf = gpd.read_file(str(f))
        print(f"  {f.name}: {len(gdf)} features")
        # Add color if not present
        if "class_value" in gdf.columns:
            gdf["color"] = gdf["class_value"].map(lambda v: ESA_COLORS.get(int(v), "#888888"))
        gdfs.append(gdf)

    merged = gpd.pd.concat(gdfs, ignore_index=True)
    merged = merged.to_crs("EPSG:4326")

    # Simplify for web rendering
    merged["geometry"] = merged["geometry"].simplify(tolerance=0.001, preserve_topology=True)
    merged = merged[~merged.geometry.is_empty]

    merged.to_file(str(OUT_FILE), driver="GeoJSON")
    size_kb = round(OUT_FILE.stat().st_size / 1024, 1)
    print(f"\n✅ Merged {len(merged)} features → {OUT_FILE.name} ({size_kb} KB)")


if __name__ == "__main__":
    merge_geojsons()
