from os import getenv

from sqlalchemy import create_engine, Engine


class Db:
    """Database manager"""

    def __init__(self):
        db_host = getenv('DB_HOST')
        db_port = getenv('DB_PORT')
        db_name = getenv('DB_NAME')
        db_user = getenv('DB_USER')
        db_pass = getenv('DB_PASS')

        url = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        self.engine = create_engine(url)

    def get_engine(self) -> Engine:
        """Returns DB engine"""
        return self.engine
