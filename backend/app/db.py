import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import replace

from .catalog import PRODUCTS, Product


def _path() -> str:
    return os.environ.get("KIRANA_DB", "kirana.db")


@contextmanager
def conn():
    c = sqlite3.connect(_path())
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    stock REAL NOT NULL CHECK (stock >= 0),
    price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL UNIQUE,
    total REAL NOT NULL,
    transcript TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    qty REAL NOT NULL,
    unit TEXT NOT NULL,
    price REAL NOT NULL,
    amount REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    kind TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        for p in PRODUCTS:
            c.execute("INSERT OR IGNORE INTO products (id, stock, price) VALUES (?, ?, ?)",
                      (p.id, p.stock, p.price))


def reset_demo() -> None:
    """Dev only: clear orders and restore the seed stock."""
    with conn() as c:
        c.execute("DELETE FROM order_items")
        c.execute("DELETE FROM orders")
        for p in PRODUCTS:
            c.execute("UPDATE products SET stock = ?, price = ? WHERE id = ?",
                      (p.stock, p.price, p.id))


def get_products() -> dict[str, Product]:
    """Catalogue names/aliases from code, live stock and price from the database."""
    with conn() as c:
        rows = {r["id"]: r for r in c.execute("SELECT id, stock, price FROM products")}
    return {p.id: replace(p, stock=rows[p.id]["stock"], price=rows[p.id]["price"])
            for p in PRODUCTS if p.id in rows}


def log_event(session_id: str, kind: str, detail: object = None) -> None:
    with conn() as c:
        c.execute("INSERT INTO events (session_id, kind, detail) VALUES (?, ?, ?)",
                  (session_id, kind, json.dumps(detail, ensure_ascii=False, default=str)))


class StockError(Exception):
    pass


def commit_order(proposal_id: str, lines: list[dict], transcript: str) -> dict:
    """Atomic: either the whole order is saved and stock reduced, or nothing changes.
    Prices and stock are re-read from the database here, not trusted from the caller."""
    try:
        with conn() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute("SELECT id, total FROM orders WHERE proposal_id = ?",
                                 (proposal_id,)).fetchone()
            if existing:
                return {"status": "already_committed", "order_id": existing["id"],
                        "total": existing["total"]}
            if not lines:
                raise StockError("empty order")

            priced = []
            for l in lines:
                row = c.execute("SELECT stock, price FROM products WHERE id = ?",
                                (l["product_id"],)).fetchone()
                if row is None or l["qty"] <= 0:
                    raise StockError(f"invalid line {l.get('product_id')}")
                if l["qty"] > row["stock"]:
                    raise StockError(f"not enough stock for {l['product_id']}")
                priced.append((l, row["price"], round(l["qty"] * row["price"], 2)))

            total = round(sum(a for _, _, a in priced), 2)
            oid = c.execute("INSERT INTO orders (proposal_id, total, transcript) VALUES (?, ?, ?)",
                            (proposal_id, total, transcript)).lastrowid
            for l, price, amount in priced:
                cur = c.execute("UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                                (l["qty"], l["product_id"], l["qty"]))
                if cur.rowcount != 1:
                    raise StockError(f"not enough stock for {l['product_id']}")
                c.execute("INSERT INTO order_items (order_id, product_id, qty, unit, price, amount)"
                          " VALUES (?, ?, ?, ?, ?, ?)",
                          (oid, l["product_id"], l["qty"], l["unit"], price, amount))
            c.execute("INSERT INTO events (session_id, kind, detail) VALUES (?, 'commit', ?)",
                      (proposal_id, json.dumps({"order_id": oid, "total": total})))
            return {"status": "committed", "order_id": oid, "total": total}
    except StockError as e:
        return {"status": "rejected", "reason": str(e)}


def list_orders(limit: int = 20) -> list[dict]:
    with conn() as c:
        orders = c.execute("SELECT id, total, transcript, created_at FROM orders "
                           "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for o in orders:
            items = c.execute("SELECT product_id, qty, unit, price, amount FROM order_items "
                              "WHERE order_id = ?", (o["id"],)).fetchall()
            out.append({**dict(o), "items": [dict(i) for i in items]})
        return out
