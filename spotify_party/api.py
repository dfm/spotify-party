__all__ = ["request"]

from aiohttp import web, ClientSession
from . import auth


async def request(
    req: web.Request, path: str, method: str = "GET", **params
) -> dict:
    token = await auth.get_token(req)
    if token is None:
        return None

    params = dict(
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer {0}".format(token),
        },
        **params
    )
    print(params)
    async with ClientSession() as client:
        async with client.request(
            method, "https://api.spotify.com/v1{0}".format(path), **params
        ) as response:
            return await response.json()
