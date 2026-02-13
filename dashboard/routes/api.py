import json
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "provinces.json"

_provinces_cache: dict | None = None


def _load_provinces() -> dict:
    global _provinces_cache
    if _provinces_cache is None:
        with open(DATA_PATH) as f:
            _provinces_cache = json.load(f)
    return _provinces_cache


@router.get("/provinces")
async def get_provinces():
    return JSONResponse(_load_provinces())


@router.get("/province/{adcode}")
async def get_province(adcode: str, request: Request):
    provinces = _load_provinces()
    data = provinces.get(adcode)
    if not data:
        return JSONResponse({"error": "Province not found"}, status_code=404)
    return templates.TemplateResponse(
        "partials/province_panel.html",
        {"request": request, "province": data, "adcode": adcode},
    )
