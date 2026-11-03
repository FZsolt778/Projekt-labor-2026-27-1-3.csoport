from api_client import api


def load_my_parcels(direction: str, scope: str) -> list[dict]:
    parcels = []
    offset = 0

    while True:
        page = api.get(
            "/parcels/my",
            params={"direction": direction, "scope": scope, "limit": 100, "offset": offset},
        )
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise ValueError("A szerver hibás csomaglistát küldött.")

        items = page["items"]
        parcels.extend(items)
        offset += len(items)

        total = page.get("total")
        if not isinstance(total, int):
            raise ValueError("A szerver hibás oldalszám-adatot küldött.")
        if not items:
            if offset < total:
                raise ValueError("A szerver a csomaglista egy üres oldalát küldte vissza.")
            return parcels
        if offset >= total:
            return parcels
