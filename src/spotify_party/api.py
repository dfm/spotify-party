__all__ = ["require_auth", "handle_auth", "update_auth", "call_api"]

import time
from functools import partial, wraps
from typing import Any, Awaitable, Callable, Optional, Tuple, Union

import aiohttp_session
from aiohttp import web
from aiohttp_spotify import SpotifyAuth, SpotifyResponse

from . import db


def require_auth(
    original_handler: Optional[
        Callable[[web.Request, db.User], Awaitable]
    ] = None,
    *,
    redirect: bool = True,
) -> Callable[..., Any]:
    """A decorator requiring that the user is authenticated to see a view

    Args:
        redirect (bool, optional): If true, the user will be redirected to the
            login page. Otherwise, a :class:`HTTPUnauthorized error is thrown.

    """
    if original_handler is None:
        return partial(_require_auth, redirect=redirect)
    return _require_auth(original_handler, redirect=redirect)


def _require_auth(
    handler: Callable[[web.Request, db.User], Awaitable],
    *,
    redirect: bool = True,
) -> Callable[[web.Request], Awaitable]:
    """This does the heavy lifting for the authorization check"""

    @wraps(handler)
    async def wrapped(request: web.Request) -> web.Response:
        session = await aiohttp_session.get_session(request)
        user_id = session.get("sp_user_id")
        user = await request.app["db"].get_user(user_id)
        if user_id is None or user is None:
            if not redirect:
                raise web.HTTPUnauthorized()
            raise web.HTTPTemporaryRedirect(
                location=request.app["spotify_app"]
                .router["auth"]
                .url_for()
                .with_query(redirect=request.url.path)
            )
        return await handler(request, user)

    return wrapped


async def handle_auth(request: web.Request, auth: SpotifyAuth) -> None:
    """This will be called at the end of the initial OAuth dance"""
    main_app = request.app["main_app"]
    response = await request.app["spotify_client"].request(
        main_app["client_session"], auth, "/me"
    )
    if response.status != 200:
        raise web.HTTPInternalServerError()

    user_info = response.json()
    user = await main_app["db"].add_user(
        user_info["id"], user_info["display_name"], response.auth
    )

    session = await aiohttp_session.get_session(request)
    session["sp_user_id"] = user.user_id


async def update_auth(
    request: web.Request, auth: SpotifyAuth
) -> Tuple[bool, SpotifyAuth]:
    auth_changed = False
    if auth.expires_at - time.time() <= 60:
        auth_changed = True
        auth = await request.app["spotify_app"]["spotify_client"].update_auth(
            request.app["client_session"], auth
        )
    return auth_changed, auth


async def call_api(
    request: web.Request,
    user: Union[db.User, None],
    endpoint: str,
    *,
    method: str = "GET",
    **kwargs,
) -> Union[SpotifyResponse, None]:
    """Call the Spotify API

    Args:
        request (web.Request): The current request
        user (Union[db.User, None]): The current user (this call will fail
            without one)
        endpoint (str): The API path
        method (str, optional): The HTTP request method. Defaults to "GET".

    Returns:
        Union[SpotifyResponse, None]: The response from the API

    """
    if user is None:
        return None

    response = await request.app["spotify_app"]["spotify_client"].request(
        request.app["client_session"],
        user.auth,
        endpoint,
        method=method,
        **kwargs,
    )

    # Update the authentication info if required
    if response.auth_changed:
        await request.app["db"].update_auth(user, response.auth)

    return response
