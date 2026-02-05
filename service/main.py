from fastapi import FastAPI
from api import router
from lmnr import Laminar
from dotenv import load_dotenv

load_dotenv()
from config import settings
from loguru import logger
from contextlib import asynccontextmanager
from infrastructure.mongo import connect_to_mongo, client

@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        logger.info("Starting up application...")
        await connect_to_mongo()

        Laminar.initialize(
            base_url=settings.LAMINAR_BASE_URL,
            http_port=settings.LAMINAR_HTTP_PORT,
            grpc_port=settings.LAMINAR_GRPC_PORT,
            project_api_key=settings.LAMINAR_PROJECT_API_KEY,
        )

        yield

    except Exception as e:
        logger.error(e)

    finally:
        logger.info("Shutting down application...")
        client.close()


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    cors_allowed_origins="*",
    lifespan=lifespan
)


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)