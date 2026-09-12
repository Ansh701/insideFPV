import asyncio
import json

from app.db import SessionFactory
from app.services.seed import seed_database


async def run() -> None:
    async with SessionFactory() as session:
        result = await seed_database(session)
    print(json.dumps(result.__dict__))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
