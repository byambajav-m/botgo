from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from config import settings
from db.models import Review

client = AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.MONGO_DB_NAME]

async def connect_to_mongo():
    try:
        await db.command("ping")
        await init_beanie(database=db, document_models=[Review])
        print("MongoDB connected and Beanie initialized!")

    except Exception as e:
        print(f"MongoDB connection failed: {e}")