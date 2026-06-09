from __future__ import annotations

import argparse
import json

import uvicorn

from .api import app
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
