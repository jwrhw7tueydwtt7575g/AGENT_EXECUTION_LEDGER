import os
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "agent_ledger")

client: AsyncIOMotorClient = None
db = None


def _mongo_host_label() -> str:
    if not MONGO_URL:
        return "unknown"
    try:
        parsed = urlparse(MONGO_URL.replace("mongodb+srv://", "https://").replace("mongodb://", "http://"))
        return parsed.hostname or "unknown"
    except Exception:
        return "unknown"


async def connect_db():
    global client, db
    if not MONGO_URL:
        raise ValueError("MONGO_URL environment variable is not set. Please configure it in .env file.")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.receipts.create_index([("run_id", 1), ("timestamp", 1)])
    await db.receipts.create_index([("run_id", 1), ("step_index", 1)])
    await db.receipts.create_index([("receipt_id", 1)], unique=True)
    await db.receipts.create_index([("node_status", 1)])
    await db.receipts.create_index([("timestamp", -1)])
    await db.runs.create_index([("run_id", 1)], unique=True)
    await db.runs.create_index([("started_at", -1)])
    await db.run_state.create_index([("run_id", 1)], unique=True)
    print(f"Connected to MongoDB host: {_mongo_host_label()}, database: {DB_NAME}")


async def close_db():
    global client
    if client:
        client.close()
        print("Disconnected from MongoDB")


def get_db():
    if db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return db
