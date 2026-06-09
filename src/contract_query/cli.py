from __future__ import annotations

import argparse
import json

import uvicorn

from .api import app
from .auth import ensure_admin_user, ensure_viewer_user, list_users, reset_user_password
from .config import load_settings
from .db import initialize_database
from .excel_importer import check_files, import_excel
from .indexer import inventory
from .search import search_contracts


def print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_inventory(args: argparse.Namespace) -> int:
    settings = load_settings()
    print_json(inventory(settings).to_dict())
    return 0


def run_import_excel(args: argparse.Namespace) -> int:
    settings = load_settings()
    print_json(import_excel(settings, dry_run=args.dry_run).to_dict())
    return 0


def run_build_index(args: argparse.Namespace) -> int:
    settings = load_settings()
    initialize_database(settings.db_path)
    print_json({"db_path": str(settings.db_path), "status": "ready"})
    return 0


def run_search(args: argparse.Namespace) -> int:
    settings = load_settings()
    print_json({"query": args.query, "results": search_contracts(settings.db_path, args.query, limit=args.limit)})
    return 0


def run_check_files(args: argparse.Namespace) -> int:
    settings = load_settings()
    print_json(check_files(settings))
    return 0


def run_serve(args: argparse.Namespace) -> int:
    settings = load_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    uvicorn.run(app, host=host, port=port)
    return 0


def run_admin_init(args: argparse.Namespace) -> int:
    settings = load_settings()
    initialize_database(settings.db_path)
    admin_password = ensure_admin_user(settings.db_path)
    viewer_password = ensure_viewer_user(settings.db_path) if args.create_viewer else None
    payload: dict[str, object] = {"status": "ready", "admin_created": admin_password is not None}
    if admin_password:
        payload["admin_username"] = "admin"
        payload["admin_temporary_password"] = admin_password
    if viewer_password:
        payload["viewer_username"] = "query"
        payload["viewer_temporary_password"] = viewer_password
    print_json(payload)
    return 0


def run_admin_reset_password(args: argparse.Namespace) -> int:
    settings = load_settings()
    initialize_database(settings.db_path)
    password = reset_user_password(settings.db_path, args.username)
    print_json({"username": args.username, "temporary_password": password})
    return 0


def run_admin_list_users(args: argparse.Namespace) -> int:
    settings = load_settings()
    print_json({"users": list_users(settings.db_path)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contract-query", description="Contract information query system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory", help="Summarize source files under data/raw")
    inventory_parser.set_defaults(func=run_inventory)

    import_parser = subparsers.add_parser("import-excel", help="Import Excel contracts and map PDF files")
    import_parser.add_argument("--dry-run", action="store_true", help="Scan and report without writing database")
    import_parser.set_defaults(func=run_import_excel)

    build_index_parser = subparsers.add_parser("build-index", help="Initialize the SQLite contract database")
    build_index_parser.set_defaults(func=run_build_index)

    search_parser = subparsers.add_parser("search", help="Search contract metadata")
    search_parser.add_argument("query", help="Keyword to search in contract metadata")
    search_parser.add_argument("--limit", type=int, default=20, help="Maximum results to return")
    search_parser.set_defaults(func=run_search)

    check_files_parser = subparsers.add_parser("check-files", help="Check database file references under raw dir")
    check_files_parser.set_defaults(func=run_check_files)

    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI service")
    serve_parser.add_argument("--host", default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.set_defaults(func=run_serve)

    admin_parser = subparsers.add_parser("admin", help="Manage local web users")
    admin_subparsers = admin_parser.add_subparsers(dest="admin_command", required=True)

    admin_init_parser = admin_subparsers.add_parser("init", help="Create the initial admin account if missing")
    admin_init_parser.add_argument("--create-viewer", action="store_true", help="Also create a public query viewer account if missing")
    admin_init_parser.set_defaults(func=run_admin_init)

    admin_reset_parser = admin_subparsers.add_parser("reset-password", help="Reset a user's password and print a temporary password")
    admin_reset_parser.add_argument("--username", required=True, help="Username to reset")
    admin_reset_parser.set_defaults(func=run_admin_reset_password)

    admin_list_parser = admin_subparsers.add_parser("list-users", help="List local web users without password hashes")
    admin_list_parser.set_defaults(func=run_admin_list_users)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
