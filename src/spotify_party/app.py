__all__ = ["app_factory"]

import base64
import pathlib
from typing import Any, AsyncIterator, Mapping

import aiohttp_jinja2
import aiohttp_session
import aiohttp_spotify
import jinja2
import pkg_resources
from aiohttp import ClientSession, web
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet

from . import api, db, interface, views


def get_resource_path(path: str) -> pathlib.Path:
    return pathlib.Path(
        pkg_resources.resource_filename(__name__, path)
    ).resolve()


async def client_session(app: web.Application) -> AsyncIterator[None]:
    """A fixture to create a single ClientSession for the app to use"""
    async with ClientSession() as session:
        app["client_session"] = session
        yield


def app_factory(config: Mapping[str, Any]) -> web.Application:
    app = web.Application()

    # load the configuration file
    app["config"] = config

    # Add the client session for pooling outgoing connections
    app.cleanup_ctx.append(client_session)

    # Connect the database and set up a map of websockets
    app["db"] = db.Database(config["database_filename"])

    # And the routes for the main app
    app.add_routes(views.routes)
    app.add_routes(interface.routes)

    # Set up the user session for cookies
    secret_key = base64.urlsafe_b64decode(fernet.Fernet.generate_key())
    aiohttp_session.setup(app, EncryptedCookieStorage(secret_key))

    # Set up the templating engine and the static endpoint
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(get_resource_path("templates"))
    )
    app["static_root_url"] = "/assets"
    app.router.add_static("/assets", get_resource_path("assets"))

    # Set up the Spotify app to instigate the OAuth flow
    app["spotify_app"] = aiohttp_spotify.spotify_app(
        client_id=config["spotify_client_id"],
        client_secret=config["spotify_client_secret"],
        redirect_uri=config["spotify_redirect_uri"],
        handle_auth=api.handle_auth,
        default_redirect=app.router["play"].url_for(),
        scope=[
            "streaming",
            "user-read-email",
            "user-read-private",
            "user-modify-playback-state",
            "user-read-playback-state",
            "user-read-currently-playing",
        ],
    )
    app["spotify_app"]["main_app"] = app
    app.add_subapp("/spotify", app["spotify_app"])

    # Attach the socket.io interface
    interface.sio.attach(app)

    return app
