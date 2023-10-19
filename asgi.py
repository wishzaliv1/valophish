import uvloop
import asyncio
from server import app
from hypercorn.asyncio import serve
from hypercorn.config import Config

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

async def run():
    config = Config.from_mapping(bind="0.0.0.0:8000", workers=4)
    await serve(app, config)

if __name__ == "__main__":
    asyncio.run(run())
