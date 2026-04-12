#!/usr/bin/env python3
"""
pgbackup.py — Database Backup + Safe Migration Runner
by pgwiz

Usage:
        python pgbackup.py backup              # Backup current DB (compressed .sql.gz by default)
        python pgbackup.py backup --label x    # Backup with label in filename
    python pgbackup.py restore <file>      # Restore from a backup file
    python pgbackup.py migrate             # Backup first, then run migrations
    python pgbackup.py list                # List available backups

Reads DB config from Django's settings (via DJANGO_SETTINGS_MODULE)
or from a .env file / env vars.

Supported engines:
    - PostgreSQL (pg_dump / psql)
    - MySQL/MariaDB (mysqldump / mysql)
"""

import os
import sys
import subprocess
import datetime
import gzip
import shutil
import argparse
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# You can override these via environment variables or a .env file.
# ──────────────────────────────────────────────────────────────────────────────

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./db_backups"))
SCHEMA = os.getenv("BACKUP_SCHEMA", "public")
COMPRESS = os.getenv("BACKUP_COMPRESS", "true").lower() == "true"
KEEP_LAST = int(os.getenv("BACKUP_KEEP_LAST", "10"))


def normalize_engine(engine_raw: str) -> str:
    e = (engine_raw or "").strip().lower()

    if e in ("postgres", "postgresql", "psql"):
        return "postgresql"
    if e in ("mysql", "mariadb"):
        return "mysql"
    if e in ("sqlite", "sqlite3"):
        return "sqlite3"

    if e.startswith("django.db.backends.postgresql") or e.startswith("django.contrib.gis.db.backends.postgis"):
        return "postgresql"
    if e.startswith("django.db.backends.mysql"):
        return "mysql"
    if e.startswith("django.db.backends.sqlite3"):
        return "sqlite3"

    return "unknown"


def default_port(engine: str) -> str:
    if engine == "postgresql":
        return "5432"
    if engine == "mysql":
        return "3306"
    return ""


def default_host(engine: str) -> str:
    if engine in ("postgresql", "mysql"):
        return "127.0.0.1"
    return ""


def default_user(engine: str) -> str:
    if engine == "postgresql":
        return "postgres"
    if engine == "mysql":
        return "root"
    return ""


def load_env_file(path: str = ".env"):
    """Parse a simple .env file into os.environ (only if key not already set)."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_db_config() -> dict:
    """
    Resolve DB credentials in priority order:
      1. Django settings (DJANGO_SETTINGS_MODULE must be set)
      2. DATABASE_URL env var
      3. Individual DB_* env vars
      4. Fallback defaults
    """
    # Try Django settings first
    dsm = os.getenv("DJANGO_SETTINGS_MODULE")
    if dsm:
        try:
            import django
            django.setup()
            from django.conf import settings
            db = settings.DATABASES.get("default", {})
            engine_raw = str(db.get("ENGINE", os.getenv("DB_ENGINE", "")))
            engine = normalize_engine(engine_raw)
            return {
                "engine_raw": engine_raw,
                "engine": engine,
                "host": str(db.get("HOST") or default_host(engine)),
                "port": str(db.get("PORT") or default_port(engine)),
                "name": str(db.get("NAME", "")),
                "user": str(db.get("USER") or default_user(engine)),
                "password": str(db.get("PASSWORD", "")),
            }
        except Exception as e:
            print(f"[warn] Could not load Django settings: {e}")

    # Try DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            u = urlparse(db_url)
            scheme = (u.scheme or "").split("+", 1)[0]
            engine = normalize_engine(scheme)
            return {
                "engine_raw": scheme,
                "engine": engine,
                "host": u.hostname or default_host(engine),
                "port": str(u.port or default_port(engine)),
                "name": u.path.lstrip("/"),
                "user": u.username or default_user(engine),
                "password": u.password or "",
            }
        except Exception as e:
            print(f"[warn] Could not parse DATABASE_URL: {e}")

    # Fallback to individual env vars
    engine_raw = os.getenv("DB_ENGINE", "django.db.backends.postgresql")
    engine = normalize_engine(engine_raw)
    return {
        "engine_raw": engine_raw,
        "engine": engine,
        "host": os.getenv("DB_HOST", default_host(engine)),
        "port": os.getenv("DB_PORT", default_port(engine)),
        "name": os.getenv("DB_NAME", ""),
        "user": os.getenv("DB_USER", default_user(engine)),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def build_env(cfg: dict) -> dict:
    """Build subprocess environment for DB tools."""
    env = os.environ.copy()
    if cfg["engine"] == "postgresql" and cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]
    if cfg["engine"] == "mysql" and cfg["password"]:
        env["MYSQL_PWD"] = cfg["password"]
    return env


def ensure_backup_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve_tool(name: str, fail_hard: bool = True) -> str:
    """Find DB client tools from PATH, env overrides, and common install locations."""
    from_path = shutil.which(name)
    if from_path:
        return from_path

    mysql_bin = os.getenv("MYSQL_BIN", "").strip()
    postgres_bin = os.getenv("POSTGRES_BIN", "").strip()

    env_candidates = {
        "mysqldump": [
            os.getenv("MYSQLDUMP_PATH", "").strip(),
            str(Path(mysql_bin) / "mysqldump.exe") if mysql_bin else "",
            str(Path(mysql_bin) / "mysqldump") if mysql_bin else "",
        ],
        "mysql": [
            os.getenv("MYSQL_PATH", "").strip(),
            str(Path(mysql_bin) / "mysql.exe") if mysql_bin else "",
            str(Path(mysql_bin) / "mysql") if mysql_bin else "",
        ],
        "pg_dump": [
            os.getenv("PG_DUMP_PATH", "").strip(),
            str(Path(postgres_bin) / "pg_dump.exe") if postgres_bin else "",
            str(Path(postgres_bin) / "pg_dump") if postgres_bin else "",
        ],
        "psql": [
            os.getenv("PSQL_PATH", "").strip(),
            str(Path(postgres_bin) / "psql.exe") if postgres_bin else "",
            str(Path(postgres_bin) / "psql") if postgres_bin else "",
        ],
    }

    common_candidates = {
        "mysqldump": [
            r"C:\xampp\mysql\bin\mysqldump.exe",
            r"C:\xampplite\mysql\bin\mysqldump.exe",
            r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        ],
        "mysql": [
            r"C:\xampp\mysql\bin\mysql.exe",
            r"C:\xampplite\mysql\bin\mysql.exe",
            r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        ],
        "pg_dump": [
            r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\13\bin\pg_dump.exe",
            r"C:\Program Files\PostgreSQL\12\bin\pg_dump.exe",
        ],
        "psql": [
            r"C:\Program Files\PostgreSQL\17\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\16\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\14\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\13\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\12\bin\psql.exe",
        ],
    }

    for candidate in env_candidates.get(name, []) + common_candidates.get(name, []):
        if candidate and Path(candidate).exists():
            return str(Path(candidate))

    if fail_hard:
        print(f"[error] '{name}' not found in PATH.")
        print("        Set PATH or configure *_PATH / MYSQL_BIN / POSTGRES_BIN in .env")
        sys.exit(1)

    return ""


def resolve_first_tool(names: list[str]) -> str:
    for name in names:
        found = resolve_tool(name, fail_hard=False)
        if found:
            return found

    print(f"[error] None of these tools were found: {', '.join(names)}")
    print("        Set PATH or configure *_PATH / MYSQL_BIN / POSTGRES_BIN in .env")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# BACKUP
# ──────────────────────────────────────────────────────────────────────────────

def build_backup_filename(cfg: dict, label: str = "") -> str:
    suffix = f"_{label}" if label else ""

    if cfg["engine"] == "postgresql":
        return f"{cfg['name']}_{SCHEMA}{suffix}_{timestamp()}.sql"
    if cfg["engine"] == "mysql":
        return f"{cfg['name']}_mysql{suffix}_{timestamp()}.sql"
    if cfg["engine"] == "sqlite3":
        db_name = Path(cfg["name"]).stem or "sqlite"
        return f"{db_name}_sqlite{suffix}_{timestamp()}.sql"

    return f"{cfg['name']}_backup{suffix}_{timestamp()}.sql"


def do_backup_postgresql(cfg: dict, out_path: Path):
    pg_dump_bin = resolve_tool("pg_dump")
    cmd = [
        pg_dump_bin,
        "-h", cfg["host"],
        "-p", cfg["port"],
        "-U", cfg["user"],
        "-d", cfg["name"],
        "--no-owner",
        "--no-acl",
        "--clean",
        "--if-exists",
        "-f", str(out_path),
    ]

    if SCHEMA:
        cmd.extend(["--schema", SCHEMA])

    print(f"[backup] Dumping PostgreSQL '{cfg['name']}' schema '{SCHEMA}' -> {out_path}")
    result = subprocess.run(cmd, env=build_env(cfg))
    if result.returncode != 0:
        print("[backup] pg_dump failed.")
        sys.exit(1)


def do_backup_mysql(cfg: dict, out_path: Path):
    mysqldump_bin = resolve_first_tool(["mysqldump", "mariadb-dump"])
    cmd = [
        mysqldump_bin,
        "-h", cfg["host"],
        "-P", cfg["port"],
        "-u", cfg["user"],
        "--single-transaction",
        "--skip-lock-tables",
        "--routines",
        "--triggers",
        "--events",
        "--add-drop-table",
        "--default-character-set=utf8mb4",
        cfg["name"],
        "-r", str(out_path),
    ]

    print(f"[backup] Dumping MySQL '{cfg['name']}' -> {out_path}")
    result = subprocess.run(cmd, env=build_env(cfg))
    if result.returncode != 0:
        print("[backup] mysqldump failed.")
        sys.exit(1)


def do_backup_sqlite(cfg: dict, out_path: Path):
    db_path = Path(cfg["name"])
    if not db_path.exists():
        print(f"[backup] sqlite file not found: {db_path}")
        sys.exit(1)

    print(f"[backup] Copying SQLite DB '{db_path}' -> {out_path}")
    shutil.copyfile(db_path, out_path)


def maybe_compress(path: Path) -> Path:
    if not COMPRESS:
        return path

    gz_path = Path(str(path) + ".gz")
    print(f"[backup] Compressing -> {gz_path}")
    with open(path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    path.unlink()
    return gz_path


def do_backup(cfg: dict, label: str = "") -> Path:
    ensure_backup_dir()

    base_name = build_backup_filename(cfg, label=label)
    out_path = BACKUP_DIR / base_name

    if cfg["engine"] == "postgresql":
        do_backup_postgresql(cfg, out_path)
    elif cfg["engine"] == "mysql":
        do_backup_mysql(cfg, out_path)
    elif cfg["engine"] == "sqlite3":
        do_backup_sqlite(cfg, out_path)
    else:
        print(f"[backup] Unsupported engine: {cfg.get('engine_raw') or cfg['engine']}")
        sys.exit(1)

    out_path = maybe_compress(out_path)

    print(f"[backup] ✓ Saved: {out_path}  ({out_path.stat().st_size // 1024} KB)")
    rotate_backups()
    return out_path


def rotate_backups():
    """Keep only the N most recent backups."""
    if KEEP_LAST <= 0:
        return
    files = sorted(BACKUP_DIR.glob("*.sql*"), key=lambda f: f.stat().st_mtime, reverse=True)
    for old in files[KEEP_LAST:]:
        print(f"[rotate] Removing old backup: {old.name}")
        old.unlink()


# ──────────────────────────────────────────────────────────────────────────────
# RESTORE
# ──────────────────────────────────────────────────────────────────────────────

def prepare_sql_file(path: Path) -> tuple[Path, Optional[Path]]:
    sql_path = path
    tmp_file: Optional[Path] = None

    if path.suffix == ".gz":
        ensure_backup_dir()
        tmp_file = BACKUP_DIR / path.stem
        print(f"[restore] Decompressing -> {tmp_file}")
        with gzip.open(path, "rb") as f_in, open(tmp_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        sql_path = tmp_file

    return sql_path, tmp_file


def do_restore_postgresql(cfg: dict, sql_path: Path):
    psql_bin = resolve_tool("psql")
    cmd = [
        psql_bin,
        "-h", cfg["host"],
        "-p", cfg["port"],
        "-U", cfg["user"],
        "-d", cfg["name"],
        "-f", str(sql_path),
        "-v", "ON_ERROR_STOP=1",
    ]
    print(f"[restore] Restoring PostgreSQL from {sql_path} ...")
    result = subprocess.run(cmd, env=build_env(cfg))
    if result.returncode != 0:
        print("[restore] Restore failed.")
        sys.exit(1)


def do_restore_mysql(cfg: dict, sql_path: Path):
    mysql_bin = resolve_first_tool(["mysql", "mariadb"])
    cmd = [
        mysql_bin,
        "-h", cfg["host"],
        "-P", cfg["port"],
        "-u", cfg["user"],
        cfg["name"],
    ]
    print(f"[restore] Restoring MySQL from {sql_path} ...")
    with open(sql_path, "rb") as f_in:
        result = subprocess.run(cmd, stdin=f_in, env=build_env(cfg))
    if result.returncode != 0:
        print("[restore] Restore failed.")
        sys.exit(1)


def do_restore_sqlite(cfg: dict, sql_path: Path):
    db_path = Path(cfg["name"])
    if not sql_path.exists():
        print(f"[restore] Backup file not found: {sql_path}")
        sys.exit(1)
    print(f"[restore] Replacing SQLite DB file {db_path} from {sql_path}")
    shutil.copyfile(sql_path, db_path)


def do_restore(cfg: dict, backup_file: str):
    path = Path(backup_file)
    if not path.exists():
        print(f"[error] File not found: {path}")
        sys.exit(1)

    warning_scope = f"database '{cfg['name']}'"
    if cfg["engine"] == "postgresql" and SCHEMA:
        warning_scope = f"database '{cfg['name']}' (schema: {SCHEMA})"
    print(f"[restore] ⚠  This will overwrite data in {warning_scope}.")
    confirm = input("  Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("[restore] Aborted.")
        return

    sql_path, tmp_file = prepare_sql_file(path)

    try:
        if cfg["engine"] == "postgresql":
            do_restore_postgresql(cfg, sql_path)
        elif cfg["engine"] == "mysql":
            do_restore_mysql(cfg, sql_path)
        elif cfg["engine"] == "sqlite3":
            do_restore_sqlite(cfg, sql_path)
        else:
            print(f"[restore] Unsupported engine: {cfg.get('engine_raw') or cfg['engine']}")
            sys.exit(1)
    finally:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()

    print("[restore] ✓ Restore complete.")


# ──────────────────────────────────────────────────────────────────────────────
# MIGRATE (backup → then migrate)
# ──────────────────────────────────────────────────────────────────────────────

def do_migrate(cfg: dict):
    print("[migrate] Step 1/2 — Creating pre-migration backup ...")
    backup_path = do_backup(cfg, label="pre_migrate")
    print(f"[migrate] Backup saved: {backup_path}")

    print("\n[migrate] Step 2/2 — Running Django migrations ...")

    # Detect manage.py location
    manage = Path("manage.py")
    if not manage.exists():
        # walk up to find it
        for parent in Path.cwd().parents:
            candidate = parent / "manage.py"
            if candidate.exists():
                manage = candidate
                break
        else:
            print("[migrate] ✗ Could not find manage.py. Run from your Django project root.")
            sys.exit(1)

    cmd = [sys.executable, str(manage), "migrate", "--noinput"]
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\n[migrate] ✗ Migrations failed.")
        print(f"[migrate] Your pre-migration backup is at: {backup_path}")
        print(f"[migrate] Restore with:  python pgbackup.py restore {backup_path}")
        sys.exit(1)

    print("\n[migrate] ✓ Migrations applied successfully.")
    print(f"[migrate] Pre-migration backup retained at: {backup_path}")


# ──────────────────────────────────────────────────────────────────────────────
# LIST
# ──────────────────────────────────────────────────────────────────────────────

def do_list():
    ensure_backup_dir()
    files = sorted(BACKUP_DIR.glob("*.sql*"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print(f"[list] No backups found in {BACKUP_DIR}")
        return
    print(f"[list] Backups in {BACKUP_DIR}:\n")
    for i, f in enumerate(files, 1):
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = f.stat().st_size // 1024
        print(f"  {i:>3}.  {f.name:<60}  {size_kb:>6} KB   {mtime}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def main():
    load_env_file()

    parser = argparse.ArgumentParser(
                description="Database Backup + Safe Migration Runner (PostgreSQL/MySQL)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pgbackup.py backup
    python pgbackup.py backup --label before-feature-x
  python pgbackup.py restore db_backups/mydb_public_20250101_120000.sql.gz
  python pgbackup.py migrate
  python pgbackup.py list

Environment variables (or .env file):
  DJANGO_SETTINGS_MODULE   e.g. myproject.settings.staging
    DATABASE_URL             e.g. postgresql://user:pass@host/dbname
                                                     or mysql://user:pass@host/dbname
    DB_ENGINE                e.g. django.db.backends.postgresql or django.db.backends.mysql
    DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
  BACKUP_DIR               default: ./db_backups
    BACKUP_SCHEMA            default: public (PostgreSQL only)
  BACKUP_COMPRESS          true/false  (default: true)
  BACKUP_KEEP_LAST         number of backups to retain (default: 10, 0=all)
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # backup
    p_backup = sub.add_parser("backup", help="Dump the configured DB to a file")
    p_backup.add_argument("--label", default="", help="Optional label appended to filename")

    # restore
    p_restore = sub.add_parser("restore", help="Restore from a backup file")
    p_restore.add_argument("file", help="Path to .sql or .sql.gz backup file")

    # migrate
    sub.add_parser("migrate", help="Backup then run Django migrations")

    # list
    sub.add_parser("list", help="List available backups")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "list":
        do_list()
        return

    cfg = get_db_config()

    if not cfg["name"]:
        print("[error] No database name found. Set DJANGO_SETTINGS_MODULE, DATABASE_URL, or DB_NAME.")
        sys.exit(1)

    if cfg["engine"] == "unknown":
        print(f"[error] Unsupported DB engine: {cfg.get('engine_raw') or '(empty)'}")
        print("        Supported: django.db.backends.postgresql, django.db.backends.mysql")
        sys.exit(1)

    schema_text = f"  schema={SCHEMA}" if cfg["engine"] == "postgresql" else ""
    print(f"[config] Engine={cfg['engine']}  DB={cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['name']}{schema_text}\n")

    if args.command == "backup":
        do_backup(cfg, label=getattr(args, "label", ""))
    elif args.command == "restore":
        do_restore(cfg, args.file)
    elif args.command == "migrate":
        do_migrate(cfg)


if __name__ == "__main__":
    main()
