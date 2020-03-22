from typing import Generator

from aiohttp import web, ClientSession


async def client_session(app: web.Application) -> Generator[None, None, None]:
    async with ClientSession() as session:
        app["client_session"] = session
        yield
