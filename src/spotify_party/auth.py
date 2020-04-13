__all__ = ["require_auth", "handle_auth", "update_auth", "call_api"]

import time
from functools import partial, wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, Tuple

import aiohttp_session
from aiohttp import web
from aiohttp_spotify import SpotifyAuth, SpotifyResponse

if TYPE_CHECKING:
    from .data_model import User  # NOQA


def require_auth(
    original_handler: Optional[
        Callable[[web.Request, "User"], Awaitable]
    ] = None,
    *,
    redirect: bool = True,
    admin: bool = False,
) -> Callable[..., Any]:
    """A decorator requiring that the user is authenticated to see a view

    Args:
        redirect (bool, optional): If true, the user will be redirected to the
            login page. Otherwise, a :class:`HTTPUnauthorized error is thrown.

    """
    if original_handler is None:
        return partial(_require_auth, redirect=redirect, admin=admin)
    return _require_auth(original_handler, redirect=redirect, admin=admin)


def _require_auth(
    handler: Callable[[web.Request, "User"], Awaitable],
    *,
    redirect: bool = True,
    admin: bool = False,
) -> Callable[[web.Request], Awaitable]:
    """This does the heavy lifting for the authorization check"""

    @wraps(handler)
    async def wrapped(request: web.Request) -> web.Response:
        session = await aiohttp_session.get_session(request)
        user_id = session.get("sp_user_id")
        user = await request.config_dict["db"].get_user(user_id)
        if user is None:
            if admin:
                return web.HTTPNotFound()
            if not redirect:
                raise web.HTTPUnauthorized()
            raise web.HTTPTemporaryRedirect(
                location=request.config_dict["spotify_app"]
                .router["auth"]
                .url_for()
                .with_query(redirect=request.url.path)
            )

        if admin and user.user_id not in request.app["config"]["admins"]:
            return web.HTTPNotFound()

        async with user:
            await user.update_auth(request)
            return await handler(request, user)

    return wrapped


async def handle_auth(request: web.Request, auth: SpotifyAuth) -> None:
    """This will be called at the end of the initial OAuth dance"""
    response = await request.app["spotify_client"].request(
        request.config_dict["client_session"], auth, "/me"
    )
    if response.status != 200:
        raise web.HTTPInternalServerError()

    user_info = response.json()

    if user_info.get("product", "free") != "premium":
        raise web.HTTPTemporaryRedirect(
            location=request.app["main_app"].router["premium"].url_for()
        )

    user = await request.config_dict["db"].add_user(
        user_info["id"], user_info["display_name"], response.auth
    )

    session = await aiohttp_session.get_session(request)
    session["sp_user_id"] = user.user_id


async def update_auth(
    request: web.Request, auth: SpotifyAuth
) -> Tuple[bool, SpotifyAuth]:
    auth_changed = False
    if auth.expires_at - time.time() <= 600:  # 10 minutes
        auth_changed = True
        auth = await request.config_dict["spotify_app"][
            "spotify_client"
        ].update_auth(request.config_dict["client_session"], auth)
    return auth_changed, auth


async def call_api(
    request: web.Request,
    user: Optional["User"],
    endpoint: str,
    *,
    method: str = "GET",
    **kwargs,
) -> Optional[SpotifyResponse]:
    """Call the Spotify API

    Args:
        request (web.Request): The current request
        user (Optional[User]): The current user (this call will fail
            without one)
        endpoint (str): The API path
        method (str, optional): The HTTP request method. Defaults to "GET".

    Returns:
        Optional[SpotifyResponse]: The response from the API

    """
    if user is None:
        return None

    response = await request.config_dict["spotify_app"][
        "spotify_client"
    ].request(
        request.config_dict["client_session"],
        user.auth,
        endpoint,
        method=method,
        **kwargs,
    )

    # Update the authentication info if required
    if response.auth_changed:
        user.auth = response.auth

    return response
