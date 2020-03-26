from typing import AsyncIterator

from aiohttp import web, ClientSession


async def client_session(app: web.Application,) -> AsyncIterator[None]:
    async with ClientSession() as session:
        app["client_session"] = session
        yield
