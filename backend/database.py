import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://vivekchaudhari3718:vivekchaudhari3718@cluster1.9qlun5j.mongodb.net/?retryWrites=true&w=majority"
)
DB_NAME = os.getenv("DB_NAME", "agent_ledger")

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    # Create indexes for efficient querying
    await db.receipts.create_index([("run_id", 1), ("timestamp", 1)])
    await db.runs.create_index([("run_id", 1)], unique=True)
    await db.runs.create_index([("started_at", -1)])
    print(f"Connected to MongoDB at {MONGO_URL}, database: {DB_NAME}")


async def close_db():
    global client
    if client:
        client.close()
        print("Disconnected from MongoDB")


def get_db():
    return db
