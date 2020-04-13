import argparse
import sqlite3

from aiohttp import web

from spotify_party import app_factory, create_tables, get_config

parser = argparse.ArgumentParser()
parser.add_argument("config_file", type=str)
parser.add_argument("--create-tables", action="store_true")
args = parser.parse_args()

config = get_config(args.config_file)


if args.create_tables:
    try:
        create_tables(config["database_filename"])
    except sqlite3.OperationalError:
        print("Tables already exist")

else:
    web.run_app(app_factory(config), port=config["port"])
