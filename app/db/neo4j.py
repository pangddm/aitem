from __future__ import annotations

import os
from typing import Optional


from neo4j import AsyncGraphDatabase, AsyncDriver


from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


class Neo4j:


    def __init__(

        self,

        uri: str = "bolt://localhost:7687",

        user: str = os.getenv("NEO4J_USER"),

        password: str = os.getenv("NEO4J_PASSWORD"),

    ):

        self.uri = uri

        self.user = user

        self.password = password

        self.driver: Optional[AsyncDriver] = None



    async def connect(self):


        if self.driver is not None:

            return



        self.driver = (
            AsyncGraphDatabase.driver(

                self.uri,

                auth=(

                    self.user,

                    self.password

                )

            )
        )


        await self.driver.verify_connectivity()


        print(
            "Neo4j connected."
        )



    async def close(self):


        if self.driver:


            await self.driver.close()


            self.driver = None


            print(
                "Neo4j closed."
            )



    def get_driver(self):


        if self.driver is None:

            raise RuntimeError(

                "Neo4j is not connected."

            )


        return self.driver



neo4j = Neo4j()



neo4j_driver = neo4j