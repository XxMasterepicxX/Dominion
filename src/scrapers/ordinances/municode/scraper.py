#!/usr/bin/env python3
"""
COMPREHENSIVE MUNICIPAL CODE SCRAPER
Designed for real estate analyst teams, developers, and attorneys

Crawls hierarchically to capture ALL real estate-related ordinances:
1. Get all Parts/Titles from main TOC
2. For each Part, get all Chapters/Articles/Divisions inside it
3. Filter for comprehensive real estate keywords (728)
4. Scrape complete regulatory intelligence

STRUCTURAL TYPES SUPPORTED:
- Parts, Titles, Subparts (Level 1)
- Chapters, Articles, Divisions (Level 2)
- Sections, Subsections (Level 3 - captured in content)
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

try:
    from ....config.schemas import MarketConfig, OrdinanceScraperConfig
except (ImportError, ValueError):
    MarketConfig = None
    OrdinanceScraperConfig = None

from .get_cities import get_florida_municipalities, get_alachua_county_municipalities

# COMPREHENSIVE REAL ESTATE KEYWORDS (200+)
# Organized by category for analyst teams, developers, and attorneys

REAL_ESTATE_KEYWORDS = [
    # === LAND USE & ZONING ===
    "land development", "development code", "land use", "land use regulations",
    "zoning", "zone", "zoning district", "zoning map", "rezoning",
    "subdivision", "platting", "plat", "replatting", "lot split",
    "comprehensive plan", "future land use", "growth management",
    "overlay district", "planned unit development", "PUD", "planned development",
    "conditional use", "special exception", "special use permit",
    "variance", "waiver", "deviation", "modification",
    "setback", "yard requirement", "lot size", "lot coverage", "lot width",
    "density", "floor area ratio", "FAR", "height limit", "height restriction",
    "residential", "commercial", "industrial", "mixed-use", "agricultural",
    "single-family", "multi-family", "multifamily", "townhouse", "duplex", "triplex",
    "apartment", "apartment building", "apartment complex",
    "condominium", "mobile home", "manufactured housing",
    "nonconforming use", "legal nonconforming", "grandfathered",
    "vested rights", "development agreement", "development order",

    # === DEVELOPMENT PROCESS & PROCEDURES ===
    "development review", "site plan", "site development", "master plan",
    "preliminary plat", "final plat", "construction plans",
    "development application", "application process", "submission requirements",
    "review criteria", "approval criteria", "findings",
    "planning commission", "zoning board", "board of adjustment",
    "development review committee", "technical review", "staff review",
    "public hearing", "notice requirement", "notification",
    "appeal", "administrative appeal", "judicial review",
    "expiration", "extension", "renewal", "abandonment",
    "phasing", "development phasing", "buildout",
    "concurrency", "adequate public facilities", "level of service",
    "vesting", "permit vesting", "development rights",
    "entitlement", "land entitlement", "development entitlement",
    "site plan approval", "development permit", "land use permit",
    "conditional use", "variance permit", "zoning variance",

    # === BUILDING & CONSTRUCTION ===
    "building", "construction", "building code", "building regulation",
    "building permit", "construction permit", "demolition permit",
    "building standard", "construction standard", "technical codes",
    "certificate of occupancy", "CO", "temporary CO", "TCO",
    "building inspection", "inspection", "code compliance",
    "contractor", "contractor licensing", "general contractor",
    "building official", "code enforcement", "enforcement",
    "foundation", "structural", "fire code", "fire safety",
    "fire-life-safety", "fire marshal", "fire inspection",
    "accessibility", "ADA", "disabled access", "barrier-free", "ADA compliance",
    "energy code", "energy efficiency", "green building",
    "solar", "solar panel", "solar energy", "photovoltaic", "PV system",
    "solar installation", "renewable energy", "alternative energy",

    # === HOUSING & PROPERTY STANDARDS ===
    "housing code", "property maintenance", "maintenance code",
    "minimum housing standards", "habitability", "unsafe structure",
    "rental housing", "rental property", "rental registration",
    "rental inspection", "rental licensing", "landlord",
    "tenant", "dwelling unit", "living conditions",
    "nuisance", "public nuisance", "nuisance abatement",
    "noise", "noise ordinance", "sound level", "quiet hours", "noise complaint",
    "light pollution", "outdoor lighting", "glare", "lighting standard",
    "blight", "blighted property", "property abandonment",
    "condemnation", "unsafe building", "dangerous building",
    "foreclosure", "tax delinquency", "vacant property",
    "affordable housing", "workforce housing", "inclusionary zoning",
    "density bonus", "parking ratio", "parking requirement", "parking reduction",
    "transit-oriented development", "TOD", "major transit stop", "transit station",
    "accessory dwelling unit", "ADU", "granny flat", "in-law unit",
    "garage conversion", "garage apartment", "detached garage", "accessory garage",
    "carriage house", "garage dwelling", "above-garage unit",
    "short-term rental", "vacation rental", "Airbnb",
    "student housing", "dormitory", "dorm", "rooming house", "boarding house",
    "co-living", "co-housing", "congregate living", "group living",
    "micro-apartment", "microunit", "efficiency apartment",

    # === ACCESSORY STRUCTURES & IMPROVEMENTS ===
    "swimming pool", "pool", "spa", "hot tub", "jacuzzi", "pool enclosure",
    "pool fence", "pool barrier", "pool safety",
    "fence", "wall", "privacy fence", "chain link", "picket fence", "retaining wall",
    "fence height", "fence material", "property line fence",
    "shed", "storage shed", "tool shed", "outbuilding", "barn", "workshop",
    "accessory structure", "accessory building", "detached structure",
    "deck", "patio", "balcony", "veranda", "pergola", "gazebo", "pavilion",
    "outdoor structure", "covered structure", "shade structure",
    "driveway", "parking pad", "carport", "parking area", "driveway permit",
    "paving", "pavement", "concrete pad", "asphalt",
    "porch", "front porch", "back porch", "screened porch", "covered porch",
    "addition", "home addition", "room addition", "expansion", "extension",
    "basement", "finished basement", "walkout basement", "cellar", "crawl space",

    # === VEHICLES & MOBILE DWELLINGS ===
    "RV", "recreational vehicle", "camper", "trailer", "boat", "boat storage",
    "RV parking", "vehicle storage", "boat parking", "trailer parking",
    "inoperable vehicle", "abandoned vehicle", "junk vehicle",
    "mobile dwelling", "park model", "tiny home", "tiny house", "mobile tiny home",
    "manufactured home", "modular home", "prefab home",

    # === UTILITIES & INFRASTRUCTURE ===
    "utility", "public utility", "utility service", "utility extension",
    "water", "water service", "water supply", "water main",
    "sewer", "sanitary sewer", "wastewater", "sewage",
    "septic", "septic system", "on-site sewage",
    "stormwater", "stormwater management", "drainage", "storm drain",
    "electric", "electrical service", "power", "franchise",
    "gas", "natural gas", "telecommunications", "broadband",
    "cell tower", "wireless facility", "telecommunications tower",
    "5G", "small cell", "antenna", "monopole", "communication facility",
    "wireless communication", "cellular tower", "radio tower",
    "utility capacity", "capacity analysis", "capacity reservation",
    "EV charging", "electric vehicle charging", "charging station",
    "EV infrastructure", "vehicle charging equipment", "EV charger",
    "connection fee", "tap fee", "utility deposit",
    "impact fee", "system development charge", "capital facility fee",
    "assessment", "special assessment", "benefit assessment",
    "infrastructure", "public infrastructure", "capital improvement",
    "street", "road", "roadway", "street improvement",
    "sidewalk", "pedestrian", "bicycle", "trail",
    "right-of-way", "easement", "utility easement", "access easement",
    "public works", "public improvements", "dedication",

    # === ENVIRONMENTAL & NATURAL RESOURCES ===
    "environmental", "environmental protection", "environmental review",
    "conservation", "natural resources", "resource protection",
    "wetland", "wetlands protection", "jurisdictional wetland",
    "floodplain", "flood zone", "flood hazard", "FEMA",
    "flood damage prevention", "floodplain management", "base flood elevation",
    "coastal", "coastal zone", "coastal construction", "shoreline",
    "sea level rise", "climate adaptation", "resilience",
    "tree protection", "tree preservation", "heritage tree", "protected tree",
    "tree removal", "tree permit", "tree replacement", "tree mitigation",
    "landscaping", "landscape requirement", "native vegetation", "landscape buffer",
    "lawn", "grass", "yard maintenance", "vegetation maintenance",
    "irrigation", "sprinkler system", "water conservation",
    "open space", "green space", "recreation area",
    "endangered species", "habitat protection", "wildlife",
    "erosion", "soil erosion", "sediment control",
    "water quality", "surface water", "groundwater", "wellhead protection",
    "air quality", "emissions", "dust control",
    "contamination", "hazardous materials", "brownfield",
    "environmental site assessment", "Phase I", "Phase II", "ESA",
    "environmental compliance", "environmental review", "environmental impact",
    "solid waste", "waste management", "landfill", "recycling",

    # === BUSINESS & ECONOMIC DEVELOPMENT ===
    "business", "business regulation", "business license",
    "business tax", "occupational license", "commercial activity",
    "certificate of use", "business permit", "operating permit",
    "liquor license", "alcohol permit", "beer and wine", "alcoholic beverage",
    "entertainment permit", "entertainment license", "live entertainment",
    "economic development", "community development", "redevelopment",
    "community redevelopment area", "CRA", "tax increment",
    "downtown", "downtown development", "urban core",
    "enterprise zone", "opportunity zone", "incentive district",
    "public-private partnership", "development agreement",
    "signage", "sign code", "sign permit", "sign regulation",
    "outdoor advertising", "billboard", "monument sign",
    "home occupation", "home business", "home-based business",
    "restaurant", "food service", "eating establishment", "dining",
    "fast food", "quick service", "drive-through", "drive-thru", "drive-in",
    "outdoor dining", "outdoor seating", "sidewalk cafe", "patio dining",
    "food truck", "mobile food vendor", "food cart", "mobile vending",
    "street vendor", "mobile food unit",
    "shopping center", "strip mall", "retail center", "commercial center",
    "grocery store", "supermarket", "convenience store",
    "bar", "tavern", "nightclub", "lounge", "brewery", "brewpub",
    "hotel", "motel", "inn", "lodging", "accommodation",
    "office", "office building", "professional office", "medical office",
    "warehouse", "distribution center", "logistics facility", "fulfillment center",
    "industrial park", "business park", "flex space", "flex warehouse",
    "self-storage", "mini storage", "storage facility",
    "car wash", "gas station", "service station", "fuel station",
    "auto repair", "automotive service", "vehicle repair",
    "cannabis", "marijuana", "dispensary", "medical marijuana", "MMTC",
    "livestock", "farm animals", "chickens", "poultry", "beekeeping", "bees",
    "urban agriculture", "backyard chickens", "animal keeping",
    "kennel", "animal care", "pet care", "animal boarding",

    # === FEES & FINANCIAL ===
    "fee", "fee schedule", "application fee", "permit fee",
    "impact fee", "development impact fee", "transportation impact",
    "school impact fee", "park impact fee", "fire impact fee",
    "exaction", "dedication", "in-lieu fee",
    "assessment", "special assessment", "non-ad valorem",
    "tax increment financing", "TIF", "TIFF",
    "bond", "performance bond", "surety", "guarantee",
    "escrow", "cash deposit", "letter of credit",

    # === GOVERNMENT PROCESS ===
    "comprehensive plan", "comp plan", "general plan",
    "plan amendment", "text amendment", "map amendment",
    "future land use", "land use element", "capital improvement element",
    "consistency", "plan consistency", "comprehensive plan compliance",
    "evaluation and appraisal", "EAR", "plan update",
    "development of regional impact", "DRI", "substantial deviation",
    "annexation", "municipal boundary", "extraterritorial jurisdiction",
    "interlocal agreement", "joint planning", "coordination",

    # === PUBLIC FACILITIES ===
    "public facility", "community facility", "essential service",
    "school", "educational facility", "school site",
    "daycare", "day care", "child care", "childcare facility", "child care center",
    "nursery school", "preschool", "family daycare", "group daycare",
    "park", "recreation", "recreation facility", "playground",
    "library", "community center", "civic facility",
    "fire station", "police station", "emergency service",
    "hospital", "healthcare facility", "medical facility",

    # === TRANSPORTATION & ACCESS ===
    "transportation", "traffic", "traffic impact", "traffic study",
    "access", "site access", "driveway", "curb cut",
    "parking", "parking requirement", "parking space", "off-street parking",
    "on-street parking", "parking lot", "parking garage", "parking structure",
    "loading", "loading zone", "service area", "delivery",
    "transit", "public transit", "bus stop", "transit-oriented development",
    "walkability", "pedestrian access", "pedestrian safety",
    "complete streets", "multimodal", "bike lane",

    # === HISTORIC & DESIGN ===
    "historic preservation", "historic district", "landmark",
    "historic resource", "contributing structure", "historic character",
    "design standard", "design guideline", "architectural review",
    "architectural", "facade", "building design", "site design",
    "appearance", "aesthetic", "compatibility", "character",
    "buffer", "buffering", "screening", "landscaping buffer",

    # === LEGAL & ENFORCEMENT ===
    "enforcement", "code enforcement", "violation", "citation",
    "penalty", "fine", "civil penalty", "criminal penalty",
    "lien", "code enforcement lien", "special assessment lien",
    "injunction", "cease and desist", "stop work order",
    "administrative hearing", "hearing officer", "code board",
    "due process", "notice of violation", "compliance deadline",
    "definition", "interpretation", "rules of construction",
    "severability", "amendment", "repeal", "effective date",
]

async def get_level1_parts(crawler, url):
    """Get Level 1: Parts/Titles from main TOC"""

    config = CrawlerRunConfig(
        word_count_threshold=10,
        excluded_tags=['form', 'footer'],
        page_timeout=90000,
        js_code=["await new Promise(r => setTimeout(r, 8000))"],
    )

    result = await crawler.arun(url=url, config=config)

    if not result.success or not result.markdown:
        return []

    # Find all Parts/Titles/Subparts
    lines = result.markdown.split('\n')
    parts = []

    for line in lines:
        lower = line.lower()
        # Look for Parts, Titles, Subparts
        if ("part" in lower or "title" in lower or "subpart" in lower) and "[" in line and "](" in line:
            start = line.find("[")
            end = line.find("]", start)
            if start == -1 or end == -1:
                continue

            title = line[start+1:end].strip()

            url_start = line.find("](", end)
            url_end = line.find(")", url_start)
            if url_start == -1 or url_end == -1:
                continue

            part_url = line[url_start+2:url_end]

            if title and part_url and len(title) > 5:
                parts.append({"title": title, "url": part_url})

    return parts

async def get_level2_chapters(crawler, part_url):
    """Get Level 2: Chapters/Articles/Divisions inside a Part"""

    config = CrawlerRunConfig(
        word_count_threshold=10,
        excluded_tags=['form', 'footer'],
        page_timeout=90000,
        js_code=["await new Promise(r => setTimeout(r, 8000))"],
    )

    # Make full URL if relative
    if not part_url.startswith("http"):
        part_url = f"https://library.municode.com{part_url}"

    result = await crawler.arun(url=part_url, config=config)

    if not result.success or not result.markdown:
        return []

    # Find all Chapters, Articles, AND Divisions
    lines = result.markdown.split('\n')
    chapters = []
    seen = set()

    for line in lines:
        lower = line.lower()
        # Look for chapters, articles, OR divisions
        if ("chapter" in lower or "article" in lower or "division" in lower) and "[" in line and "](" in line:
            start = line.find("[")
            end = line.find("]", start)
            if start == -1 or end == -1:
                continue

            title = line[start+1:end].strip()

            url_start = line.find("](", end)
            url_end = line.find(")", url_start)
            if url_start == -1 or url_end == -1:
                continue

            chapter_url = line[url_start+2:url_end]

            if title and chapter_url and len(title) > 5 and chapter_url not in seen:
                chapters.append({"title": title, "url": chapter_url})
                seen.add(chapter_url)

    return chapters

async def get_chapters_from_toc(crawler, url):
    """Get Chapters/Articles/Divisions directly from main TOC (FLAT structure)"""

    config = CrawlerRunConfig(
        word_count_threshold=10,
        excluded_tags=['form', 'footer'],
        page_timeout=90000,
        js_code=["await new Promise(r => setTimeout(r, 8000))"],
    )

    result = await crawler.arun(url=url, config=config)

    if not result.success or not result.markdown:
        return []

    # Find all Chapters, Articles, AND Divisions on main TOC
    lines = result.markdown.split('\n')
    chapters = []
    seen = set()

    for line in lines:
        lower = line.lower()
        # Look for chapters, articles, OR divisions
        if ("chapter" in lower or "article" in lower or "division" in lower) and "[" in line and "](" in line:
            start = line.find("[")
            end = line.find("]", start)
            if start == -1 or end == -1:
                continue

            title = line[start+1:end].strip()

            url_start = line.find("](", end)
            url_end = line.find(")", url_start)
            if url_start == -1 or url_end == -1:
                continue

            chapter_url = line[url_start+2:url_end]

            if title and chapter_url and len(title) > 5 and chapter_url not in seen:
                chapters.append({"title": title, "url": chapter_url})
                seen.add(chapter_url)

    return chapters

async def discover_all_chapters_hierarchical(crawler, municipality_name, url_slug):
    """
    HIERARCHICAL DISCOVERY:
    1. Get all Parts/Titles (Level 1)
    2. For each Part, get Chapters/Articles/Divisions (Level 2)
    3. If no Parts found, look for Chapters/Articles/Divisions directly on TOC (FLAT structure)
    4. Filter for real estate keywords (200+)
    """

    url = f"https://library.municode.com/fl/{url_slug}/codes/code_of_ordinances"

    print(f"  [1/4] Getting Level 1: Parts/Titles/Subparts...")

    # Level 1: Get all Parts
    parts = await get_level1_parts(crawler, url)
    print(f"  Found {len(parts)} parts/titles/subparts")

    all_chapters = []

    # Level 2A: For each Part, get its Chapters/Articles/Divisions (hierarchical)
    if parts:
        print(f"  [2/4] Getting Level 2: Chapters/Articles/Divisions inside each Part...")
        for i, part in enumerate(parts, 1):
            print(f"    Expanding: {part['title'][:50]}...")
            chapters = await get_level2_chapters(crawler, part["url"])
            print(f"      Found {len(chapters)} chapters/articles/divisions")
            all_chapters.extend(chapters)

    # Level 2B: ALWAYS also check for flat structure (chapters/articles/divisions on TOC)
    # Some cities have HYBRID structure with both Parts and flat Chapters
    print(f"  [2/4] Also checking for flat structure (chapters/articles/divisions on TOC)...")
    flat_chapters = await get_chapters_from_toc(crawler, url)
    if flat_chapters:
        print(f"  Found {len(flat_chapters)} chapters/articles/divisions directly on TOC")
        all_chapters.extend(flat_chapters)
    else:
        print(f"  No chapters/articles/divisions found on TOC")

    # Remove duplicates
    seen_urls = set()
    unique_chapters = []
    for ch in all_chapters:
        if ch["url"] not in seen_urls:
            unique_chapters.append(ch)
            seen_urls.add(ch["url"])

    print(f"  Total unique chapters/articles/divisions: {len(unique_chapters)}")

    # Filter for real estate-related chapters
    print(f"  [3/4] Filtering for real estate ordinances (200+ keywords)...")

    real_estate_chapters = []
    for chapter in unique_chapters:
        title_lower = chapter["title"].lower()
        for keyword in REAL_ESTATE_KEYWORDS:
            if keyword in title_lower:
                if not any(d["url"] == chapter["url"] for d in real_estate_chapters):
                    real_estate_chapters.append(chapter)
                break

    print(f"  [4/4] Found {len(real_estate_chapters)} real estate ordinances:")
    for ch in real_estate_chapters:
        print(f"    • {ch['title'][:60]}")

    return real_estate_chapters

async def scrape_chapter(crawler, chapter_url, chapter_title):
    """Scrape a chapter"""

    config = CrawlerRunConfig(
        word_count_threshold=10,
        excluded_tags=['form', 'nav', 'header', 'footer'],
        page_timeout=60000,
        js_code=["await new Promise(r => setTimeout(r, 3000))"],
    )

    if not chapter_url.startswith("http"):
        chapter_url = f"https://library.municode.com{chapter_url}"

    try:
        result = await crawler.arun(url=chapter_url, config=config)

        if result.success and result.markdown:
            lower_content = result.markdown.lower()

            if "content cannot be found" in lower_content:
                return None

            has_section = "sec" in lower_content or "§" in lower_content
            has_ordinance = "ordinance" in lower_content
            is_substantial = len(result.markdown) > 5000

            if (has_section or has_ordinance) and is_substantial:
                return {
                    "title": chapter_title,
                    "url": chapter_url,
                    "content": result.markdown,
                    "size": len(result.markdown),
                    "status": "success"
                }

        return None

    except Exception as e:
        print(f"    Error scraping {chapter_title[:50]}: {e}")
        return None

async def scrape_municipality_hierarchical(crawler, municipality, output_dir):
    """Scrape comprehensive real estate ordinances with hierarchical discovery"""

    name = municipality["name"]
    url_slug = municipality["url_slug"]

    print(f"\n{'=' * 80}")
    print(f"MUNICIPALITY: {name}")
    print('=' * 80)

    # Discover real estate ordinances hierarchically
    ordinances = await discover_all_chapters_hierarchical(crawler, name, url_slug)

    if not ordinances:
        print(f"  No real estate ordinances found")
        return {
            "municipality": name,
            "url_slug": url_slug,
            "status": "no_ordinances",
            "ordinances": []
        }

    # Scrape each ordinance
    print(f"\n  Scraping {len(ordinances)} ordinances...")

    scraped_ordinances = []
    for i, ordinance in enumerate(ordinances, 1):
        print(f"    [{i}/{len(ordinances)}] {ordinance['title'][:50]}...")

        result = await scrape_chapter(crawler, ordinance["url"], ordinance["title"])

        if result:
            scraped_ordinances.append(result)
            print(f"      {result['size']:,} chars")
        else:
            print(f"      Failed or no content")

    if not scraped_ordinances:
        print(f"\n  No ordinances successfully scraped")
        return {
            "municipality": name,
            "url_slug": url_slug,
            "status": "no_content",
            "ordinances_found": len(ordinances),
            "ordinances": []
        }

    # Save
    combined = f"\n{'=' * 80}\n{name.upper()} - REAL ESTATE ORDINANCES\n{'=' * 80}\n\n"
    combined += "Comprehensive ordinances for real estate analysts, developers, and attorneys\n"
    combined += "Includes: Zoning, Land Use, Building, Housing, Utilities, Environmental, Fees, and Legal Procedures\n\n"

    for ordinance in scraped_ordinances:
        combined += f"\n\n{'=' * 80}\n{ordinance['title']}\n{'=' * 80}\n\n"
        combined += ordinance["content"]

    safe_name = name.replace(" ", "_").replace("/", "_").lower()
    output_file = f"{output_dir}/{safe_name}_real_estate_ordinances.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(combined)

    total_size = sum(ch["size"] for ch in scraped_ordinances)

    print(f"\n  Saved to: {output_file}")
    print(f"  Total: {len(scraped_ordinances)} ordinances, {total_size:,} chars")

    return {
        "municipality": name,
        "url_slug": url_slug,
        "status": "success",
        "ordinances_found": len(ordinances),
        "ordinances_scraped": len(scraped_ordinances),
        "total_size": total_size,
        "ordinances": [{"title": ch["title"], "size": ch["size"]} for ch in scraped_ordinances]
    }

async def run_from_config(market_config: Optional['MarketConfig'] = None):
    """Run scraper from MarketConfig (for integration with YAML configs)"""

    if not market_config or not market_config.scrapers.ordinances:
        raise ValueError("OrdinanceScraperConfig not provided or not enabled")

    config = market_config.scrapers.ordinances

    if not config.enabled:
        print("Ordinances scraper is disabled in config")
        return {"status": "disabled"}

    # Fetch municipalities dynamically from Municode API
    print(f"[API] Fetching municipalities from Municode API...")

    if config.scope == "market":
        # Just the market city (e.g., Gainesville only)
        market_name = market_config.market.name.split(",")[0].strip()  # "Gainesville, FL" -> "Gainesville"
        test_cities = get_florida_municipalities(city_filter=market_name)
        print(f"   Scope: Market city only ({market_name})")

    elif config.scope == "county":
        # All cities in the county
        county_name = market_config.market.county
        if county_name == "Alachua":
            test_cities = get_alachua_county_municipalities()
        else:
            # Fallback to county filter
            test_cities = get_florida_municipalities(county_filter=county_name)
        print(f"   Scope: All {county_name} County municipalities")

    elif config.scope == "state":
        # All FL cities
        test_cities = get_florida_municipalities()
        print(f"   Scope: Entire state ({len(test_cities)} municipalities)")

    elif config.scope == "custom":
        # Specific list of municipalities
        if not config.municipalities:
            raise ValueError("scope='custom' requires municipalities list")
        all_cities = get_florida_municipalities()
        test_cities = [c for c in all_cities if c["name"] in config.municipalities]
        print(f"   Scope: Custom list ({len(test_cities)} municipalities)")

    else:
        raise ValueError(f"Invalid scope: {config.scope}. Must be 'market', 'county', 'state', or 'custom'")

    if not test_cities:
        print(f"[WARN] No municipalities found for scope '{config.scope}'")
        return {"status": "no_municipalities_found"}

    print("=" * 80)
    print(f"ORDINANCES SCRAPER - {market_config.market.name}")
    print(f"Platform: {config.platform}")
    print(f"Scraping: {len(test_cities)} Florida municipalities")
    print("=" * 80)

    # Create output directory
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=['--disable-blink-features=AutomationControlled']
    )

    results = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, city in enumerate(test_cities, 1):
            print(f"\n[{i}/{len(test_cities)}]")
            try:
                result = await scrape_municipality_hierarchical(crawler, city, str(output_dir))
                results.append(result)
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({
                    "municipality": city["name"],
                    "url_slug": city["url_slug"],
                    "status": "error",
                    "error": str(e),
                    "ordinances": []
                })

    # Summary
    print("\n\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    successful = [r for r in results if r["status"] == "success"]
    no_ordinances = [r for r in results if r["status"] == "no_ordinances"]
    no_content = [r for r in results if r["status"] == "no_content"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"\nTotal tested: {len(results)}")
    print(f"Successful:   {len(successful)} ({len(successful)*100//len(results) if results else 0}%)")
    print(f"No ordinances: {len(no_ordinances)}")
    print(f"No content:   {len(no_content)}")
    print(f"Errors:       {len(errors)}")

    if successful:
        total_ordinances = sum(r['ordinances_scraped'] for r in successful)
        total_size = sum(r['total_size'] for r in successful)
        print(f"\nTotal ordinances scraped: {total_ordinances}")
        print(f"Total data collected:     {total_size:,} chars ({total_size/1024/1024:.1f} MB)")

    # Save results
    results_file = output_dir / f"scrape_results_{len(test_cities)}_cities.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {results_file}")

    return results
