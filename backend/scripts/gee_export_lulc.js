/**
 * Google Earth Engine Script — Export ESA WorldCover LULC for Andhra Pradesh
 * 
 * How to use:
 *   1. Open https://code.earthengine.google.com
 *   2. Paste this script and click Run
 *   3. Go to Tasks panel → Run each export task
 *   4. Download GeoJSON files from Google Drive
 *   5. Merge all files or place individually in backend/data/
 *      then run: python backend/scripts/merge_lulc_geojsons.py
 */

// ── AP boundary from GADM / FAO
var india = ee.FeatureCollection('projects/sat-io/open-datasets/boundary/INDIA_STATES');
var ap = india.filter(ee.Filter.eq('ST_NM', 'Andhra Pradesh'));
var apGeom = ap.geometry();

Map.centerObject(apGeom, 7);

// ── ESA WorldCover 2021 (v200)
var esa = ee.ImageCollection('ESA/WorldCover/v200').first().clip(apGeom);

// Visualise
var esaVis = {
  bands: ['Map'],
  min: 10, max: 100,
  palette: [
    '006400', // 10 Tree cover
    'ffbb22', // 20 Shrubland
    'ffff4c', // 30 Grassland
    'f096ff', // 40 Cropland
    'fa0000', // 50 Built-up
    'b4b4b4', // 60 Bare / sparse
    'f0f0f0', // 70 Snow
    '0064c8', // 80 Water
    '0096a0', // 90 Wetland
    '00cf75', // 95 Mangroves
    'fae6a0'  // 100 Moss
  ]
};
Map.addLayer(esa, esaVis, 'ESA WorldCover 2021');
Map.addLayer(ap, {color: '38bdf8'}, 'Andhra Pradesh');

// ── Export each class as separate vector layer
var classes = {
  10: 'Tree_cover',
  20: 'Shrubland',
  30: 'Grassland',
  40: 'Cropland',
  50: 'Built_up',
  60: 'Bare_sparse',
  80: 'Water',
  90: 'Wetland',
  95: 'Mangroves'
};

Object.keys(classes).forEach(function(cls) {
  var classInt = parseInt(cls);
  var className = classes[cls];

  var classVector = esa
    .eq(classInt)
    .selfMask()
    .reduceToVectors({
      geometry: apGeom,
      scale: 100,           // 100 m — manageable file size for AP
      maxPixels: 1e12,
      geometryType: 'polygon',
      eightConnected: false,
      labelProperty: 'class_value',
      reducer: ee.Reducer.countEvery()
    })
    .map(function(f) {
      return f.set({
        'class_value': classInt,
        'class_label': className
      });
    });

  Export.table.toDrive({
    collection: classVector,
    description: 'AP_ESA_LULC_' + className,
    folder: 'AP_LULC_GEE',
    fileFormat: 'GeoJSON'
  });
});

print('Tasks created. Go to Tasks panel → click Run for each export.');
