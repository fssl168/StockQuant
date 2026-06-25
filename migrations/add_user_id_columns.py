#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration: Add user_id VARCHAR(50) to tables that are missing it.
Run this after starting PostgreSQL.

Usage: python add_user_id_columns.py
"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import psycopg2

def get_db_config():
    """Read DB config from .env or use defaults."""
    from dotenv import load_dotenv
    load_dotenv()
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "dbname": os.getenv("DB_NAME", "stockquant"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }

TABLES = [
    "backtest_tasks", "strategies", "collect_tasks", "optimize_tasks",
    "comparison_history", "pending_orders", "orders_audit",
]

def main():
    cfg = get_db_config()
    print(f"Connecting to PostgreSQL at {cfg['host']}:{cfg['port']}/{cfg['dbname']}...")
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    cur = conn.cursor()

    for t in TABLES:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (t, "user_id"),
        )
        if cur.fetchone():
            print(f"  {t}: user_id already exists, skipping")
        else:
            cur.execute("ALTER TABLE %s ADD COLUMN user_id VARCHAR(50)" % t)
            idx = "ix_%s_user_id" % t
            cur.execute("CREATE INDEX %s ON %s(user_id)" % (idx, t))
            print(f"  {t}: added user_id + index")

    cur.close()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    main()
