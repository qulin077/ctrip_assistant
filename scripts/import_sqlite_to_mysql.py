import argparse
import sqlite3
from pathlib import Path

import pymysql


TYPE_MAP = {
    "INTEGER": "BIGINT",
    "TEXT": "TEXT",
    "TIMESTAMP": "TEXT",
}


def quote_name(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def mysql_type(sqlite_type: str) -> str:
    normalized = (sqlite_type or "TEXT").upper().strip()
    return TYPE_MAP.get(normalized, "TEXT")


def fetch_tables(sqlite_conn: sqlite3.Connection) -> list[str]:
    rows = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def create_mysql_table(mysql_cur, sqlite_conn: sqlite3.Connection, table: str) -> list[str]:
    columns_info = sqlite_conn.execute(f"PRAGMA table_info({quote_name(table)})").fetchall()
    columns = [row[1] for row in columns_info]
    column_defs = [
        f"{quote_name(row[1])} {mysql_type(row[2])} NULL"
        for row in columns_info
    ]
    mysql_cur.execute(f"DROP TABLE IF EXISTS {quote_name(table)}")
    mysql_cur.execute(
        f"CREATE TABLE {quote_name(table)} ({', '.join(column_defs)}) "
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    )
    return columns


def import_table(
    sqlite_conn: sqlite3.Connection,
    mysql_conn,
    table: str,
    batch_size: int,
) -> int:
    with mysql_conn.cursor() as mysql_cur:
        columns = create_mysql_table(mysql_cur, sqlite_conn, table)
        mysql_conn.commit()

        column_sql = ", ".join(quote_name(col) for col in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_sql = f"INSERT INTO {quote_name(table)} ({column_sql}) VALUES ({placeholders})"

        sqlite_cur = sqlite_conn.execute(f"SELECT {column_sql} FROM {quote_name(table)}")
        total = 0
        while True:
            rows = sqlite_cur.fetchmany(batch_size)
            if not rows:
                break
            mysql_cur.executemany(insert_sql, rows)
            total += len(rows)
            mysql_conn.commit()
        return total


def import_database(sqlite_path: Path, mysql_db: str, args) -> None:
    print(f"Importing {sqlite_path.name} -> {mysql_db}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    mysql_conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        charset="utf8mb4",
        autocommit=False,
        local_infile=False,
    )
    try:
        with mysql_conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS {quote_name(mysql_db)} "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(f"USE {quote_name(mysql_db)}")
        mysql_conn.commit()

        for table in fetch_tables(sqlite_conn):
            count = import_table(sqlite_conn, mysql_conn, table, args.batch_size)
            print(f"  {table}: {count}")
    finally:
        sqlite_conn.close()
        mysql_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    imports = [
        (args.project_root / "travel_new.sqlite", "ctrip_travel_new"),
        (args.project_root / "travel2.sqlite", "ctrip_travel_backup"),
    ]

    for sqlite_path, mysql_db in imports:
        if not sqlite_path.exists():
            raise FileNotFoundError(sqlite_path)
        import_database(sqlite_path, mysql_db, args)


if __name__ == "__main__":
    main()
