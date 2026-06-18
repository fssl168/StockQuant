# -*- coding: utf-8 -*-
"""启用 PostgreSQL pgvector 扩展"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get('DATABASE_URL', 'sqlite:///./stockquant.db')
# 转换为同步驱动
sync_url = db_url.replace('+asyncpg', '') if '+asyncpg' in db_url else db_url
host_info = sync_url.split('@')[-1] if '@' in sync_url else sync_url
print(f'Connecting to: {host_info}')

engine = create_engine(sync_url)
with engine.connect() as conn:
    result = conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    conn.commit()
    print('Vector extension enabled successfully!')

# 验证
with engine.connect() as conn:
    result = conn.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"))
    row = result.fetchone()
    if row:
        print(f'Vector extension version: {row[1]}')
    else:
        print('Vector extension not found')
