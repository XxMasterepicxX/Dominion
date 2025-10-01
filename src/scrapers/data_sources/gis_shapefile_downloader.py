"""
GIS Shapefile/GeoJSON Scraper

Downloads and processes geographic data from county GIS portals.
Config-driven to support multiple FL counties.
"""
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import requests
import structlog

from ...config.schemas import MarketConfig

logger = structlog.get_logger(__name__)

try:
    import geopandas as gpd
    import pandas as pd
except ImportError:
    gpd = None
    pd = None


class GISFeature:
    """Simple GIS feature model."""

    def __init__(self, data: Dict):
        self.properties = data
        self.geometry = data.get('geometry', {})

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def to_dict(self):
        return self.properties


class GISScraper:
    """GIS scraper that downloads and parses shapefiles/GeoJSON using geopandas."""

    def __init__(self, market_config: MarketConfig):
        """Initialize with market config."""
        self.config = market_config
        self.gis_config = market_config.scrapers.gis

        if not self.gis_config or not self.gis_config.enabled:
            raise ValueError("GIS scraper not enabled in config")

        self.county_name = self.gis_config.county_name
        self.shapefile_urls = self.gis_config.shapefile_urls

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; DominionScraper/1.0)'
        })

        logger.info("gis_scraper_initialized",
                   county=self.county_name,
                   layers_count=len(self.shapefile_urls))

    def fetch_layer(self, layer_name: str, limit: Optional[int] = None) -> List[GISFeature]:
        """
        Fetch a GIS layer and return features.

        Args:
            layer_name: Name of the layer (e.g., 'parcels', 'zoning')
            limit: Max features to return (for testing)

        Returns:
            List of GISFeature objects
        """
        if layer_name not in self.shapefile_urls:
            logger.error("layer_not_found", layer=layer_name)
            return []

        url = self.shapefile_urls[layer_name]

        try:
            if 'geojson' in url.lower() or 'f=geojson' in url.lower():
                return self._fetch_geojson(url, limit)
            elif url.endswith('.zip'):
                return self._fetch_shapefile_zip(url, limit)
            else:
                logger.warning("unknown_format", url=url)
                return []

        except Exception as e:
            logger.error("layer_fetch_failed", layer=layer_name, error=str(e))
            import traceback
            traceback.print_exc()
            return []

    def _fetch_geojson(self, url: str, limit: Optional[int] = None) -> List[GISFeature]:
        """Fetch and parse GeoJSON features."""
        try:
            response = self.session.get(url, timeout=120)
            response.raise_for_status()

            geojson = response.json()

            if 'features' not in geojson:
                logger.error("invalid_geojson", reason="no features key")
                return []

            features = geojson['features']

            result = []
            for i, feature in enumerate(features):
                if limit and i >= limit:
                    break

                data = feature.get('properties', {})
                data['geometry'] = feature.get('geometry', {})
                result.append(GISFeature(data))

            logger.info("geojson_fetched", features_count=len(result))
            return result

        except Exception as e:
            logger.error("geojson_fetch_failed", error=str(e))
            import traceback
            traceback.print_exc()
            return []

    def _fetch_shapefile_zip(self, url: str, limit: Optional[int] = None) -> List[GISFeature]:
        """Download shapefile ZIP and parse with geopandas."""
        if not gpd:
            logger.error("geopandas_not_installed")
            return []

        try:
            response = self.session.get(url, timeout=120, stream=True)
            response.raise_for_status()

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            temp_file.close()

            temp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(temp_file.name, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            shp_files = list(Path(temp_dir).glob('*.shp'))
            if not shp_files:
                logger.error("no_shp_file_in_zip")
                return []

            shp_file = shp_files[0]
            gdf = gpd.read_file(shp_file)

            result = []
            for i, (idx, row) in enumerate(gdf.iterrows()):
                if limit and i >= limit:
                    break
                data = row.to_dict()
                result.append(GISFeature(data))

            logger.info("shapefile_fetched", features_count=len(result))
            return result

        except Exception as e:
            logger.error("shapefile_fetch_failed", error=str(e))
            import traceback
            traceback.print_exc()
            return []

    def fetch_all_layers(self, limit: Optional[int] = None) -> Dict[str, List[GISFeature]]:
        """Fetch all configured GIS layers."""
        results = {}

        for layer_name in self.shapefile_urls.keys():
            features = self.fetch_layer(layer_name, limit)
            if features:
                results[layer_name] = features

        return results

    def get_layer_summary(self, layer_name: str, features: List[GISFeature]) -> Dict:
        """Get summary stats for a GIS layer."""
        if not features:
            return {}

        # Get field names from first feature
        fields = list(features[0].properties.keys()) if features else []

        summary = {
            'layer_name': layer_name,
            'feature_count': len(features),
            'fields': fields,
            'field_count': len(fields),
        }

        return summary


def test_scraper():
    """Test the GIS scraper."""
    from ...config.loader import load_market_config

    print("\n=== Testing GIS Scraper ===\n")

    try:
        config = load_market_config('gainesville_fl')
        print(f"[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"[FAIL] Failed to load config: {e}")
        return

    try:
        scraper = GISScraper(config)
        print(f"[OK] Initialized scraper for {scraper.county_name} County")
        print(f"     Layers configured: {len(scraper.shapefile_urls)}")
        for layer_name in scraper.shapefile_urls.keys():
            print(f"       - {layer_name}")
    except Exception as e:
        print(f"[FAIL] Failed to initialize scraper: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n[TEST] Fetching 'parcels' layer (limit: 100)...")
    features = scraper.fetch_layer('parcels', limit=100)

    if features:
        print(f"\n[SUCCESS] Fetched {len(features)} parcels!")

        first = features[0]
        print(f"\n--- Sample Parcel ---")
        for i, (key, value) in enumerate(first.properties.items()):
            if i >= 10:
                break
            if key != 'geometry':
                print(f"{key}: {value}")

        summary = scraper.get_layer_summary('parcels', features)
        print(f"\n--- Layer Summary ---")
        print(f"Layer: {summary['layer_name']}")
        print(f"Features: {summary['feature_count']:,}")
        print(f"Fields: {summary['field_count']}")
        print(f"Sample fields: {', '.join(summary['fields'][:8])}")

    else:
        print(f"\n[WARN] No features fetched")


if __name__ == "__main__":
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    test_scraper()
