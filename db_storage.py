# -*- coding: utf-8 -*-
"""云端持久化存储层（供 Render 等临时文件系统平台使用）。

Render 免费版文件系统是临时的：服务休眠重启或重新部署后，
运行期写盘的 data/config.json 会被清空，导致后台修改丢失。

设置环境变量 DATABASE_URL（Neon 等 PostgreSQL 连接串）后，
配置、备份、登录日志改存数据库，重启 / 重新部署后仍然保留。
未设置 DATABASE_URL 时本模块不会被启用，本地继续用 data/ 文件。

表结构：
  app_config      单行存放完整 config JSON（对应本地 data/config.json）
  config_backups  修改前快照，保留最近 N 份（对应本地 data/backup/）
  auth_log        登录日志（对应本地 data/auth.log）
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_KEEP_BACKUPS = 20

_schema_lock = threading.Lock()
_schema_ready = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_config (
    id          INTEGER PRIMARY KEY,
    data        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config_backups (
    name  TEXT PRIMARY KEY,
    data  TEXT NOT NULL,
    size  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_log (
    id      BIGSERIAL PRIMARY KEY,
    ts      TEXT NOT NULL,
    ip      TEXT NOT NULL DEFAULT '',
    success BOOLEAN NOT NULL,
    reason  TEXT NOT NULL DEFAULT ''
);
"""


class DbStorageError(OSError):
    """数据库读写失败。继承 OSError，使 app.py 现有的 except OSError 兜底生效。"""


def enabled() -> bool:
    """是否启用了数据库模式（由环境变量 DATABASE_URL 决定）。"""
    return bool(os.environ.get("DATABASE_URL", "").strip())


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _connect():
    # 惰性导入：本地不装 psycopg 也能以文件模式运行
    try:
        import psycopg
    except ImportError as exc:
        raise DbStorageError(
            f"DATABASE_URL 已设置但未安装 psycopg：{exc}。"
            "请在 requirements.txt 安装 psycopg[binary] 后重新部署。"
        ) from exc
    url = os.environ["DATABASE_URL"].strip()
    try:
        return psycopg.connect(url, connect_timeout=8)
    except Exception as exc:
        raise DbStorageError(f"连接数据库失败：{exc}") from exc


def _ensure_schema(conn) -> None:
    """每个进程首次连接时建表（幂等）。"""
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
        conn.commit()
        _schema_ready = True
        logger.info("云端数据库表已就绪")


# --------------------------------------------------------------------------- #
# 配置读写
# --------------------------------------------------------------------------- #
def get_config() -> Optional[Dict[str, Any]]:
    """读取配置；表为空返回 None（由调用方决定种子来源）。"""
    with _connect() as conn:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM app_config WHERE id = 1")
            row = cur.fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError as exc:
        raise DbStorageError(f"数据库配置 JSON 解析失败：{exc}") from exc


def set_config(cfg: Dict[str, Any], backup: bool = True,
               keep_backups: int = DEFAULT_KEEP_BACKUPS) -> None:
    """保存配置；backup=True 时同事务内先把旧值快照进 config_backups 并裁剪超额备份。"""
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    backup_name = "config_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    with _connect() as conn:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            if backup:
                cur.execute(
                    "INSERT INTO config_backups (name, data, size) "
                    "SELECT %s, data, length(data) FROM app_config WHERE id = 1 "
                    "ON CONFLICT (name) DO NOTHING",
                    (backup_name,),
                )
                cur.execute(
                    "DELETE FROM config_backups WHERE name NOT IN "
                    "(SELECT name FROM config_backups ORDER BY name DESC LIMIT %s)",
                    (keep_backups,),
                )
            cur.execute(
                "INSERT INTO app_config (id, data, updated_at) VALUES (1, %s, %s) "
                "ON CONFLICT (id) DO UPDATE "
                "SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (payload, _now_str()),
            )


# --------------------------------------------------------------------------- #
# 备份
# --------------------------------------------------------------------------- #
def list_backups() -> List[Dict[str, Any]]:
    """备份列表，新→旧。形状与文件模式一致：[{name, size}]。"""
    with _connect() as conn:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT name, size FROM config_backups ORDER BY name DESC")
            rows = cur.fetchall()
    return [{"name": r[0], "size": r[1]} for r in rows]


def read_backup(name: str) -> Optional[Dict[str, Any]]:
    """读单个备份；不存在返回 None。"""
    with _connect() as conn:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM config_backups WHERE name = %s", (name,))
            row = cur.fetchone()
    if not row:
        return None
    return json.loads(row[0])


# --------------------------------------------------------------------------- #
# 登录日志
# --------------------------------------------------------------------------- #
def append_auth(success: bool, ip: str = "", reason: str = "") -> None:
    with _connect() as conn:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO auth_log (ts, ip, success, reason) VALUES (%s, %s, %s, %s)",
                (_now_str(), ip, success, reason),
            )


def recent_auth(limit: int = 50) -> List[Dict[str, Any]]:
    """最近登录日志，新→旧。形状与文件模式一致。"""
    with _connect() as conn:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ts, ip, success, reason FROM auth_log "
                "ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    return [{"ts": r[0], "ip": r[1], "success": r[2], "reason": r[3]} for r in rows]
