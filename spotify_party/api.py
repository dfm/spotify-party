__all__ = [
    "call_api",
    "get_token",
    "refresh_token",
    "require_auth",
]

import time
from typing import Any, Dict, Union

import asyncio
import aiohttp_session
from aiohttp import web


def get_redirect_uri(request: web.Request) -> str:
    """Get the redirect URI that the Spotify API expects"""
    return str(
        request.url.with_path(str(request.app.router["callback"].url_for()))
    )


async def get_token(
    request: web.Request, user_id: Union[str, None] = None
) -> str:
    """Get an authorization token for the user, refresh if needed"""
    session = await aiohttp_session.get_session(request)

    if user_id is None:
        user_id = session.get("sp_user_id", None)
        if user_id is None:
            raise web.HTTPUnauthorized()

    user = request.app["db"].get_user(user_id)
    if user is None:
        raise web.HTTPUnauthorized()

    current_time = time.time()
    if user.expires_at - current_time <= 60:
        auth_info = await refresh_token(request, session, user.refresh_token)
        user.access_token = auth_info["access_token"]
        user.refresh_token = auth_info["refresh_token"]
        user.expires_at = auth_info["expires_at"]

    return user.access_token


async def refresh_token(
    request: web.Request, session: aiohttp_session.Session, code: str
) -> Dict[str, Any]:
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

    return dict(
        access_token=response["access_token"],
        refresh_token=response["refresh_token"],
        expires_at=time.time() + int(response["expires_in"]),
    )


async def clear_token(request: web.Request) -> None:
    session = await aiohttp_session.get_session(request)
    session.pop("sp_user_id", None)


async def require_auth(request: web.Request) -> None:
    """Helper for routes that require authorization"""
    try:
        await get_token(request)
    except web.HTTPUnauthorized:
        raise web.HTTPTemporaryRedirect(
            location=str(
                request.app.router["login"]
                .url_for()
                .with_query(dict(redirect=request.url.path))
            )
        )


async def call_api(
    request: web.Request,
    path: str,
    method: str = "GET",
    token: Union[str, None] = None,
    user_id: Union[str, None] = None,
    **params
) -> dict:
    """Call the Spotify API

    Any other parameters will be included as arguments to
    :func:`aiohttp.ClientSession.request`.

    Args:
        path [str]: The API request path
        method [str]: The request method

    """
    if token is None:
        token = await get_token(request, user_id=user_id)
        if token is None:
            raise web.HTTPUnauthorized()

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
            return await call_api(
                request, path, method, token=token, user_id=user_id, **params
            )

        if response.status == 204:
            return {}

        return await response.json()
