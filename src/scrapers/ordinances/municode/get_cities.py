#!/usr/bin/env python3
"""
Utility to fetch municipalities from Municode API dynamically
"""

import requests
from typing import List, Dict, Optional

BASE_URL = "https://api.municode.com"

def get_florida_municipalities(city_filter: Optional[str] = None, county_filter: Optional[str] = None) -> List[Dict]:
    """
    Get Florida municipalities from Municode API

    Args:
        city_filter: Filter to specific city name (e.g., "Gainesville")
        county_filter: Filter to specific county (e.g., "Alachua")

    Returns:
        List of municipality dicts with name, city, client_id, url_slug
    """

    url = f"{BASE_URL}/Clients/stateAbbr?stateAbbr=FL"

    response = requests.get(url)
    response.raise_for_status()

    clients = response.json()

    # Extract and normalize
    municipalities = []
    for client in clients:
        name = client.get("ClientName") or client.get("clientName", "Unknown")
        city = client.get("City") or client.get("city", "Unknown")

        muni = {
            "name": name,
            "city": city,
            "client_id": client.get("ClientId") or client.get("clientId", "Unknown"),
            "url_slug": name.lower().replace(" ", "_").replace(",", "")
        }

        # Apply filters
        if city_filter and city_filter.lower() not in name.lower():
            continue

        if county_filter:
            # County filter - check if city is in county
            # For now, simple name matching (improve later with county data)
            if county_filter.lower() not in name.lower() and county_filter.lower() not in city.lower():
                continue

        municipalities.append(muni)

    # Sort by name
    municipalities.sort(key=lambda x: x["name"])

    return municipalities


def get_alachua_county_municipalities() -> List[Dict]:
    """Get all Alachua County municipalities"""

    # Known Alachua County cities (from census/local knowledge)
    alachua_cities = [
        "Alachua",
        "Archer",
        "Gainesville",
        "Hawthorne",
        "High Springs",
        "La Crosse",
        "Micanopy",
        "Newberry",
        "Waldo"
    ]

    all_fl_munis = get_florida_municipalities()

    # Filter to Alachua County cities
    alachua_munis = []
    for muni in all_fl_munis:
        for city in alachua_cities:
            if city.lower() in muni["name"].lower():
                alachua_munis.append(muni)
                break

    return alachua_munis


if __name__ == "__main__":
    print("Testing Municode API fetcher...")

    # Test 1: All FL
    all_fl = get_florida_municipalities()
    print(f"\n✅ All Florida: {len(all_fl)} municipalities")

    # Test 2: Gainesville only
    gainesville = get_florida_municipalities(city_filter="Gainesville")
    print(f"✅ Gainesville: {len(gainesville)} municipalities")
    for m in gainesville:
        print(f"   - {m['name']}")

    # Test 3: Alachua County
    alachua = get_alachua_county_municipalities()
    print(f"✅ Alachua County: {len(alachua)} municipalities")
    for m in alachua:
        print(f"   - {m['name']}")
