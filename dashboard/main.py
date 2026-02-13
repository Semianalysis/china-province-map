from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routes import map as map_routes
from .routes import api as api_routes

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="China Province Semiconductor Map")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(map_routes.router)
app.include_router(api_routes.router, prefix="/api")
