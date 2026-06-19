# -*- coding: utf-8 -*-
"""值日看板核心逻辑（Python 端，供 Flask 管理/API 使用）。

公共展示页（静态 dist）在 public.js 中镜像实现同一套算法，二者须保持一致。
本模块职责：
1. 持久化 config / duty_groups / skip_days / templates（JSON，原子写，缺省自动建）；
2. 值日轮换：基准周周一 + order 循环 → 任意日期组别与值日人；
3. 停提醒判断：法定节假日 / 课题组放假（单日 + 区间）；
4. 消息渲染：占位符替换；
5. 构建公共展示视图（今天/明天/本周/下周/提醒时间/复制文案）。

注意：本版本不含任何微信发送、定时器、去重、日志逻辑。
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

WEEKDAY_CN: List[str] = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 展示用检查事项（公共页与管理端共用）
CHECK_ITEMS: List[str] = [
    "门窗是否关好",
    "水电是否关闭",
    "仪器设备是否正常",
    "桌面地面是否整洁",
    "垃圾是否已清理",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "data")


# --------------------------------------------------------------------------- #
# 默认数据
# --------------------------------------------------------------------------- #
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


DEFAULT_CONFIG: Dict[str, Any] = {
    "lab_name": "D404 实验室",
    "chat_name": "D404实验室",
    "weekday_times": [{"time": "10:00", "enabled": True}],
    "saturday_enabled": True,
    "saturday_times": [{"time": "10:00", "enabled": True}],
    "show_sunday": False,        # 周日是否显示提醒
    "show_countdown": True,      # 是否显示倒计时
    "skip_holidays": True,
    "skip_custom": True,
    "notify_lead_minutes": 30,   # 提醒前 N 分钟页面提示
    "host": "127.0.0.1",
    "port": 8848,
}

DEFAULT_DUTY: Dict[str, Any] = {
    "groups": [
        {"id": "g-1", "number": 1, "name": "第1组", "leader": "刘美雯",
         "members": ["刘美雯", "崔岳", "李知桐", "杨纳字", "张怀正"]},
        {"id": "g-2", "number": 2, "name": "第2组", "leader": "王子月",
         "members": ["王子月", "郭世龙", "李晨", "贾磊", "李珍珍"]},
        {"id": "g-3", "number": 3, "name": "第3组", "leader": "尚与新",
         "members": ["尚与新", "王羽鑫", "于功文", "渠迪", "赵楠"]},
    ],
    "order": [2, 3, 1],
    "base_monday": "2026-06-15",
    "base_group": 2,
}

DEFAULT_SKIP: Dict[str, Any] = {
    "skip_days": [
        {"id": "h-newyear", "name": "元旦", "kind": "holiday", "start": "2026-01-01", "end": "2026-01-01"},
        {"id": "h-spring", "name": "春节", "kind": "holiday", "start": "2026-02-15", "end": "2026-02-21"},
        {"id": "h-labor", "name": "劳动节", "kind": "holiday", "start": "2026-05-01", "end": "2026-05-05"},
        {"id": "h-dragon", "name": "端午节", "kind": "holiday", "start": "2026-06-19", "end": "2026-06-21"},
        {"id": "h-national", "name": "国庆节", "kind": "holiday", "start": "2026-10-01", "end": "2026-10-07"},
        {"id": "c-summer", "name": "课题组暑假放假", "kind": "custom", "start": "2026-07-20", "end": "2026-08-30"},
    ]
}

DEFAULT_TEMPLATES: Dict[str, Any] = {
    "tpl_weekday": TPL_WEEKDAY_DEFAULT,
    "tpl_saturday": TPL_SATURDAY_DEFAULT,
}


# --------------------------------------------------------------------------- #
# JSON 工具
# --------------------------------------------------------------------------- #
def _read_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            _write_json(path, default)
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
    """配置读写 + 值日计算 + 公共视图构建。线程安全（单把可重入锁）。"""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self.paths: Dict[str, str] = {
            "config": os.path.join(self.data_dir, "config.json"),
            "duty": os.path.join(self.data_dir, "duty_groups.json"),
            "skip": os.path.join(self.data_dir, "skip_days.json"),
            "templates": os.path.join(self.data_dir, "templates.json"),
        }
        self._lock = threading.RLock()
        self.ensure_defaults()

    # ---- 初始化 ----
    def ensure_defaults(self) -> None:
        with self._lock:
            if not os.path.exists(self.paths["config"]):
                _write_json(self.paths["config"], DEFAULT_CONFIG)
            if not os.path.exists(self.paths["duty"]):
                d = json.loads(json.dumps(DEFAULT_DUTY))
                d["base_monday"] = _today_monday_iso()
                _write_json(self.paths["duty"], d)
            if not os.path.exists(self.paths["skip"]):
                _write_json(self.paths["skip"], DEFAULT_SKIP)
            if not os.path.exists(self.paths["templates"]):
                _write_json(self.paths["templates"], DEFAULT_TEMPLATES)

    # ---- 读写 ----
    def load_config(self) -> Dict[str, Any]:
        with self._lock:
            return _read_json(self.paths["config"], DEFAULT_CONFIG)

    def save_config(self, cfg: Dict[str, Any]) -> None:
        with self._lock:
            _write_json(self.paths["config"], cfg)

    def load_duty(self) -> Dict[str, Any]:
        with self._lock:
            return _read_json(self.paths["duty"], DEFAULT_DUTY)

    def save_duty(self, duty: Dict[str, Any]) -> None:
        self._normalize_duty(duty)
        with self._lock:
            _write_json(self.paths["duty"], duty)

    def load_skip(self) -> Dict[str, Any]:
        with self._lock:
            return _read_json(self.paths["skip"], DEFAULT_SKIP)

    def save_skip(self, skip: Dict[str, Any]) -> None:
        with self._lock:
            _write_json(self.paths["skip"], skip)

    def load_templates(self) -> Dict[str, Any]:
        with self._lock:
            return _read_json(self.paths["templates"], DEFAULT_TEMPLATES)

    def save_templates(self, tpl: Dict[str, Any]) -> None:
        with self._lock:
            _write_json(self.paths["templates"], tpl)

    @staticmethod
    def _normalize_duty(duty: Dict[str, Any]) -> None:
        for g in duty.get("groups", []):
            if "id" not in g:
                g["id"] = f"g-{g.get('number', '')}"
            members = g.get("members", [])
            while len(members) < 5:
                members.append("")
            g["members"] = members[:5]

    # ---- 轮换 ----
    def week_monday(self, d: date) -> date:
        return d - timedelta(days=d.weekday())

    def get_group_number(self, d: date, duty: Optional[Dict[str, Any]] = None) -> int:
        duty = duty if duty is not None else self.load_duty()
        order = duty.get("order", [])
        if not order:
            return duty.get("base_group", 1)
        base_mon = _parse_date(duty["base_monday"])
        weeks = (self.week_monday(d) - base_mon).days // 7
        return order[weeks % len(order)]

    def get_group(self, d: date, duty: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        duty = duty if duty is not None else self.load_duty()
        num = self.get_group_number(d, duty)
        for g in duty.get("groups", []):
            if g.get("number") == num:
                return g
        return None

    def get_duty_person(self, d: date, group: Optional[Dict[str, Any]] = None) -> str:
        if group is None:
            group = self.get_group(d)
        if not group:
            return "（未配置）"
        members = group.get("members", [])
        idx = d.weekday()
        if 0 <= idx < len(members) and members[idx]:
            return members[idx]
        return group.get("leader", "（未配置）")

    # ---- 停提醒 ----
    def is_skip_day(self, d: date, skip: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str, str, str]:
        """返回 (命中, 名称, kind, start, end)。"""
        skip = skip if skip is not None else self.load_skip()
        for item in skip.get("skip_days", []):
            try:
                s, e = _parse_date(item["start"]), _parse_date(item["end"])
            except (KeyError, ValueError):
                continue
            if s <= d <= e:
                return True, item.get("name", "停提醒"), item.get("kind", "custom"), item["start"], item["end"]
        return False, "", "", "", ""

    def skip_for_config(self, d: date, config: Dict[str, Any]) -> Tuple[bool, str, str, str, str]:
        hit, name, kind, s, e = self.is_skip_day(d)
        if not hit:
            return False, "", "", "", ""
        if kind == "holiday" and not config.get("skip_holidays", True):
            return False, "", "", "", ""
        if kind == "custom" and not config.get("skip_custom", True):
            return False, "", "", "", ""
        return True, name, kind, s, e

    # ---- 提醒时间 ----
    def get_reminders_for_date(self, d: date, config: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
        config = config if config is not None else self.load_config()
        wd = d.weekday()
        out: List[Tuple[str, str]] = []
        if wd < 5:
            for t in config.get("weekday_times", []):
                if t.get("enabled", True):
                    out.append((t["time"], "duty"))
        elif wd == 5:
            if config.get("saturday_enabled", True):
                for t in config.get("saturday_times", []):
                    if t.get("enabled", True):
                        out.append((t["time"], "saturday"))
        elif wd == 6:
            if config.get("show_sunday", False):
                for t in config.get("weekday_times", []):
                    if t.get("enabled", True):
                        out.append((t["time"], "duty"))
        return out

    # ---- 消息渲染 ----
    @staticmethod
    def render(tpl: str, variables: Dict[str, Any]) -> str:
        out = tpl
        for k, v in variables.items():
            out = out.replace("{" + k + "}", str(v))
        return out.strip()

    def build_message(self, d: date, mtype: str,
                      config: Optional[Dict[str, Any]] = None,
                      duty: Optional[Dict[str, Any]] = None,
                      templates: Optional[Dict[str, Any]] = None) -> str:
        config = config if config is not None else self.load_config()
        duty = duty if duty is not None else self.load_duty()
        templates = templates if templates is not None else self.load_templates()
        group = self.get_group(d, duty) or {}
        variables = {
            "date": d.isoformat(), "weekday": WEEKDAY_CN[d.weekday()],
            "group_name": group.get("name", "（未配置）"),
            "leader": group.get("leader", "（未配置）"),
            "duty_person": self.get_duty_person(d, group),
            "chat_name": config.get("chat_name", ""),
        }
        tpl = templates.get("tpl_saturday", "") if mtype == "saturday" else templates.get("tpl_weekday", "")
        return self.render(tpl, variables)

    # ---- 单日信息 ----
    def build_day_info(self, d: date,
                       config: Optional[Dict[str, Any]] = None,
                       duty: Optional[Dict[str, Any]] = None,
                       skip: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """构建某一天的展示信息。kind: duty / saturday / sunday / skip。"""
        config = config if config is not None else self.load_config()
        duty = duty if duty is not None else self.load_duty()
        skip = skip if skip is not None else self.load_skip()

        group = self.get_group(d, duty) or {}
        skipped, skip_name, skip_kind, s_start, s_end = self.skip_for_config(d, config)
        wd = d.weekday()

        info: Dict[str, Any] = {
            "date": d.isoformat(),
            "weekday": WEEKDAY_CN[wd],
            "group_name": group.get("name", ""),
            "leader": group.get("leader", ""),
            "skipped": skipped,
            "skip_name": skip_name,
            "skip_kind": skip_kind,
            "skip_range": f"{s_start} ~ {s_end}" if skipped else "",
            "kind": "",
            "person": "",
        }

        if skipped:
            info["kind"] = "skip"
            info["person"] = ""
        elif wd < 5:
            info["kind"] = "duty"
            info["person"] = self.get_duty_person(d, group)
        elif wd == 5:
            info["kind"] = "saturday"
            info["person"] = group.get("leader", "")
        else:
            info["kind"] = "sunday"
            info["person"] = ""
        return info

    # ---- 下一个值日日 ----
    def next_duty_day(self, start: date, max_days: int = 14,
                      config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """从 start 的次日起，找下一个非停提醒的工作日（周一到周五）。"""
        config = config if config is not None else self.load_config()
        for i in range(1, max_days + 1):
            d = start + timedelta(days=i)
            wd = d.weekday()
            if wd >= 5:  # 跳过周末（大扫除不算"值日日"）
                continue
            info = self.build_day_info(d, config=config)
            if not info["skipped"]:
                return info
        return None

    # ---- 复制文案 ----
    def copy_today(self, d: date) -> str:
        info = self.build_day_info(d)
        if info["kind"] == "saturday":
            return self.build_message(d, "saturday")
        return self.build_message(d, "duty")

    def copy_tomorrow(self, d: date) -> str:
        return self.copy_today(d + timedelta(days=1))

    def copy_week(self, week_monday: date) -> str:
        config = self.load_config()
        lines = [f"【{config.get('lab_name','D404 实验室')}本周值日安排】", ""]
        for i in range(6):  # 周一到周六
            d = week_monday + timedelta(days=i)
            info = self.build_day_info(d, config=config)
            label = info["weekday"]
            if info["skipped"]:
                lines.append(f"{label}（{d.strftime('%m-%d')}）暂停（{info['skip_name']}）")
            elif info["kind"] == "saturday":
                lines.append(f"{label}（{d.strftime('%m-%d')}）大扫除 · {info['person']}")
            else:
                lines.append(f"{label}（{d.strftime('%m-%d')}）{info['person']}")
        g = self.get_group(week_monday) or {}
        lines.insert(1, f"本周负责组：{g.get('name','')}（负责人：{g.get('leader','')}）")
        wd_times = ", ".join(t["time"] for t in config.get("weekday_times", []) if t.get("enabled", True)) or "无"
        sat_times = ", ".join(t["time"] for t in config.get("saturday_times", []) if t.get("enabled", True)) or "无"
        lines += ["", f"工作日提醒时间：{wd_times}", f"周六大扫除提醒时间：{sat_times}"]
        return "\n".join(lines)

    def copy_announcement(self, week_monday: date) -> str:
        config = self.load_config()
        duty = self.load_duty()
        g = self.get_group(week_monday, duty) or {}
        members = g.get("members", [])
        days = ["周一", "周二", "周三", "周四", "周五"]
        lines = [
            f"【{config.get('lab_name','D404 实验室')}值日公告】",
            "",
            f"本周负责组：{g.get('name','')}",
            f"负责人：{g.get('leader','')}",
            "",
        ]
        for i, dn in enumerate(days):
            lines.append(f"{dn}：{members[i] if i < len(members) else '—'}")
        lines.append(f"周六：大扫除（负责人：{g.get('leader','')}）")
        lines += ["", "请值日同学按时完成值日与安全检查，完成后拍照发群。"]
        return "\n".join(lines)

    # ---- 公共展示视图 ----
    def build_public_view(self, d: date) -> Dict[str, Any]:
        config = self.load_config()
        duty = self.load_duty()
        templates = self.load_templates()
        wm = self.week_monday(d)
        today_info = self.build_day_info(d, config=config)
        tomorrow_info = self.build_day_info(d + timedelta(days=1), config=config)

        # 本周 周一~周六
        this_week = [self.build_day_info(wm + timedelta(days=i), config=config) for i in range(6)]
        # 下周
        next_wm = wm + timedelta(days=7)
        next_group = self.get_group(next_wm) or {}
        next_week = {
            "week_monday": next_wm.isoformat(),
            "group_name": next_group.get("name", ""),
            "leader": next_group.get("leader", ""),
            "members": next_group.get("members", []),
        }

        # 提醒时间
        reminders = self.get_reminders_for_date(d, config)

        # 若今天停提醒，附"下一个值日日"
        if today_info["skipped"]:
            today_info["next_duty"] = self.next_duty_day(d, config=config)

        # 模板预览：工作日模板按今天渲染；大扫除模板按本周六渲染（用于管理端预览）
        week_saturday = wm + timedelta(days=5)
        copy_preview = {
            "weekday": self.build_message(d, "duty", config, duty, templates),
            "saturday": self.build_message(week_saturday, "saturday", config, duty, templates),
        }

        return {
            "config": config,
            "today": today_info,
            "tomorrow": tomorrow_info,
            "this_week": this_week,
            "next_week": next_week,
            "reminders": [{"time": t, "type": mt} for t, mt in reminders],
            "check_items": CHECK_ITEMS,
            "copy": {
                "today": self.copy_today(d),
                "tomorrow": self.copy_tomorrow(d),
                "week": self.copy_week(wm),
                "announcement": self.copy_announcement(wm),
            },
            "copy_preview": copy_preview,
        }
