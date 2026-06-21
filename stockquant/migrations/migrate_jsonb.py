# -*- coding: utf-8 -*-
"""JSONB 字段迁移脚本

将 BacktestResult 的 JSON 字段从 Text 转换为 JSONB 类型。
"""

from __future__ import annotations

import logging
import sys
from stockquant.config import get_config

logger = logging.getLogger("stockquant.migrations")


def is_postgres(database_url: str) -> bool:
    return 'postgresql' in database_url.lower()


def migrate_to_jsonb():
    config = get_config()
    db_url = config.database.url
    
    if not is_postgres(db_url):
        logger.warning(f"当前数据库不是 PostgreSQL，跳过 JSONB 迁移: {db_url}")
        return False
    
    try:
        from stockquant.persistence.models import engine
        
        with engine.connect() as conn:
            # Check current column types
            result = conn.execute(__import__('sqlalchemy').text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'backtest_results' 
                AND column_name IN ('metrics', 'equity_curve', 'trades_summary')
            """))
            
            columns = {row[0]: row[1] for row in result}
            logger.info(f"Current column types: {columns}")
            
            # Migrate each column
            for col in ['metrics', 'equity_curve', 'trades_summary']:
                if columns.get(col) == 'text':
                    conn.execute(__import__('sqlalchemy').text(f"""
                        ALTER TABLE backtest_results 
                        ALTER COLUMN {col} TYPE JSONB USING {col}::jsonb
                    """))
                    logger.info(f"Migrated {col} to JSONB")
            
            conn.commit()
            logger.info("JSONB migration completed")
            return True
            
    except Exception as e:
        logger.error(f"JSONB migration failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    success = migrate_to_jsonb()
    sys.exit(0 if success else 1)
