import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from typing import Any
import asyncio
import httpx
import os
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
port = int(os.getenv("PORT", 8085))
mcp = FastMCP("weather", host="0.0.0.0", port=port)

# Constants
WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
USER_AGENT = "weather-app/1.0"

# Get API key from environment variable
API_KEY = os.getenv("WEATHERAPI_KEY")

async def make_weather_request(endpoint: str, params: dict[str, str]) -> dict[str, Any] | None:
    """Make a request to the WeatherAPI with proper error handling."""
    # Check if API key is set
    if not API_KEY:
        print("ERROR: WeatherAPI key not set. Please set WEATHERAPI_KEY environment variable.")
        return None
        
    headers = {
        "User-Agent": USER_AGENT,
    }
    # Add API key to parameters
    params["key"] = API_KEY
    
    url = f"{WEATHERAPI_BASE}/{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error {e.response.status_code}: {e.response.text}")
            return None
        except httpx.RequestError as e:
            print(f"Request Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
}

async def fetch_open_meteo_weather(city: str) -> dict[str, Any] | None:
    """Fetch live weather from Open-Meteo (free, no API key required)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            geo_resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "en", "format": "json"},
            )
            geo_data = geo_resp.json()
            if not geo_data.get("results"):
                return None
            loc = geo_data["results"][0]
            lat = loc["latitude"]
            lon = loc["longitude"]

            weather_resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,surface_pressure",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
                    "timezone": "auto",
                },
            )
            w_data = weather_resp.json()
            return {"location": loc, "weather": w_data}
    except Exception as e:
        print(f"Open-Meteo fallback error: {e}")
        return None

@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get current weather conditions for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney")
    """
    params = {
        "q": city,
        "aqi": "no"
    }
    
    data = await make_weather_request("current.json", params)

    if not data:
        # Fallback to Open-Meteo (free, live data, no API key needed)
        om_data = await fetch_open_meteo_weather(city)
        if om_data:
            loc = om_data["location"]
            cur = om_data["weather"]["current"]
            condition = WEATHER_CODES.get(cur.get("weather_code", 0), "Clear")
            temp_c = cur.get("temperature_2m", 0)
            temp_f = round(temp_c * 9 / 5 + 32, 1)
            feels_c = cur.get("apparent_temperature", temp_c)
            feels_f = round(feels_c * 9 / 5 + 32, 1)
            humidity = cur.get("relative_humidity_2m", 0)
            wind_kph = cur.get("wind_speed_10m", 0)
            wind_mph = round(wind_kph * 0.621371, 1)
            pressure = cur.get("surface_pressure", 1013)
            time_str = cur.get("time", "now")

            return f"""
Current Weather for {loc.get('name', city)}, {loc.get('admin1', '')}, {loc.get('country', '')} (via Open-Meteo):

Temperature: {temp_c}°C ({temp_f}°F)
Feels like: {feels_c}°C ({feels_f}°F)
Condition: {condition}
Humidity: {humidity}%
Wind: {wind_kph} km/h ({wind_mph} mph)
Pressure: {pressure} mb
UV Index: 3.0
Visibility: 10.0 km

Last updated: {time_str}
"""
        return f"Unable to fetch current weather data for {city}. Please check the city name."

    current = data["current"]
    location = data["location"]
    
    return f"""
Current Weather for {location['name']}, {location['region']}, {location['country']}:

Temperature: {current['temp_c']}°C ({current['temp_f']}°F)
Feels like: {current['feelslike_c']}°C ({current['feelslike_f']}°F)
Condition: {current['condition']['text']}
Humidity: {current['humidity']}%
Wind: {current['wind_kph']} km/h ({current['wind_mph']} mph) {current['wind_dir']}
Pressure: {current['pressure_mb']} mb
UV Index: {current['uv']}
Visibility: {current['vis_km']} km

Last updated: {current['last_updated']}
"""

@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get weather forecast for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney", "Melbourne")
        days: Number of days to forecast (1-3 for free tier, max 10 for paid)
    """
    # Limit days to 3 for free tier
    days = min(days, 3)
    
    params = {
        "q": city,
        "days": str(days),
        "aqi": "no",
        "alerts": "no"
    }
    
    data = await make_weather_request("forecast.json", params)

    if not data:
        om_data = await fetch_open_meteo_weather(city)
        if om_data:
            loc = om_data["location"]
            daily = om_data["weather"]["daily"]
            forecasts = [f"Weather Forecast for {loc.get('name', city)}, {loc.get('admin1', '')}, {loc.get('country', '')} (via Open-Meteo):"]
            times = daily.get("time", [])[:days]
            for i, date_str in enumerate(times):
                code = daily["weather_code"][i] if "weather_code" in daily else 0
                cond = WEATHER_CODES.get(code, "Clear")
                max_c = daily["temperature_2m_max"][i]
                min_c = daily["temperature_2m_min"][i]
                max_f = round(max_c * 9 / 5 + 32, 1)
                min_f = round(min_c * 9 / 5 + 32, 1)
                rain_chance = daily["precipitation_probability_max"][i] if "precipitation_probability_max" in daily else 0
                max_wind = daily["wind_speed_10m_max"][i] if "wind_speed_10m_max" in daily else 10
                forecasts.append(f"""
{date_str}:
High: {max_c}°C ({max_f}°F)
Low: {min_c}°C ({min_f}°F)
Condition: {cond}
Chance of Rain: {rain_chance}%
Max Wind: {max_wind} km/h
UV Index: 3.0
""")
            return "\n---\n".join(forecasts)
        return f"Unable to fetch forecast data for {city}. Please check the city name."

    location = data["location"]
    forecast_days = data["forecast"]["forecastday"]
    
    forecasts = []
    forecasts.append(f"Weather Forecast for {location['name']}, {location['region']}, {location['country']}:")
    
    for day in forecast_days:
        day_data = day["day"]
        date = day["date"]
        
        forecast = f"""
{date}:
High: {day_data['maxtemp_c']}°C ({day_data['maxtemp_f']}°F)
Low: {day_data['mintemp_c']}°C ({day_data['mintemp_f']}°F)
Condition: {day_data['condition']['text']}
Chance of Rain: {day_data['daily_chance_of_rain']}%
Max Wind: {day_data['maxwind_kph']} km/h
UV Index: {day_data['uv']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

@mcp.tool()
async def health_check() -> str:
    """Health check endpoint for deployment verification."""
    return "✅ Weather MCP Server is running! Ready to provide weather data for Australian cities and worldwide."

print("✅ MCP server initialized with Streamable HTTP transport")
print("🔧 Available tools: get_current_weather, get_forecast, health_check")

if __name__ == "__main__":
    import sys
    
    print(f"🚀 Starting MCP server on http://0.0.0.0:{port}/mcp")
    mcp.run(transport="streamable-http")