import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("MONGO_DB", "hexagon")

client: AsyncIOMotorClient | None = None


async def get_db():
  global client
  if client is None:
    client = AsyncIOMotorClient(MONGO_URL)
  return client[DB_NAME]
