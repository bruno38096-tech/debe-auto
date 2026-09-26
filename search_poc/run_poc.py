import json
from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring


def main():
    vehicles = fetch_bmw_330e_touring()
    payload = {
        "query": "BMW 330e Touring",
        "source": "BMW Premium Selection Portugal",
        "count": len(vehicles),
        "vehicles": [v.to_dict() for v in vehicles],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
