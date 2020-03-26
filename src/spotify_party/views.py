__all__ = ["index"]

from aiohttp import web
import aiohttp_jinja2

from . import db, api

routes = web.RouteTableDef()


@routes.get("/", name="index")
async def index(request: web.Request) -> web.Response:
    return aiohttp_jinja2.render_template(
        "layout.html", request, {"logged_in": False}
    )


@routes.get("/about", name="about")
async def about(request: web.Request) -> web.Response:
    return web.Response(body="about page")


@routes.get("/me", name="me")
@api.require_auth
async def me(request: web.Request, user: db.User) -> web.Response:
    return web.json_response(
        dict(user_id=user.user_id, display_name=user.display_name)
    )
