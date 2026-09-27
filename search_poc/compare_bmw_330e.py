import json
from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring
from search_poc.connectors.standvirtual import discover_bmw_330e_touring
from search_poc.dedup import cross_source_matches


def main():
    official = fetch_bmw_330e_touring()
    marketplace = discover_bmw_330e_touring()
    matches = cross_source_matches(official, marketplace)
    matched_left = {m.left_id for m in matches}
    payload = {
        "query": "BMW 330e Touring",
        "official_count": len(official),
        "standvirtual_discovered_lower_bound": len(marketplace),
        "cross_source_matches": len(matches),
        "official_not_matched_to_standvirtual": len([v for v in official if v.source_id not in matched_left]),
        "matches": [m.__dict__ for m in matches],
        "official": [v.to_dict() for v in official],
        "standvirtual": [v.to_dict() for v in marketplace],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
