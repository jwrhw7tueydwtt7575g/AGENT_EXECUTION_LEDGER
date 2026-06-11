import asyncio
from database import connect_db, get_db
async def x():
    await connect_db()
    db = get_db()
    print("Runs:", await db.runs.count_documents({}))
    print("Receipts:", await db.receipts.count_documents({}))
asyncio.run(x())
