# AP Geospatial Platform

A production-grade geospatial web platform for **Andhra Pradesh** featuring:

- 🗺️ Real AP state + district boundaries (from OSM via `osmnx`)
- 🌿 **ESA WorldCover** land use / land cover (2021, 10 m)
- ⚡ **OSM Power Lines** & **Substations** (with voltage classification)
- 🛣️ **OSM Roads** (motorway → secondary)
- 🐳 Fully containerised with **Docker + Docker Compose**
- ⚙️ **FastAPI** REST backend serving GeoJSON endpoints
- 🍃 **Leaflet.js** interactive frontend with layer toggles & legend

---

## Quick Start

### 1. Fetch Data (run once)
```bash
cd backend
pip install -r requirements.txt
python scripts/fetch_osm_data.py
python scripts/fetch_esa_lulc.py
```

> **Alternative for ESA LULC**: Use the provided Google Earth Engine script at
> `backend/scripts/gee_export_lulc.js` to export LULC GeoJSON directly to Drive,
> then place the files in `backend/data/`.

### 2. Start with Docker
```bash
docker-compose up --build
```

Visit **http://localhost:8000**

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/boundary` | AP state boundary GeoJSON |
| `GET /api/districts` | All 26 district boundaries |
| `GET /api/lulc` | ESA WorldCover LULC polygons |
| `GET /api/power-lines` | OSM transmission lines |
| `GET /api/substations` | OSM substations |
| `GET /api/roads` | OSM major roads |
| `GET /api/stats` | Layer statistics summary |

---

## ESA WorldCover Classes

| Code | Class | Color |
|---|---|---|
| 10 | Tree cover | `#006400` |
| 20 | Shrubland | `#ffbb22` |
| 30 | Grassland | `#ffff4c` |
| 40 | Cropland | `#f096ff` |
| 50 | Built-up | `#fa0000` |
| 60 | Bare / sparse vegetation | `#b4b4b4` |
| 80 | Water bodies | `#0064c8` |
| 90 | Herbaceous wetland | `#0096a0` |
| 95 | Mangroves | `#00cf75` |

---

## Project Structure

```
ap-geospatial-platform/
├── backend/
│   ├── app.py                   # FastAPI server
│   ├── requirements.txt
│   ├── data/                    # GeoJSON data files (gitignored, fetch locally)
│   │   └── .gitkeep
│   └── scripts/
│       ├── fetch_osm_data.py    # OSM boundary + power + roads
│       ├── fetch_esa_lulc.py    # ESA WorldCover via Planetary Computer
│       └── gee_export_lulc.js   # Alternative: GEE export script
├── frontend/
│   └── index.html               # Leaflet.js interactive map
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Development (without Docker)

```bash
cd backend
uvicorn app:app --reload --port 8000
```

---

## Credits
- Boundary data: © OpenStreetMap contributors
- Land cover: ESA WorldCover 2021 (v200) — © ESA / Vito
- Power / road data: © OpenStreetMap contributors (ODbL)
