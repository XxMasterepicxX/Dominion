"""
Config loader for market configurations.

Loads and validates YAML config files.
"""
import sys
import yaml
from pathlib import Path
from typing import List

# Handle both package import and direct execution
try:
    from .schemas import MarketConfig
except ImportError:
    from schemas import MarketConfig


class ConfigLoader:
    """Loads and validates market configurations."""

    def __init__(self, config_dir: Path = None):
        """
        Initialize config loader.

        Args:
            config_dir: Directory containing market config files
        """
        if config_dir is None:
            # Default to config/markets/ relative to this file
            config_dir = Path(__file__).parent / "markets"

        self.config_dir = Path(config_dir)

        if not self.config_dir.exists():
            raise ValueError(f"Config directory not found: {self.config_dir}")

    def load(self, market_id: str) -> MarketConfig:
        """
        Load and validate a market config.

        Args:
            market_id: Market identifier (e.g., "gainesville_fl")

        Returns:
            Validated MarketConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        config_file = self.config_dir / f"{market_id}.yaml"

        if not config_file.exists():
            available = self.get_available_markets()
            raise FileNotFoundError(
                f"Config file not found: {config_file}\n"
                f"Available markets: {', '.join(available)}"
            )

        with open(config_file, 'r') as f:
            raw_config = yaml.safe_load(f)

        try:
            config = MarketConfig(**raw_config)
            return config
        except Exception as e:
            raise ValueError(f"Invalid config in {config_file}: {e}")

    def get_available_markets(self) -> List[str]:
        """
        Get list of available market IDs.

        Returns:
            List of market IDs (without .yaml extension)
        """
        if not self.config_dir.exists():
            return []

        yaml_files = self.config_dir.glob("*.yaml")
        return [f.stem for f in yaml_files]


# Convenience functions
def load_market_config(market_id: str, config_dir: Path = None) -> MarketConfig:
    """
    Load a market config (convenience function).

    Args:
        market_id: Market identifier (e.g., "gainesville_fl")
        config_dir: Optional config directory override

    Returns:
        Validated MarketConfig object
    """
    loader = ConfigLoader(config_dir)
    return loader.load(market_id)


def get_available_markets(config_dir: Path = None) -> List[str]:
    """
    Get list of available markets (convenience function).

    Args:
        config_dir: Optional config directory override

    Returns:
        List of market IDs
    """
    loader = ConfigLoader(config_dir)
    return loader.get_available_markets()


# Test if run directly
if __name__ == "__main__":
    import sys

    print("Testing config loader...")

    # Check if markets directory exists
    markets_dir = Path(__file__).parent / "markets"
    if not markets_dir.exists():
        print(f"Markets directory not found: {markets_dir}")
        print("Create config/markets/ and add YAML files to test")
        sys.exit(1)

    # List available markets
    try:
        markets = get_available_markets()
        print(f"\nAvailable markets: {markets}")

        if not markets:
            print("No market configs found. Add .yaml files to config/markets/")
            sys.exit(1)

        # Test loading each market
        for market_id in markets:
            try:
                config = load_market_config(market_id)
                print(f"\n[OK] {market_id}: Valid")
                print(f"  Name: {config.market.name}")
                print(f"  FIPS: {config.geography.fips}")
                print(f"  Scrapers enabled: {sum([1 for s in [config.scrapers.census, config.scrapers.sunbiz] if s and s.enabled])}")
            except Exception as e:
                print(f"\n[FAIL] {market_id}: INVALID")
                print(f"  Error: {e}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)