from fastapi import FastAPI
from api import router
from lmnr import Laminar
from dotenv import load_dotenv

load_dotenv()
from config import settings

Laminar.initialize(
    base_url="http://localhost",
    http_port=8000,
    grpc_port=8001,
    project_api_key="y8RPCDg22GxxlCYBwFjHKO9MD6FiBn36b6RG7AKeQgiysjnkmlDVvIZsBVGQlf8b"
)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered GitLab MR reviewer",
    version="1.0.0",
    cors_allowed_origins="*",
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)