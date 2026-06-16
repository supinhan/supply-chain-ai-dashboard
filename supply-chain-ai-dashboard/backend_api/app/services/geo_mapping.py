from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


MAPPING_PATH = Path(__file__).with_name("city_region_mapping.json")


def _normalize_city_key(city: str | None) -> str:
    if not city:
        return ""
    cleaned = re.sub(r"\s+", " ", str(city).strip().lower())
    return cleaned


def _load_mapping() -> tuple[dict[str, str], set[str]]:
    try:
        payload = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, set()

    city_to_region = {
        _normalize_city_key(city): str(region)
        for city, region in payload.get("cityToRegion", {}).items()
        if city and region
    }
    us_regions = {str(region) for region in payload.get("usRegions", []) if region}
    return city_to_region, us_regions


CITY_TO_REGION, US_REGIONS = _load_mapping()
NA_STATES_REGIONS = US_REGIONS - {"Puerto Rico"}
US_COUNTRY_NAMES = {
    "us",
    "usa",
    "u.s.",
    "u.s.a.",
    "united states",
    "united states of america",
    "ee. uu.",
    "estados unidos",
}


def _normalize_country(country: str | None) -> str | None:
    if not country:
        return None
    cleaned = re.sub(r"\s+", " ", str(country).strip())
    return cleaned or None


def map_city_to_region(city: str | None, country: str | None = None) -> tuple[str | None, bool]:
    city_key = _normalize_city_key(city)
    if city_key in CITY_TO_REGION:
        return CITY_TO_REGION[city_key], True

    normalized_country = _normalize_country(country)
    if normalized_country:
        if normalized_country.lower() in US_COUNTRY_NAMES:
            return "United States", True
        return normalized_country, True

    return None, False


def aggregate_region_heat_map(rows: Iterable[tuple[Any, Any, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    region_counts: dict[str, int] = defaultdict(int)
    unmapped_count = 0
    unmapped_cities: set[str] = set()

    for city, country, count in rows:
        try:
            value = int(count)
        except (TypeError, ValueError):
            value = 0

        region, mapped = map_city_to_region(str(city) if city is not None else None, str(country) if country is not None else None)
        if region:
            region_counts[region] += value
            continue

        unmapped_count += value
        if city:
            unmapped_cities.add(str(city))

    has_world_region = any(region not in NA_STATES_REGIONS for region in region_counts)
    map_type = "WORLD" if has_world_region else "NA_STATES"
    display_counts: dict[str, int] = defaultdict(int)
    for region, value in region_counts.items():
        if map_type == "WORLD" and region in NA_STATES_REGIONS:
            display_counts["United States"] += value
        else:
            display_counts[region] += value

    region_heat_map = [
        {"name": region, "value": value}
        for region, value in sorted(display_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    meta = {
        "mapType": map_type,
        "mappedRegionCount": len(region_heat_map),
        "unmappedCount": unmapped_count,
        "unmappedCities": sorted(unmapped_cities)[:20],
    }
    return region_heat_map, meta
