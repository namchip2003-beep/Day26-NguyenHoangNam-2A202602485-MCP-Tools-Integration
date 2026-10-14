"""Client test cho versioned_server.py — gọi cả tool v1, v2 và đọc server metadata."""

import asyncio
import json
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["versioned_server.py"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Đọc server metadata
            info = await session.read_resource("server://info")
            meta = json.loads(info.contents[0].text)
            print(f"Server: {meta['name']} v{meta['version']}")
            print(f"Deprecated tools: {meta['deprecated_tools']}")
            print(f"Migration: {meta['migration_guide']}\n")

            # 2. Liệt kê tools
            tools = await session.list_tools()
            print("Tools:")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")
            print()

            # 3. Gọi tool v1 (deprecated nhưng vẫn hoạt động)
            r1 = await session.call_tool("get_weather", {"city": "Hanoi"})
            print(f"[v1] get_weather('Hanoi'):\n  {r1.content[0].text}\n")

            # 4. Gọi tool v2
            r2 = await session.call_tool("get_weather_v2", {
                "city": "Hanoi",
                "include_forecast": True,
                "units": "celsius",
            })
            print(f"[v2] get_weather_v2('Hanoi', forecast=True):")
            print(f"  {json.dumps(json.loads(r2.content[0].text), indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
