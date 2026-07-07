#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股自选股智能分析系统 - 数据库同步工具 (SQLite ➡️ Neon PostgreSQL)

遵循开闭原则 (OCP)：作为一个独立的外部工具运行，不对原系统架构做任何破坏性修改。
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, select, text, Integer

# 将项目根目录添加到 sys.path，以便能够正确导入 src 模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from src.storage import Base
except ImportError as e:
    print(f"导入 src.storage 失败，请检查 PYTHONPATH 环境变量。错误信息: {e}")
    sys.exit(1)


def sync_database():
    sqlite_url = os.getenv("SQLITE_DATABASE_URL")
    pg_url = os.getenv("NEON_DATABASE_URL")

    if not sqlite_url:
        # 如果未指定，则默认使用项目的 sqlite 数据库路径
        sqlite_db_path = ROOT / "data" / "stock_analysis.db"
        sqlite_url = f"sqlite:///{sqlite_db_path.absolute()}"

    if not pg_url:
        print("❌ 错误: 未设置 NEON_DATABASE_URL 环境变量。跳过同步。")
        sys.exit(1)

    print(f"ℹ️ 源数据库 (SQLite): {sqlite_url}")
    print(f"ℹ️ 目标数据库 (PostgreSQL): {pg_url.split('@')[-1] if '@' in pg_url else pg_url}")  # 脱敏打印

    try:
        sqlite_engine = create_engine(sqlite_url)
        pg_engine = create_engine(pg_url)
    except Exception as e:
        print(f"❌ 错误: 无法创建 SQLAlchemy Engine 实例。{e}")
        sys.exit(1)

    # 1. 在 Neon (PostgreSQL) 上创建所有缺少的表结构
    print("🔄 正在初始化目标数据库表结构...")
    try:
        Base.metadata.create_all(pg_engine)
        print("✅ 目标数据库表结构初始化成功。")
    except Exception as e:
        print(f"❌ 错误: 初始化 Neon 数据库表结构失败。{e}")
        sys.exit(1)

    # 2. 依次同步每个表的数据，使用 sorted_tables 遵循外键依赖顺序
    print("🔄 开始同步表数据...")
    
    # 导入 PostgreSQL 专用的 insert 语句用于 upsert 操作
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    try:
        with sqlite_engine.connect() as sqlite_conn, pg_engine.connect() as pg_conn:
            for table in Base.metadata.sorted_tables:
                table_name = table.name
                print(f"\n⏳ 正在同步表: {table_name} ...")

                # 读取 SQLite 源表的所有记录
                try:
                    stmt_select = select(table)
                    rows = sqlite_conn.execute(stmt_select).mappings().all()
                except Exception as e:
                    print(f"⚠️ 警告: 读取 SQLite 数据失败，跳过表 {table_name}。{e}")
                    continue

                if not rows:
                    print(f"ℹ️ 表 {table_name} 在源数据库中为空，无需同步。")
                    continue

                total_rows = len(rows)
                print(f"📊 发现 {total_rows} 条记录，开始同步至 PostgreSQL...")

                # 批量同步，每次 500 条
                batch_size = 500
                success_count = 0

                for i in range(0, total_rows, batch_size):
                    batch = [dict(row) for row in rows[i:i + batch_size]]
                    
                    for row_dict in batch:
                        try:
                            # 获取主键列名
                            pk_cols = [c.name for c in table.primary_key.columns]
                            
                            if not pk_cols:
                                # 如果表无主键，则直接插入
                                pg_conn.execute(table.insert().values(row_dict))
                            else:
                                # 构造 PostgreSQL upsert 语句
                                insert_stmt = pg_insert(table).values(row_dict)
                                
                                # 构造冲突时需要更新的字段集（排除主键字段）
                                update_dict = {
                                    col.name: insert_stmt.excluded[col.name]
                                    for col in table.columns
                                    if col.name not in pk_cols
                                }
                                
                                if update_dict:
                                    # 如果有非主键字段，进行更新操作
                                    insert_stmt = insert_stmt.on_conflict_do_update(
                                        index_elements=pk_cols,
                                        set_=update_dict
                                    )
                                else:
                                    # 如果全部是主键，则冲突时忽略
                                    insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=pk_cols)
                                
                                pg_conn.execute(insert_stmt)
                            success_count += 1
                        except Exception as e:
                            print(f"⚠️ 警告: 同步单行记录失败 (表: {table_name})。错误: {e}")

                # 提交当前表的事务
                pg_conn.commit()
                print(f"✅ 表 {table_name} 同步完成：成功 {success_count}/{total_rows}")

                # 3. 自动更新 PostgreSQL 的 Serial 主键序列值，保证后置数据库自增序列的连续和可用
                for col in table.primary_key.columns:
                    if isinstance(col.type, Integer):
                        seq_query = f"SELECT setval(pg_get_serial_sequence('{table_name}', '{col.name}'), coalesce(max({col.name}), 1), max({col.name}) IS NOT NULL) FROM {table_name}"
                        try:
                            pg_conn.execute(text(seq_query))
                            pg_conn.commit()
                        except Exception:
                            # 如果对应的自增序列不存在（例如非 SERIAL 键），静默忽略
                            pass

        print("\n🎉 所有的数据库表同步任务执行完毕！")

    except Exception as e:
        print(f"\n❌ 数据同步异常中断: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sync_database()
