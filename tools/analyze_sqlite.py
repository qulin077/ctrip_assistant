import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "travel_new.sqlite"
DEFAULT_FAQ = PROJECT_ROOT / "order_faq.md"
DEFAULT_OUT = PROJECT_ROOT / "analysis"

KEY_TABLES = [
    "flights",
    "tickets",
    "ticket_flights",
    "boarding_passes",
    "bookings",
    "hotels",
    "car_rentals",
    "trip_recommendations",
    "airports_data",
    "aircrafts_data",
    "seats",
]


def fetch_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def table_schema(conn: sqlite3.Connection, table: str) -> list[dict]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in rows
    ]


def table_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row[0] if row else ""


def row_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def sample_rows(conn: sqlite3.Connection, table: str, limit: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f'SELECT * FROM "{table}" LIMIT ?', (limit,)).fetchall()
    return [dict(row) for row in rows]


def distinct_count(conn: sqlite3.Connection, table: str, column: str) -> int:
    return conn.execute(f'SELECT COUNT(DISTINCT "{column}") FROM "{table}"').fetchone()[0]


def null_count(conn: sqlite3.Connection, table: str, column: str) -> int:
    return conn.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NULL OR "{column}" = "\\N"'
    ).fetchone()[0]


def column_profiles(conn: sqlite3.Connection, table: str, columns: list[str]) -> dict:
    profiles = {}
    for column in columns:
        profiles[column] = {
            "distinct": distinct_count(conn, table, column),
            "null_or_N": null_count(conn, table, column),
        }
    return profiles


def parse_faq(faq_path: Path) -> list[dict]:
    text = faq_path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    sections = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        sections.append(
            {
                "title": match.group(1).strip(),
                "start_line": text[: match.start()].count("\n") + 1,
                "char_count": len(content),
                "question_like_count": len(re.findall(r"(^|\n)\s*\d+\.", content)),
                "content_preview": content[:300].replace("\n", " "),
            }
        )
    return sections


def write_csv_exports(conn: sqlite3.Connection, tables: list[str], export_dir: Path) -> dict:
    export_dir.mkdir(parents=True, exist_ok=True)
    exported = {}
    old_row_factory = conn.row_factory
    conn.row_factory = None
    try:
        for table in tables:
            path = export_dir / f"{table}.csv"
            cur = conn.execute(f'SELECT * FROM "{table}"')
            columns = [desc[0] for desc in cur.description]
            count = 0
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                while True:
                    rows = cur.fetchmany(10000)
                    if not rows:
                        break
                    writer.writerows(rows)
                    count += len(rows)
            exported[table] = {"path": str(path.relative_to(PROJECT_ROOT)), "rows": count}
    finally:
        conn.row_factory = old_row_factory
    return exported


def write_samples(conn: sqlite3.Connection, tables: list[str], export_dir: Path, limit: int) -> dict:
    export_dir.mkdir(parents=True, exist_ok=True)
    exported = {}
    old_row_factory = conn.row_factory
    conn.row_factory = None
    try:
        for table in tables:
            path = export_dir / f"{table}_sample.csv"
            cur = conn.execute(f'SELECT * FROM "{table}" LIMIT ?', (limit,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)
            exported[table] = {"path": str(path.relative_to(PROJECT_ROOT)), "rows": len(rows)}
    finally:
        conn.row_factory = old_row_factory
    return exported


def generate_raw_inventory(inventory: dict, path: Path) -> None:
    lines = [
        "# Raw Data Inventory",
        "",
        f"- SQLite database: `{inventory['database']}`",
        f"- FAQ document: `{inventory['faq_path']}`",
        "",
        "## Tables",
        "",
        "| Table | Rows | Columns |",
        "| --- | ---: | --- |",
    ]
    for table, meta in inventory["tables"].items():
        columns = ", ".join(col["name"] for col in meta["schema"])
        lines.append(f"| `{table}` | {meta['row_count']} | {columns} |")
    lines.extend(["", "## FAQ Sections", "", "| Section | Start line | Chars | Numbered items |", "| --- | ---: | ---: | ---: |"])
    for section in inventory["faq_sections"]:
        lines.append(
            f"| {section['title']} | {section['start_line']} | {section['char_count']} | {section['question_like_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--faq", type=Path, default=DEFAULT_FAQ)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--export-full-csv", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        raise FileNotFoundError(args.db)
    if not args.faq.exists():
        raise FileNotFoundError(args.faq)

    args.out.mkdir(parents=True, exist_ok=True)
    export_dir = args.out / "exports"
    samples_dir = export_dir / "samples"
    full_csv_dir = export_dir / "travel_new_csv"

    conn = sqlite3.connect(args.db)
    try:
        tables = fetch_tables(conn)
        inventory = {
            "database": str(args.db.relative_to(PROJECT_ROOT)),
            "faq_path": str(args.faq.relative_to(PROJECT_ROOT)),
            "tables": {},
            "faq_sections": parse_faq(args.faq),
            "exports": {},
        }
        for table in tables:
            schema = table_schema(conn, table)
            columns = [col["name"] for col in schema]
            inventory["tables"][table] = {
                "sql": table_sql(conn, table),
                "schema": schema,
                "row_count": row_count(conn, table),
                "sample_rows": sample_rows(conn, table, args.sample_limit),
                "column_profiles": column_profiles(conn, table, columns),
            }

        inventory["exports"]["samples"] = write_samples(conn, tables, samples_dir, args.sample_limit)
        if args.export_full_csv:
            inventory["exports"]["full_csv"] = write_csv_exports(conn, tables, full_csv_dir)

        (args.out / "raw_inventory.json").write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        generate_raw_inventory(inventory, args.out / "raw_inventory.md")
    finally:
        conn.close()

    print(f"Wrote {args.out / 'raw_inventory.json'}")
    print(f"Wrote {args.out / 'raw_inventory.md'}")
    print(f"Wrote samples to {samples_dir}")
    if args.export_full_csv:
        print(f"Wrote full CSV exports to {full_csv_dir}")


if __name__ == "__main__":
    main()
