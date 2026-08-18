# -*- coding: utf-8 -*-
"""D404 值日看板核心逻辑（v3，在线可保存 Flask 系统）。

单一数据源 data/config.json，包含全部配置。
职责：
1. 持久化 config.json（原子写 + 保存前自动备份到 data/backup）；
2. 值日轮换（rotation.base_monday + order）；
3. 覆盖优先级：date_overrides > 节假日/课题组放假 > 星期规则；
4. 消息渲染、复制文案；
5. 公共视图构建（今天/明天/本周/下周）；
6. CSV / JSON 导入导出、配置校验。

不包含任何微信发送、定时器、localStorage 逻辑。
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import secrets
import shutil
import threading
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import db_storage

logger = logging.getLogger(__name__)

WEEKDAY_CN: List[str] = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
CHECK_ITEMS: List[str] = [
    "门窗是否关好", "水电是否关闭", "仪器设备是否正常",
    "桌面地面是否整洁", "垃圾是否已清理",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "data")
MAX_BACKUPS = 20

TPL_WEEKDAY_DEFAULT = """【D404实验室值日提醒】

日期：{date}（{weekday}）
今日值日：{duty_person}
所属组别：{group_name}
本周负责人：{leader}

请今日值日同学完成 D404 实验室值日与安全检查。
检查内容包括：门窗、水电、仪器设备、桌面地面、垃圾清理等。
完成后请拍照发至群内留存。"""

TPL_SATURDAY_DEFAULT = """【D404实验室周六大扫除提醒】

日期：{date}（{weekday}）
本周负责组：{group_name}
负责人：{leader}

请负责人组织本组完成 D404 实验室大扫除。
完成后请拍照发至群内留存。"""


def _today_monday_iso() -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def _default_config() -> Dict[str, Any]:
    return {
        "lab_name": "D404 实验室",
        "chat_name": "D404实验室",
        "admin_password": "d404admin",
        "rotation": {
            "base_monday": "2026-06-15",
            "base_group": 2,
            "order": [2, 3, 1],
        },
        "groups": [
            {"id": "g-1", "number": 1, "name": "第1组", "leader": "刘美雯",
             "members": ["刘美雯", "崔岳", "李知桐", "杨纳字", "张怀正"]},
            {"id": "g-2", "number": 2, "name": "第2组", "leader": "王子月",
             "members": ["王子月", "郭世龙", "李晨", "贾磊", "李珍珍"]},
            {"id": "g-3", "number": 3, "name": "第3组", "leader": "尚与新",
             "members": ["尚与新", "王羽鑫", "于功文", "渠迪", "赵楠"]},
        ],
        "skip_days": [
            {"id": "h-newyear", "name": "元旦", "kind": "holiday", "start": "2026-01-01", "end": "2026-01-01"},
            {"id": "h-spring", "name": "春节", "kind": "holiday", "start": "2026-02-15", "end": "2026-02-21"},
            {"id": "h-labor", "name": "劳动节", "kind": "holiday", "start": "2026-05-01", "end": "2026-05-05"},
            {"id": "h-dragon", "name": "端午节", "kind": "holiday", "start": "2026-06-19", "end": "2026-06-21"},
            {"id": "h-national", "name": "国庆节", "kind": "holiday", "start": "2026-10-01", "end": "2026-10-07"},
            {"id": "c-summer", "name": "课题组暑假放假", "kind": "custom", "start": "2026-07-20", "end": "2026-08-30"},
        ],
        "templates": {"tpl_weekday": TPL_WEEKDAY_DEFAULT, "tpl_saturday": TPL_SATURDAY_DEFAULT},
        "date_overrides": [],
        "settings": {
            "weekday_times": [{"time": "10:00", "enabled": True}],
            "saturday_enabled": True,
            "saturday_times": [{"time": "10:00", "enabled": True}],
            "show_sunday": False,
            "show_countdown": True,
            "skip_holidays": True,
            "skip_custom": True,
            "notify_lead_minutes": 30,
        },
        "host": "0.0.0.0",
        "port": 8848,
        "public_mode_enabled": False,
        "public_url": "",
        "secret_key": "",
    }


# --------------------------------------------------------------------------- #
# JSON 工具
# --------------------------------------------------------------------------- #
def _read_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("读取 %s 失败，使用默认值：%s", path, exc)
        return default


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


# --------------------------------------------------------------------------- #
# 核心
# --------------------------------------------------------------------------- #
class DutyCore:
    """单一 config.json 读写 + 计算 + 导入导出 + 备份。线程安全。"""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self.backup_dir = os.path.join(self.data_dir, "backup")
        os.makedirs(self.backup_dir, exist_ok=True)
        self.config_path = os.path.join(self.data_dir, "config.json")
        # 云端模式：设置了 DATABASE_URL（如 Render 部署）时改用数据库持久化，
        # 避免 Render 免费版临时文件系统在重启后丢失全部修改。
        self.use_db = db_storage.enabled()
        self._lock = threading.RLock()
        self.ensure_defaults()

    # ---- 初始化 / 升级旧配置 ----
    def ensure_defaults(self) -> None:
        """数据库模式：表为空则用本地 config.json / example / 默认值作种子。
        文件模式：config.json 不存在则建默认；缺 secret_key 自动生成。"""
        with self._lock:
            if self.use_db:
                try:
                    if db_storage.get_config() is None:
                        seed = _read_json(self.config_path, None)
                        if seed is None:
                            seed = _read_json(
                                os.path.join(self.data_dir, "config.json.example"), None)
                        if seed is None:
                            seed = _default_config()
                        db_storage.set_config(seed)
                        logger.info("云端数据库为空，已写入初始配置")
                except Exception:
                    logger.exception("云端数据库初始化失败，本次运行的修改不会持久化")
                return
            if not os.path.exists(self.config_path):
                # 先尝试从 config.json.example 复制
                example_path = os.path.join(self.data_dir, "config.json.example")
                if os.path.exists(example_path):
                    try:
                        import shutil
                        shutil.copyfile(example_path, self.config_path)
                        cfg = _read_json(self.config_path, {})
                        # 如果 example 没有 secret_key 就生成
                        if not cfg.get("secret_key"):
                            cfg["secret_key"] = secrets.token_hex(32)
                            _write_json(self.config_path, cfg)
                        return
                    except OSError:
                        pass
                # 如果没有 example 就用默认配置
                cfg = _default_config()
                cfg["rotation"]["base_monday"] = _today_monday_iso()
                cfg["secret_key"] = secrets.token_hex(32)
                _write_json(self.config_path, cfg)
                return
            # 已存在：补齐可能缺失的字段（兼容旧版升级）
            cfg = _read_json(self.config_path, {})
            changed = self._migrate(cfg)
            if changed:
                _write_json(self.config_path, cfg)

    def _migrate(self, cfg: Dict[str, Any]) -> bool:
        """补齐默认字段；生成 secret_key。返回是否有改动。"""
        default = _default_config()
        changed = False
        for k, v in default.items():
            if k not in cfg:
                cfg[k] = json.loads(json.dumps(v))
                changed = True
        if not cfg.get("secret_key"):
            cfg["secret_key"] = secrets.token_hex(32)
            changed = True
        return changed

    # ---- 读写 ----
    def load_config(self) -> Dict[str, Any]:
        with self._lock:
            if self.use_db:
                try:
                    cfg = db_storage.get_config()
                except Exception:
                    logger.exception("从数据库读取配置失败，使用默认配置")
                    cfg = None
                if cfg is None:
                    cfg = _default_config()
                self._migrate(cfg)
                return cfg
            cfg = _read_json(self.config_path, _default_config())
            self._migrate(cfg)
            return cfg

    def save_config(self, cfg: Dict[str, Any], backup: bool = True) -> None:
        """数据库模式直接写库（备份在同事务内完成）；
        文件模式：保存前备份旧 config.json 到 data/backup，再原子写。"""
        with self._lock:
            self._migrate(cfg)
            if self.use_db:
                db_storage.set_config(cfg, backup=backup, keep_backups=MAX_BACKUPS)
                return
            if backup and os.path.exists(self.config_path):
                self._backup()
            _write_json(self.config_path, cfg)

    def _backup(self) -> None:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = os.path.join(self.backup_dir, f"config_{ts}.json")
            shutil.copy2(self.config_path, dst)
            # 只保留最近 MAX_BACKUPS 个
            files = [f for f in os.listdir(self.backup_dir) if f.startswith("config_") and f.endswith(".json")]
            files.sort()
            for old in files[:-MAX_BACKUPS]:
                try:
                    os.remove(os.path.join(self.backup_dir, old))
                except OSError:
                    pass
        except OSError as exc:
            logger.warning("备份失败（不影响保存）：%s", exc)

    def list_backups(self) -> List[Dict[str, Any]]:
        if self.use_db:
            try:
                return db_storage.list_backups()
            except Exception:
                logger.exception("读取云端备份列表失败")
                return []
        if not os.path.isdir(self.backup_dir):
            return []
        out = []
        for f in sorted(os.listdir(self.backup_dir), reverse=True):
            if f.startswith("config_") and f.endswith(".json"):
                p = os.path.join(self.backup_dir, f)
                out.append({"name": f, "size": os.path.getsize(p)})
        return out

    def read_backup(self, name: str) -> Optional[Dict[str, Any]]:
        """按名称读备份内容；不存在或名称非法返回 None。"""
        if not name.startswith("config_") or not name.endswith(".json"):
            return None
        if self.use_db:
            try:
                return db_storage.read_backup(name)
            except Exception:
                logger.exception("读取云端备份失败：%s", name)
                return None
        path = os.path.join(self.backup_dir, name)
        if not os.path.isfile(path):
            return None
        return _read_json(path, None)

    # ---- 登录日志（公网暴露后用于排查暴力破解）----
    def log_auth(self, success: bool, ip: str = "", reason: str = "") -> None:
        if self.use_db:
            try:
                db_storage.append_auth(success, ip, reason)
            except Exception:
                logger.warning("写入云端登录日志失败")
            return
        path = os.path.join(self.data_dir, "auth.log")
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ip": ip, "success": success, "reason": reason,
                }, ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("写入登录日志失败")

    def read_auth_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.use_db:
            try:
                return db_storage.recent_auth(limit)
            except Exception:
                logger.exception("读取云端登录日志失败")
                return []
        path = os.path.join(self.data_dir, "auth.log")
        if not os.path.exists(path):
            return []
        with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        out: List[Dict[str, Any]] = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out

    # ---- 轮换 ----
    def week_monday(self, d: date) -> date:
        return d - timedelta(days=d.weekday())

    def get_group_number(self, d: date, cfg: Dict[str, Any]) -> int:
        rot = cfg.get("rotation", {})
        order = rot.get("order", [])
        if not order:
            return rot.get("base_group", 1)
        base_mon = _parse_date(rot["base_monday"])
        weeks = (self.week_monday(d) - base_mon).days // 7
        return order[weeks % len(order)]

    def get_group(self, d: date, cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        num = self.get_group_number(d, cfg)
        for g in cfg.get("groups", []):
            if g.get("number") == num:
                return g
        return None

    def get_duty_person(self, d: date, group: Optional[Dict[str, Any]]) -> str:
        if not group:
            return "（未配置）"
        members = group.get("members", [])
        idx = d.weekday()
        if 0 <= idx < len(members) and members[idx]:
            return members[idx]
        return group.get("leader", "（未配置）")

    # ---- 覆盖与停提醒 ----
    def get_override(self, d: date, cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ds = d.isoformat()
        for ov in cfg.get("date_overrides", []):
            if ov.get("date") == ds:
                return ov
        return None

    def is_skip_day(self, d: date, cfg: Dict[str, Any]) -> Tuple[bool, str, str, str]:
        """是否落入节假日/课题组放假区间（受 settings 开关约束）。返回 (命中, 名称, kind, 范围)。"""
        st = cfg.get("settings", {})
        ds = d.isoformat()
        for item in cfg.get("skip_days", []):
            try:
                if not (item["start"] <= ds <= item["end"]):
                    continue
            except (KeyError, TypeError):
                continue
            kind = item.get("kind", "custom")
            if kind == "holiday" and not st.get("skip_holidays", True):
                continue
            if kind == "custom" and not st.get("skip_custom", True):
                continue
            return True, item.get("name", "停提醒"), kind, f"{item['start']} ~ {item['end']}"
        return False, "", "", ""

    # ---- 单日信息（含覆盖优先级）----
    def build_day_info(self, d: date, cfg: Dict[str, Any]) -> Dict[str, Any]:
        group = self.get_group(d, cfg) or {}
        wd = d.weekday()
        ov = self.get_override(d, cfg)
        info: Dict[str, Any] = {
            "date": d.isoformat(), "weekday": WEEKDAY_CN[wd],
            "group_name": group.get("name", ""), "leader": group.get("leader", ""),
            "kind": "", "person": "",
            "skipped": False, "skip_name": "", "skip_kind": "", "skip_range": "",
            "manual": False,
        }

        def weekday_kind() -> Tuple[str, str]:
            if wd < 5:
                return "duty", self.get_duty_person(d, group)
            if wd == 5:
                return "saturday", group.get("leader", "")
            return "sunday", ""

        # 1) 手动覆盖优先级最高
        if ov:
            mode = ov.get("mode", "auto")
            if mode == "paused":
                info["kind"], info["person"] = "skip", ""
                info["skipped"] = True
                info["skip_name"] = ov.get("reason") or "手动暂停"
                info["skip_kind"] = "manual"
                info["manual"] = True
                return info
            if mode == "normal":
                info["kind"], info["person"] = weekday_kind()
                info["manual"] = True
                return info
        # 2) 节假日 / 课题组放假
        hit, name, kind, rng = self.is_skip_day(d, cfg)
        if hit:
            info["kind"], info["person"] = "skip", ""
            info["skipped"] = True
            info["skip_name"] = name
            info["skip_kind"] = kind
            info["skip_range"] = rng
            return info
        # 3) 星期规则
        info["kind"], info["person"] = weekday_kind()
        return info

    def next_duty_day(self, start: date, cfg: Dict[str, Any], max_days: int = 14) -> Optional[Dict[str, Any]]:
        for i in range(1, max_days + 1):
            d = start + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            info = self.build_day_info(d, cfg)
            if not info["skipped"]:
                return info
        return None

    # ---- 消息渲染 ----
    @staticmethod
    def render(tpl: str, variables: Dict[str, Any]) -> str:
        out = tpl
        for k, v in variables.items():
            out = out.replace("{" + k + "}", str(v))
        return out.strip()

    def build_message(self, d: date, mtype: str, cfg: Dict[str, Any]) -> str:
        group = self.get_group(d, cfg) or {}
        variables = {
            "date": d.isoformat(), "weekday": WEEKDAY_CN[d.weekday()],
            "group_name": group.get("name", "（未配置）"),
            "leader": group.get("leader", "（未配置）"),
            "duty_person": self.get_duty_person(d, group),
            "chat_name": cfg.get("chat_name", ""),
        }
        tpl = cfg.get("templates", {}).get("tpl_saturday", "") if mtype == "saturday" \
            else cfg.get("templates", {}).get("tpl_weekday", "")
        return self.render(tpl, variables)

    # ---- 复制文案 ----
    def copy_today(self, d: date, cfg: Dict[str, Any]) -> str:
        info = self.build_day_info(d, cfg)
        return self.build_message(d, "saturday" if info["kind"] == "saturday" else "duty", cfg)

    def copy_tomorrow(self, d: date, cfg: Dict[str, Any]) -> str:
        return self.copy_today(d + timedelta(days=1), cfg)

    def copy_week(self, wm: date, cfg: Dict[str, Any]) -> str:
        lines = [f"【{cfg.get('lab_name', 'D404 实验室')}本周值日安排】", ""]
        g = self.get_group(wm, cfg) or {}
        lines.append(f"本周负责组：{g.get('name', '')}（负责人：{g.get('leader', '')}）")
        for i in range(6):
            d = wm + timedelta(days=i)
            info = self.build_day_info(d, cfg)
            if info["skipped"]:
                lines.append(f"{info['weekday']}（{d.strftime('%m-%d')}）暂停（{info['skip_name']}）")
            elif info["kind"] == "saturday":
                lines.append(f"{info['weekday']}（{d.strftime('%m-%d')}）大扫除 · {info['person']}")
            else:
                lines.append(f"{info['weekday']}（{d.strftime('%m-%d')}）{info['person']}")
        st = cfg.get("settings", {})
        wt = ", ".join(t["time"] for t in st.get("weekday_times", []) if t.get("enabled", True)) or "无"
        sat = ", ".join(t["time"] for t in st.get("saturday_times", []) if t.get("enabled", True)) or "无"
        lines += ["", f"工作日提醒时间：{wt}", f"周六大扫除提醒时间：{sat}"]
        return "\n".join(lines)

    def copy_announcement(self, wm: date, cfg: Dict[str, Any]) -> str:
        g = self.get_group(wm, cfg) or {}
        members = g.get("members", [])
        days = ["周一", "周二", "周三", "周四", "周五"]
        lines = [f"【{cfg.get('lab_name', 'D404 实验室')}值日公告】", "",
                 f"本周负责组：{g.get('name', '')}", f"负责人：{g.get('leader', '')}", ""]
        for i, dn in enumerate(days):
            lines.append(f"{dn}：{members[i] if i < len(members) else '—'}")
        lines.append(f"周六：大扫除（负责人：{g.get('leader', '')}）")
        lines += ["", "请值日同学按时完成值日与安全检查，完成后拍照发群。"]
        return "\n".join(lines)

    # ---- 公共视图 ----
    def build_public_view(self, d: date, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cfg = cfg if cfg is not None else self.load_config()
        wm = self.week_monday(d)
        today = self.build_day_info(d, cfg)
        tomorrow = self.build_day_info(d + timedelta(days=1), cfg)
        this_week = [self.build_day_info(wm + timedelta(days=i), cfg) for i in range(6)]
        next_wm = wm + timedelta(days=7)
        next_group = self.get_group(next_wm, cfg) or {}
        next_week = {
            "week_monday": next_wm.isoformat(),
            "group_name": next_group.get("name", ""),
            "leader": next_group.get("leader", ""),
            "members": next_group.get("members", []),
        }
        if today["skipped"]:
            today["next_duty"] = self.next_duty_day(d, cfg)
        return {
            "lab_name": cfg.get("lab_name", ""),
            "chat_name": cfg.get("chat_name", ""),
            "public_mode_enabled": cfg.get("public_mode_enabled", False),
            "public_url": cfg.get("public_url", ""),
            "today": today,
            "tomorrow": tomorrow,
            "this_week": this_week,
            "next_week": next_week,
            "check_items": CHECK_ITEMS,
            "copy": {
                "today": self.copy_today(d, cfg),
                "tomorrow": self.copy_tomorrow(d, cfg),
                "week": self.copy_week(wm, cfg),
                "announcement": self.copy_announcement(wm, cfg),
            },
        }

    # ---- 今日状态（操作今天那条 date_override）----
    def set_today_status(self, cfg: Dict[str, Any], mode: str, reason: str = "") -> Dict[str, Any]:
        """mode: auto | normal | paused。auto = 删除今天的覆盖。"""
        today = date.today().isoformat()
        cfg["date_overrides"] = [ov for ov in cfg.get("date_overrides", []) if ov.get("date") != today]
        if mode in ("normal", "paused"):
            cfg["date_overrides"].append({"id": "today-" + today, "date": today, "mode": mode, "reason": reason})
        return cfg

    # ---- 校验 ----
    @staticmethod
    def validate_config(obj: Any) -> Tuple[bool, str]:
        if not isinstance(obj, dict):
            return False, "配置必须是 JSON 对象"
        for k in ("lab_name", "groups", "rotation"):
            if k not in obj:
                return False, f"缺少字段：{k}"
        if not isinstance(obj.get("groups"), list) or not obj["groups"]:
            return False, "groups 必须是非空数组"
        for g in obj["groups"]:
            if "number" not in g or "members" not in g:
                return False, "每组需包含 number 与 members"
        return True, ""

    # ---- CSV 导入导出 ----
    def export_csv(self, cfg: Dict[str, Any]) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["组号", "组名", "负责人", "周一", "周二", "周三", "周四", "周五"])
        for g in cfg.get("groups", []):
            m = g.get("members", [])
            w.writerow([g.get("number"), g.get("name"), g.get("leader")] +
                       [m[i] if i < len(m) else "" for i in range(5)])
        return buf.getvalue()

    def import_csv(self, text: str) -> Tuple[bool, List[Dict[str, Any]], str]:
        """解析 CSV 为 groups 列表（不直接写盘，由调用方决定保存）。"""
        rows = list(csv.reader(io.StringIO(text)))
        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows:
            return False, [], "CSV 为空"
        rows = rows[1:] if len(rows[0]) >= 3 and "组号" in rows[0][0] else rows  # 跳过表头
        groups: List[Dict[str, Any]] = []
        for i, r in enumerate(rows):
            if len(r) < 8:
                return False, [], f"第 {i + 2} 行字段不足（需 8 列）"
            try:
                num = int(str(r[0]).strip())
            except ValueError:
                return False, [], f"第 {i + 2} 行组号不是数字：{r[0]}"
            groups.append({
                "id": f"g-{num}", "number": num,
                "name": r[1].strip(), "leader": r[2].strip(),
                "members": [c.strip() for c in r[3:8]],
            })
        return True, groups, ""

    def apply_csv_groups(self, cfg: Dict[str, Any], groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """用导入的 groups 替换；同步 order 包含全部组号。"""
        cfg["groups"] = groups
        nums = [g["number"] for g in groups]
        # 保留 order 中仍存在的组号顺序，再补新组号
        order = [n for n in cfg.get("rotation", {}).get("order", []) if n in nums]
        for n in nums:
            if n not in order:
                order.append(n)
        cfg.setdefault("rotation", {})["order"] = order
        if "base_group" not in cfg["rotation"]:
            cfg["rotation"]["base_group"] = nums[0] if nums else 1
        return cfg
