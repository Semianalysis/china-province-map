import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "provinces.json"
SEMI_COMPANIES_PATH = Path(__file__).resolve().parent.parent / "data" / "semi_companies.json"
AI_COMPANY_PROFILES_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_company_profiles.json"

_provinces_cache: dict | None = None
_semi_companies_cache: list | None = None
_ai_company_profiles_cache: list | None = None
_schema_report_cache: dict | None = None


def _load_provinces() -> dict:
    global _provinces_cache
    if _provinces_cache is None:
        with open(DATA_PATH) as f:
            _provinces_cache = json.load(f)
    return _provinces_cache


def _load_semi_companies() -> list:
    global _semi_companies_cache
    if _semi_companies_cache is None:
        with open(SEMI_COMPANIES_PATH) as f:
            data = json.load(f)
            _semi_companies_cache = data if isinstance(data, list) else []
    return _semi_companies_cache


def _load_ai_company_profiles() -> list:
    global _ai_company_profiles_cache
    if _ai_company_profiles_cache is None:
        with open(AI_COMPANY_PROFILES_PATH) as f:
            data = json.load(f)
            companies = data.get("companies", []) if isinstance(data, dict) else []
            _ai_company_profiles_cache = companies if isinstance(companies, list) else []
    return _ai_company_profiles_cache


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_provinces_schema(provinces: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    if not isinstance(provinces, dict):
        return {
            "ok": False,
            "summary": {"provinces": 0, "errors": 1, "warnings": 0},
            "issues": [{"level": "error", "path": "$", "message": "Top-level payload must be an object keyed by adcode."}],
        }

    for adcode, province in provinces.items():
        base_path = f"$.{adcode}"
        if not isinstance(province, dict):
            issues.append({"level": "error", "path": base_path, "message": "Province entry must be an object."})
            continue

        for field in ("name_en", "name_cn", "region", "metrics"):
            if field not in province:
                issues.append({"level": "error", "path": base_path, "message": f"Missing required field '{field}'."})

        metrics = province.get("metrics", {})
        if not isinstance(metrics, dict) or not metrics:
            issues.append({"level": "error", "path": f"{base_path}.metrics", "message": "Metrics must be a non-empty object."})
        else:
            for metric_key, metric in metrics.items():
                metric_path = f"{base_path}.metrics.{metric_key}"
                if not isinstance(metric, dict):
                    issues.append({"level": "error", "path": metric_path, "message": "Metric must be an object."})
                    continue
                if "value" not in metric:
                    issues.append({"level": "error", "path": metric_path, "message": "Missing required metric field 'value'."})
                elif not _is_number(metric["value"]):
                    issues.append({"level": "error", "path": f"{metric_path}.value", "message": "Metric value must be numeric."})
                if "label" in metric and not isinstance(metric["label"], str):
                    issues.append({"level": "warning", "path": f"{metric_path}.label", "message": "Metric label should be a string."})
                if "unit" in metric and not isinstance(metric["unit"], str):
                    issues.append({"level": "warning", "path": f"{metric_path}.unit", "message": "Metric unit should be a string."})

        fabs = province.get("fabs", [])
        if fabs is not None and not isinstance(fabs, list):
            issues.append({"level": "error", "path": f"{base_path}.fabs", "message": "Fabs must be an array when provided."})
        elif isinstance(fabs, list):
            for i, fab in enumerate(fabs):
                fab_path = f"{base_path}.fabs[{i}]"
                if not isinstance(fab, dict):
                    issues.append({"level": "error", "path": fab_path, "message": "Fab entry must be an object."})
                    continue
                if "name" not in fab:
                    issues.append({"level": "warning", "path": fab_path, "message": "Fab is missing name."})
                if "capacity_kwpm" in fab and not _is_number(fab["capacity_kwpm"]):
                    issues.append({"level": "warning", "path": f"{fab_path}.capacity_kwpm", "message": "Fab capacity_kwpm should be numeric."})

        companies = province.get("companies", [])
        if companies is not None and not isinstance(companies, list):
            issues.append({"level": "error", "path": f"{base_path}.companies", "message": "Companies must be an array when provided."})

    errors = sum(1 for i in issues if i["level"] == "error")
    warnings = sum(1 for i in issues if i["level"] == "warning")
    return {
        "ok": errors == 0,
        "summary": {"provinces": len(provinces), "errors": errors, "warnings": warnings},
        "issues": issues,
    }


def _get_schema_report() -> dict[str, Any]:
    global _schema_report_cache
    if _schema_report_cache is None:
        _schema_report_cache = _validate_provinces_schema(_load_provinces())
    return _schema_report_cache


@router.get("/provinces")
async def get_provinces():
    return JSONResponse(_load_provinces())


@router.get("/schema-report")
async def get_schema_report():
    return JSONResponse(_get_schema_report())


@router.get("/company-profiles")
async def get_company_profiles():
    semi_companies = _load_semi_companies()
    ai_companies = _load_ai_company_profiles()

    def _sum_revenue(companies: list[dict[str, Any]]) -> float:
        return sum(float(c.get("revenue_b_cny") or 0) for c in companies if isinstance(c, dict))

    response = {
        "semi_companies": semi_companies,
        "ai_companies": ai_companies,
        "summary": {
            "semi_count": len(semi_companies),
            "ai_count": len(ai_companies),
            "total_count": len(semi_companies) + len(ai_companies),
            "semi_revenue_b_cny": _sum_revenue(semi_companies),
            "ai_revenue_b_cny": _sum_revenue(ai_companies),
            "total_revenue_b_cny": _sum_revenue(semi_companies) + _sum_revenue(ai_companies),
        },
    }
    return JSONResponse(response)


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
