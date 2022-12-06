import re
import aiosqlite
import discord
from os.path import abspath, isfile
from typing import Type, Any, Optional, List, Dict
import logging

DSLOGGER = logging.getLogger("discord")
# See https://stackoverflow.com/questions/12179271/meaning-of-classmethod-and-staticmethod-for-beginner

class DatabaseManager:
    def __init__(self, *, database_file_path: str, database_schema_path: str | None = None):
        self.database_file_path: Type[str] = abspath(database_file_path)
        self.database_schema_path = abspath(database_schema_path) if database_schema_path is not None else None
        self._database_connection: aiosqlite.Connection | None = None
        self._is_connected: bool = False
        self._db_already_exists: bool = False


    async def __aenter__(self):
        DSLOGGER.log(logging.INFO, "Attempting connection to the database...")

        if isfile(self.database_file_path):
            self._db_already_exists = True

        if not self._is_connected:
            self._database_connection = await aiosqlite.connect(self.database_file_path)
            self._is_connected = True
        else:
            DSLOGGER.log(logging.WARN, "You're already connected to a database!")

        if self._is_connected:
            DSLOGGER.log(logging.INFO, f"Successfully connected to {self.database_file_path}")

        if self.database_schema_path is not None and not self._db_already_exists:
            DSLOGGER.log(logging.INFO, "Attempting to load schema...")
            await self.__load_schema(self.database_schema_path)
            DSLOGGER.log(logging.INFO, f"Successfully loaded {self.database_schema_path} schema.")

        elif self.database_schema_path is not None and self._db_already_exists:
            DSLOGGER.log(logging.WARN, "Database file already exists, skipping schema...")

        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        DSLOGGER.log(logging.INFO, "Attempting to disconnect from the database...")

        if self._is_connected:
            await self._database_connection.close()
            self._is_connected = False
        else:
            DSLOGGER.log(logging.WARN, "You are not connected to any database!")

        if not self._is_connected:
            DSLOGGER.log(logging.INFO, "Successfully disconnected from the database.")


    async def _create_cursor(self) -> aiosqlite.Cursor:
        """`Async method`\n
        Internal private method to create a new cursor using the given database connection.

        Returns:
            `aiosqlite.Cursor`: The new cursor to be used.
        """
        cursor: aiosqlite.Cursor = await self._database_connection.cursor()
        return cursor


    async def __load_schema(self, schema: str) -> None:
        """`Async method`\n
        Internal private method to load a given schema into a database.

        Args:
            schema (str): The path to the schema file.
        """
        with open(schema) as s:
            _schema = s.read()

        await self._database_connection.executescript(_schema)
        await self._database_connection.commit()


class ItemsDatabaseManager(DatabaseManager):
    def __init__(self, *, database_file_path: str, database_schema_path: str | None = None):
        super().__init__(database_file_path=database_file_path, database_schema_path=database_schema_path)

    
    async def get_weapons_specials(self, table: str, base_item: str) -> List[Dict[str, Any]]:

        table = re.sub(r"[^a-zA-Z0-9_\-]", "", table)
        base_item = re.sub(r"[^a-zA-Z0-9_\-]", "", base_item)

        cursor: aiosqlite.Cursor = await self._create_cursor()

        await cursor.execute(f"""
            SELECT {table}_specials.* FROM {table}
            INNER JOIN {table}_specials
            ON {table}.id = {table}_specials.is_from
            WHERE melee.name = "{base_item}"
        """)

        columns = [description[0] for description in cursor.description]
        rows = [dict(zip(columns, row)) for row in await cursor.fetchall()]

        await cursor.close()

        return rows