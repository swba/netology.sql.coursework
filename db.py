from os import getenv

import pydapper
from pydapper.commands import Commands


def get_url():
    """Returns the database connection URL"""
    db_host = getenv('DB_HOST')
    db_port = getenv('DB_PORT')
    db_name = getenv('DB_NAME')
    db_user = getenv('DB_USER')
    db_pass = getenv('DB_PASS')

    return f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

def connect() -> Commands:
    """Connects to the database"""
    return pydapper.connect(get_url())
