__all__ = ["setup", "require_auth"]

import secrets

import yarl
import aiohttp_session
from aiohttp import web

from . import api


def get_default_redirect(request: web.Request) -> str:
    """Get the URL to the main index page as the default redirect"""
    return str(request.app.router["index"].url_for())


async def handle_error(request: web.Request, error: str) -> web.Response:
    """Deal with errors in the authorization flow"""
    raise web.HTTPInternalServerError(
        text="Unhandled OAuth2 Error: {0}".format()
    )


async def login(request: web.Request) -> web.Response:
    """The view for the OAuth login flow"""
    session = await aiohttp_session.get_session(request)

    # Get the current redirect URL
    session["redirect"] = request.query.get(
        "redirect", get_default_redirect(request)
    )

    # Generate a state token
    state = secrets.token_urlsafe()
    session["state"] = state

    # Construct the API OAuth2 URL
    location = yarl.URL("https://accounts.spotify.com/authorize").with_query(
        client_id=request.config_dict["config"]["spotify_client_id"],
        response_type="code",
        redirect_uri=api.get_redirect_uri(request),
        state=state,
        scope=",".join(
            [
                "streaming",
                "user-read-email",
                "user-read-private",
                "user-modify-playback-state",
                "user-read-playback-state",
                "user-read-currently-playing",
            ]
        ),
    )

    return web.HTTPTemporaryRedirect(location=str(location))


async def logout(request: web.Request) -> web.Response:
    """Clear the login info and log out"""
    await api.clear_token()
    return web.Response(body="logged out")


async def callback(request: web.Request) -> web.Response:
    """View to deal with an OAuth response from the Spotify API"""
    session = await aiohttp_session.get_session(request)

    # Check that the 'state' matches
    state = session.get("state", None)
    returned_state = request.query.get("state", None)
    if None in (state, returned_state) or state != returned_state:
        raise web.HTTPBadRequest()

    # The request didn't go through or the user blocked the request
    if "error" in request.query:
        return handle_error(
            request, request.query.get("error", "unknown error")
        )

    # Get the actual tokens
    await api.refresh_token(request, session, request.query["code"])

    # Get the user's Spotify info
    session["sp_user_info"] = await api.call_api(request, "/me")

    return web.HTTPTemporaryRedirect(
        location=session.get("redirect", get_default_redirect(request))
    )


def setup(app: web.Application) -> None:
    """Add the auth routes to an existing app"""
    app.add_routes(
        [
            web.get("/spotify/login", login, name="login"),
            web.get("/spotify/logout", logout, name="logout"),
            web.get("/spotify/callback", callback, name="callback"),
        ]
    )


async def require_auth(request: web.Request) -> None:
    try:
        await api.get_token(request)
    except web.HTTPUnauthorized:
        raise web.HTTPTemporaryRedirect(
            location=str(request.app.router["login"].url_for())
        )
