import sys
from aiohttp import web
from spotify_party import config, app_factory

cfg = config.get_config(sys.argv[1])
web.run_app(app_factory(cfg), port=cfg["port"])
