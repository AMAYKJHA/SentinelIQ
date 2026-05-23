import asyncio
import httpx

from app.core.config import settings
from app.schemas.dto import GeoLocation, GeoResult

async def _fetch_geo(ip: str = ""):
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,lat,lon,city,region,country,countryCode,as"}
            )
            data = resp.json()
            
            if data.get("status") != "success":
                return None

            return GeoLocation(
                ip=ip,
                lat=data.get("lat"),
                lon=data.get("lon"),
                city=data.get("city", ""),
                country=data.get("country", ""),
                country_code=data.get("countryCode", "")
            )
    except Exception as e:
        return None


if __name__ == "__main__":
    asyncio.run(_fetch_geo())