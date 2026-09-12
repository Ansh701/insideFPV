import asyncio
import json

from app.main import app


async def run() -> None:
    result = await app.state.monitor.run(trigger="scheduled")
    print(json.dumps(result.__dict__, default=str))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
