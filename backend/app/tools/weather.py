import httpx

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取指定城市的当前天气信息。当用户询问某个城市的天气时调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，例如：北京、上海、哈尔滨",
                }
            },
            "required": ["city"],
        },
    },
}

#这个工具是通过这个城市的经纬度来获取天气的
async def get_weather(city:str)->dict:
    """获取指定城市的当前天气"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 1. 城市名 -> 经纬度
            geo_resp =await client.get(
                GEO_URL,
                params={"name": city, "count": 1, "language": "zh"},
                timeout=10,
            )
            geo_resp.raise_for_status()
            results = geo_resp.json().get("results")
            if not results:
                return {"city": city, "error": f"找不到城市：{city}"}

            loc = results[0]
            lat, lon = loc["latitude"], loc["longitude"]

            # 2. 查当前天气
            weather_resp = await client.get(
                WEATHER_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                },
                timeout=10,
            )
            weather_resp.raise_for_status()
            current = weather_resp.json()["current"]

            return {
                "city": loc["name"],
                "country": loc.get("country"),
                "temperature": current["temperature_2m"],
                "humidity": current["relative_humidity_2m"],
                "wind_speed": current["wind_speed_10m"],
                "weather_code": current["weather_code"],
            }

    except httpx.RequestException as e:
        return {"city": city, "error": f"请求天气服务失败：{e}"}

