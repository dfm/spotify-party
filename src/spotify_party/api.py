__all__ = ["require_auth", "handle_auth", "call_api"]

from functools import wraps
from typing import Callable, Awaitable, Union

import aiohttp_session
from aiohttp import web
from aiohttp_spotify import SpotifyAuth, SpotifyResponse

from . import db


def require_auth(
    handler: Callable[[web.Request, db.User], Awaitable]
) -> Callable[[web.Request], Awaitable]:
    """A decorator requiring that the user is authenticated to see a view"""

    @wraps(handler)
    async def wrapped(request: web.Request) -> web.Response:
        session = await aiohttp_session.get_session(request)
        user_id = session.get("sp_user_id")
        user = await request.app["db"].get_user(user_id)
        if user_id is None or user is None:
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


async def call_api(
    request: web.Request,
    user: Union[db.User, None],
    endpoint: str,
    *,
    method: str = "GET",
    **kwargs
) -> Union[SpotifyResponse, None]:
    if user is None:
        return None

    response = await request.app["spotify_app"]["spotify_client"].request(
        request.app["client_session"],
        user.auth,
        endpoint,
        method=method,
        **kwargs
    )

    # Update the authentication info if required
    if response.auth_changed:
        await request.app["db"].update_auth(user, response.auth)

    return response
