__all__ = ["GLOBALS"]

from typing import Any, Dict, cast

import jinja2
from aiohttp import web
from yarl import URL


@jinja2.contextfunction
def room_url(
    context: Dict[str, Any], __route_name: str, *, room_id: str
) -> URL:
    app = cast(web.Application, context["app"])
    user_id, room_name = room_id.split("/")
    return app.router[__route_name].url_for(
        user_id=user_id, room_name=room_name
    )


GLOBALS = dict(room_url=room_url)
