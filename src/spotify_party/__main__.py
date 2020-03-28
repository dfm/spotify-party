import argparse
from aiohttp import web
from spotify_party import get_config, app_factory, create_tables

parser = argparse.ArgumentParser()
parser.add_argument("config_file", type=str)
parser.add_argument("--create-tables", action="store_true")
args = parser.parse_args()

config = get_config(args.config_file)


if args.create_tables:
    create_tables(config["database_filename"])

else:
    web.run_app(app_factory(config), port=config["port"])
