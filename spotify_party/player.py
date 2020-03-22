__all__ = ["setup"]

from aiohttp import web

from . import api


async def token(request: web.Request) -> web.Response:
    """A view to access the token from the web player"""
    token = await api.get_token(request)
    return web.json_response(dict(token=token))


def setup(app: web.Application) -> None:
    app.add_routes([web.get("/player/token", token, name="token")])
