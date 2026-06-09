from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .auth import (
    SESSION_COOKIE,
    create_session_cookie,
    create_user,
    generate_password,
    list_users,
    load_session_user,
    reset_user_password,
    set_user_active,
    authenticate_user,
)
from .config import load_settings
from .excel_importer import check_files, import_excel
from .file_store import copy_existing_pdf, resolve_raw_path, save_uploaded_pdf
from .indexer import inventory
from .search import add_contract, get_contract, get_file_record, list_purchase_methods, search_contracts, stats

PACKAGE_DIR = Path(__file__).resolve().parent

settings = load_settings()
app = FastAPI(title="Contract Info Query System")
business_app = FastAPI(title="Contract Info Query System Web")
business_app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
app.mount(settings.root_path, business_app)
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


def render_template(request: Request, name: str, context: dict[str, object], status_code: int = 200):
    context["current_user"] = getattr(request.state, "user", None)
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def cookie_path() -> str:
    current_settings = load_settings()
    return current_settings.root_path or "/"


def login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(str(request.url_for("login_page")), status_code=303)


def current_user(request: Request) -> dict[str, object]:
    settings = load_settings()
    user = load_session_user(settings, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    request.state.user = user
    return user


def current_admin(user: dict[str, object] = Depends(current_user)) -> dict[str, object]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    return user


@business_app.exception_handler(401)
def unauthorized(request: Request, exc: HTTPException):
    return login_redirect(request)


@business_app.exception_handler(403)
def forbidden(request: Request, exc: HTTPException):
    return render_template(request, "forbidden.html", {"detail": exc.detail}, status_code=403)


def health_payload() -> dict[str, object]:
    current_settings = load_settings()
    return {
        "status": "ok",
        "database_exists": current_settings.db_path.exists(),
        "raw_dir_exists": current_settings.raw_dir.exists(),
        "root_path": current_settings.root_path,
    }


@app.get("/health")
def root_health() -> dict[str, object]:
    return health_payload()


@business_app.get("/health")
def health() -> dict[str, object]:
    return health_payload()


@business_app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    settings = load_settings()
    user = load_session_user(settings, request.cookies.get(SESSION_COOKIE))
    if user is not None:
        request.state.user = user
        return RedirectResponse(str(request.url_for("home")), status_code=303)
    return render_template(request, "login.html", {"error": "", "username": ""})


@business_app.post("/login")
def login(request: Request, username: str = Form(default=""), password: str = Form(default="")):
    settings = load_settings()
    user = authenticate_user(settings.db_path, username, password)
    if user is None:
        return render_template(request, "login.html", {"error": "用户名或密码错误", "username": username.strip()}, status_code=400)
    response = RedirectResponse(str(request.url_for("home")), status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_cookie(settings, user),
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        path=cookie_path(),
    )
    return response


@business_app.post("/logout")
def logout(request: Request):
    response = RedirectResponse(str(request.url_for("login_page")), status_code=303)
    response.delete_cookie(SESSION_COOKIE, path=cookie_path())
    return response


@business_app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = Query(default="", max_length=100), user: dict[str, object] = Depends(current_user)):
    settings = load_settings()
    results = search_contracts(settings.db_path, q, limit=20) if settings.db_path.exists() else []
    recent = search_contracts(settings.db_path, "", limit=20) if settings.db_path.exists() else []
    return render_template(
        request,
        "index.html",
        {"q": q, "results": results, "recent": recent, "stats": stats(settings.db_path)},
    )


@business_app.get("/contracts")
def contracts(
    request: Request,
    q: str = Query(default="", max_length=100),
    year: str = Query(default="", max_length=4),
    supplier: str = Query(default="", max_length=100),
    purchase_method: str = Query(default="", max_length=100),
    min_amount: Optional[float] = Query(default=None),
    max_amount: Optional[float] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    format: str = Query(default="html"),
    user: dict[str, object] = Depends(current_user),
):
    settings = load_settings()
    results = search_contracts(settings.db_path, q, limit, year, supplier, purchase_method, min_amount, max_amount)
    if format == "json":
        return {"query": q, "count": len(results), "results": results}
    return render_template(
        request,
        "contracts_list.html",
        {
            "results": results,
            "q": q,
            "year": year,
            "supplier": supplier,
            "purchase_method": purchase_method,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "purchase_methods": list_purchase_methods(settings.db_path),
        },
    )


@business_app.get("/contracts/new", response_class=HTMLResponse)
def new_contract_form(request: Request, user: dict[str, object] = Depends(current_admin)):
    return render_template(request, "contract_form.html", {"error": "", "values": {}})


@business_app.post("/contracts")
async def create_contract(
    request: Request,
    serial_no: Optional[int] = Form(default=None),
    contract_no: str = Form(default=""),
    contract_name: str = Form(default=""),
    project_no: str = Form(default=""),
    project_name: str = Form(default=""),
    purchaser: str = Form(default=""),
    supplier: str = Form(default=""),
    item_name: str = Form(default=""),
    spec_or_service: str = Form(default=""),
    item_quantity: str = Form(default=""),
    unit_price_wan: Optional[float] = Form(default=None),
    amount_wan: Optional[float] = Form(default=None),
    purchase_method: str = Form(default=""),
    signed_date: str = Form(default=""),
    source_url: str = Form(default=""),
    excel_contract_file: str = Form(default=""),
    notes: str = Form(default=""),
    existing_pdf_path: str = Form(default=""),
    pdf: Optional[UploadFile] = File(default=None),
    user: dict[str, object] = Depends(current_admin),
):
    settings = load_settings()
    values = {
        "serial_no": serial_no,
        "contract_no": contract_no.strip(),
        "contract_name": contract_name.strip(),
        "project_no": project_no.strip(),
        "project_name": project_name.strip(),
        "purchaser": purchaser.strip(),
        "supplier": supplier.strip(),
        "item_name": item_name.strip(),
        "spec_or_service": spec_or_service.strip(),
        "item_quantity": item_quantity.strip(),
        "unit_price_wan": unit_price_wan,
        "amount_wan": amount_wan,
        "purchase_method": purchase_method.strip(),
        "signed_date": signed_date.strip(),
        "source_url": source_url.strip(),
        "excel_contract_file": excel_contract_file.strip(),
        "notes": notes.strip(),
    }
    try:
        file_record = await save_uploaded_pdf(settings, pdf)
        if file_record is None:
            file_record = copy_existing_pdf(settings, existing_pdf_path.strip())
        contract_id = add_contract(settings.db_path, values, file_record)
    except ValueError as exc:
        return render_template(request, "contract_form.html", {"error": str(exc), "values": values}, status_code=400)
    return RedirectResponse(str(request.url_for("contract_detail", contract_id=contract_id)), status_code=303)


@business_app.get("/contracts/{contract_id}")
def contract_detail(request: Request, contract_id: int, format: str = Query(default="html"), user: dict[str, object] = Depends(current_user)):
    settings = load_settings()
    result = get_contract(settings.db_path, contract_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    if format == "json":
        return result
    return render_template(request, "contract_detail.html", {"contract": result})


@business_app.get("/stats")
def stats_endpoint(user: dict[str, object] = Depends(current_user)) -> dict[str, object]:
    settings = load_settings()
    return stats(settings.db_path)


@business_app.get("/import", response_class=HTMLResponse)
def import_page(request: Request, user: dict[str, object] = Depends(current_admin)):
    settings = load_settings()
    return render_template(
        request,
        "import.html",
        {"settings": settings, "inventory": inventory(settings).to_dict(), "report": None},
    )


@business_app.post("/import/excel")
def import_excel_endpoint(request: Request, dry_run: bool = Form(default=False), user: dict[str, object] = Depends(current_admin)):
    settings = load_settings()
    report = import_excel(settings, dry_run=dry_run).to_dict()
    return render_template(
        request,
        "import.html",
        {"settings": settings, "inventory": inventory(settings).to_dict(), "report": report},
    )


@business_app.get("/users", response_class=HTMLResponse)
def users_page(request: Request, message: str = Query(default=""), user: dict[str, object] = Depends(current_admin)):
    settings = load_settings()
    return render_template(request, "users.html", {"users": list_users(settings.db_path), "message": message, "temporary_password": "", "error": ""})


@business_app.post("/users")
def create_viewer_user(
    request: Request,
    username: str = Form(default=""),
    display_name: str = Form(default=""),
    password: str = Form(default=""),
    user: dict[str, object] = Depends(current_admin),
):
    settings = load_settings()
    password = password.strip() or generate_password()
    try:
        create_user(settings.db_path, username, password, "viewer", display_name)
    except ValueError as exc:
        return render_template(request, "users.html", {"users": list_users(settings.db_path), "message": "", "temporary_password": "", "error": str(exc)}, status_code=400)
    return render_template(request, "users.html", {"users": list_users(settings.db_path), "message": f"已创建查询账号 {username.strip()}", "temporary_password": password, "error": ""})


@business_app.post("/users/{username}/reset-password")
def reset_viewer_password(request: Request, username: str, user: dict[str, object] = Depends(current_admin)):
    settings = load_settings()
    target = next((item for item in list_users(settings.db_path) if item["username"] == username), None)
    if target is None or target["role"] != "viewer":
        raise HTTPException(status_code=403, detail="只能在页面重置查询账号密码")
    password = reset_user_password(settings.db_path, username)
    return render_template(request, "users.html", {"users": list_users(settings.db_path), "message": f"已重置查询账号 {username}", "temporary_password": password, "error": ""})


@business_app.post("/users/{username}/toggle")
def toggle_viewer_user(request: Request, username: str, active: int = Form(default=1), user: dict[str, object] = Depends(current_admin)):
    settings = load_settings()
    target = next((item for item in list_users(settings.db_path) if item["username"] == username), None)
    if target is None or target["role"] != "viewer":
        raise HTTPException(status_code=403, detail="只能启用或禁用查询账号")
    set_user_active(settings.db_path, username, bool(active))
    return RedirectResponse(str(request.url_for("users_page")), status_code=303)


@business_app.get("/files/{file_id}/view")
def view_file(file_id: int, user: dict[str, object] = Depends(current_user)):
    return serve_file(file_id, inline=True)


@business_app.get("/files/{file_id}/download")
def download_file(file_id: int, user: dict[str, object] = Depends(current_user)):
    return serve_file(file_id, inline=False)


def serve_file(file_id: int, inline: bool):
    settings = load_settings()
    record = get_file_record(settings.db_path, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        path = resolve_raw_path(settings, str(record["relative_path"]))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="File path is invalid") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="File is missing under raw directory")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=str(record["original_filename"]),
        content_disposition_type="inline" if inline else "attachment",
    )


@business_app.get("/inventory")
def inventory_endpoint(user: dict[str, object] = Depends(current_admin)) -> dict[str, object]:
    settings = load_settings()
    summary = inventory(settings).to_dict()
    summary.pop("raw_dir", None)
    return summary


@business_app.get("/check-files")
def check_files_endpoint(user: dict[str, object] = Depends(current_admin)) -> dict[str, object]:
    settings = load_settings()
    return check_files(settings)
