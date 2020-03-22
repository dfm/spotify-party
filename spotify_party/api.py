__all__ = [
    "call_api",
    "get_token",
    "refresh_token",
]

import time

import asyncio
import aiohttp_session
from aiohttp import web


def get_redirect_uri(request: web.Request) -> str:
    """Get the redirect URI that the Spotify API expects"""
    return str(
        request.url.with_path(str(request.app.router["callback"].url_for()))
    )


async def get_token(request: web.Request) -> str:
    """Get an authorization token for the user, refresh if needed"""
    session = await aiohttp_session.get_session(request)

    auth_info = session.get("sp_auth_info", None)
    if auth_info is None:
        raise web.HTTPUnauthorized()

    current_time = time.time()
    if auth_info.get("expires_at", current_time) - current_time <= 60:
        return await refresh_token(
            request, session, auth_info["refresh_token"]
        )

    return auth_info["access_token"]


async def refresh_token(
    request: web.Request, session: aiohttp_session.Session, code: str
) -> str:
    """Refresh the authorization with a refresh_token

    Args:
        code [str]: This can either be a refresh token or the initial code
            from the authorization flow

    Returns:
        The access token needed to sign the API requests

    """
    params = dict(headers={"Accept": "application/json"})
    params["data"] = dict(
        client_id=request.config_dict["config"]["spotify_client_id"],
        client_secret=request.config_dict["config"]["spotify_client_secret"],
        grant_type="authorization_code",
        code=code,
        redirect_uri=get_redirect_uri(request),
    )

    async with request.app["client_session"].post(
        "https://accounts.spotify.com/api/token", **params
    ) as response:
        response = await response.json()

    token = response["access_token"]
    session["sp_auth_info"] = dict(
        access_token=token,
        refresh_token=response["refresh_token"],
        expires_at=time.time() + int(response["expires_in"]),
    )

    return token


async def clear_token(request: web.Request) -> None:
    session = await aiohttp_session.get_session(request)
    del session["sp_auth_info"]


async def call_api(
    request: web.Request, path: str, method: str = "GET", **params
) -> dict:
    """Call the Spotify API

    Any other parameters will be included as arguments to
    :func:`aiohttp.ClientSession.request`.

    Args:
        path [str]: The API request path
        method [str]: The request method

    """
    token = await get_token(request)
    if token is None:
        return None

    data = dict(
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer {0}".format(token),
        },
        **params
    )
    response = await request.app["client_session"].request(
        method, "https://api.spotify.com/v1{0}".format(path), **data
    )
    async with response:
        # We've been rate limited!
        if response.status == 429:
            await asyncio.sleep(int(response.headers["Retry-After"]))
            return await call_api(request, path, method, **params)

        return await response.json()
