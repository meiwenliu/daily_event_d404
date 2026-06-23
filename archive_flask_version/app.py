# -*- coding: utf-8 -*-
"""D404 实验室值日看板 · 在线可保存 Flask 系统（v3）。

- 单一数据源 data/config.json，在线修改、保存前自动备份到 data/backup。
- 普通同学访问 / 只读看板（无需登录）；管理员 /login 登录后 /admin 在线编辑。
- 监听 0.0.0.0:8848，同一局域网手机可访问。
- 不接微信机器人、不依赖 localStorage 作主数据源。

路由：
  GET  /                公共看板（无需登录）
  GET  /login           登录页
  POST /login           提交密码
  GET  /logout          登出
  GET  /admin           管理后台（需登录）
  GET  /api/public[?date=]   公共视图（开放）
  GET  /api/admin/config     读全量配置（需登录）
  POST /api/admin/config     保存全量配置（需登录，自动备份）
  POST /api/admin/password   修改管理员密码
  GET  /api/admin/export/json   导出 config.json
  POST /api/admin/import/json   导入 config.json
  GET  /api/admin/export/csv    导出值日表 CSV
  POST /api/admin/import/csv    导入值日表 CSV
  GET  /api/admin/backups       备份列表
  POST /api/admin/backup/restore  恢复某备份
"""
from __future__ import annotations

import json
import logging
import threading
import webbrowser
from datetime import date
from functools import wraps
from typing import Any, Dict

from flask import (Flask, Response, jsonify, redirect, render_template,
                   request, session, url_for)

from duty_core import BASE_DIR, DutyCore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app")

core = DutyCore()
app = Flask(__name__)
app.secret_key = core.load_config().get("secret_key") or "d404-fallback-secret"


# --------------------------------------------------------------------------- #
# 鉴权装饰器
# --------------------------------------------------------------------------- #
def login_required_page(fn):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return _wrap


def login_required_api(fn):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"ok": False, "error": "未登录或登录已过期"}), 401
        return fn(*args, **kwargs)
    return _wrap


# --------------------------------------------------------------------------- #
# 页面
# --------------------------------------------------------------------------- #
@app.route("/")
def public_page():
    return render_template("public.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public_page"))


@app.route("/admin")
@login_required_page
def admin_page():
    return render_template("admin.html")


# --------------------------------------------------------------------------- #
# 登录 / 改密
# --------------------------------------------------------------------------- #
@app.route("/login", methods=["POST"])
def login_submit():
    body = request.get_json(silent=True) or {}
    pwd = str(body.get("password", ""))
    ip = request.headers.get("X-Forwarded-For") or request.remote_addr or ""
    cfg = core.load_config()
    if pwd and pwd == cfg.get("admin_password", ""):
        session["admin"] = True
        core.log_auth(True, ip)
        return jsonify({"ok": True})
    core.log_auth(False, ip, "密码错误")
    return jsonify({"ok": False, "error": "密码错误"}), 401


@app.route("/api/admin/password", methods=["POST"])
@login_required_api
def change_password():
    body = request.get_json(silent=True) or {}
    old, new = str(body.get("old", "")), str(body.get("new", ""))
    if len(new) < 4:
        return jsonify({"ok": False, "error": "新密码至少 4 位"}), 400
    cfg = core.load_config()
    if old != cfg.get("admin_password", ""):
        return jsonify({"ok": False, "error": "原密码错误"}), 401
    cfg["admin_password"] = new
    core.save_config(cfg)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# 公共 API（开放）
# --------------------------------------------------------------------------- #
@app.route("/api/public")
def api_public():
    date_str = request.args.get("date") or date.today().isoformat()
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"ok": False, "error": "日期格式应为 YYYY-MM-DD"}), 400
    return jsonify(core.build_public_view(target))


# --------------------------------------------------------------------------- #
# 管理 API（需登录）
# --------------------------------------------------------------------------- #
@app.route("/api/admin/config", methods=["GET", "POST"])
@login_required_api
def admin_config():
    if request.method == "GET":
        cfg = core.load_config()
        is_default = cfg.get("admin_password", "") == "d404admin"
        cfg.pop("secret_key", None)        # 不回传 secret_key
        cfg.pop("admin_password", None)    # 不回传密码明文
        cfg["is_default_password"] = is_default
        return jsonify(cfg)
    body = request.get_json(silent=True) or {}
    # 合并：保留服务端的 secret_key 与 admin_password（前端不掌握）
    cur = core.load_config()
    body["secret_key"] = cur.get("secret_key", "")
    if "admin_password" not in body:
        body["admin_password"] = cur.get("admin_password", "")
    ok, err = core.validate_config(body)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    try:
        core.save_config(body)
        return jsonify({"ok": True})
    except OSError as exc:
        logger.exception("保存失败")
        return jsonify({"ok": False, "error": f"保存失败：{exc}"}), 500


@app.route("/api/admin/export/json")
@login_required_api
def export_json():
    cfg = core.load_config()
    cfg.pop("secret_key", None)
    txt = json.dumps(cfg, ensure_ascii=False, indent=2)
    return Response(txt, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=config.json"})


@app.route("/api/admin/import/json", methods=["POST"])
@login_required_api
def import_json():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "JSON 对象无效"}), 400
    cur = core.load_config()
    body["secret_key"] = cur.get("secret_key", "")
    body.setdefault("admin_password", cur.get("admin_password", ""))
    ok, err = core.validate_config(body)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    core.save_config(body)
    return jsonify({"ok": True})


@app.route("/api/admin/export/csv")
@login_required_api
def export_csv():
    cfg = core.load_config()
    return Response(core.export_csv(cfg), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=duty_groups.csv"})


@app.route("/api/admin/import/csv", methods=["POST"])
@login_required_api
def import_csv():
    body = request.get_json(silent=True) or {}
    text = str(body.get("text", ""))
    ok, groups, err = core.import_csv(text)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    cfg = core.load_config()
    core.apply_csv_groups(cfg, groups)
    core.save_config(cfg)
    return jsonify({"ok": True, "groups": len(groups)})


@app.route("/api/admin/backups")
@login_required_api
def list_backups():
    return jsonify({"backups": core.list_backups()})


@app.route("/api/admin/backup/restore", methods=["POST"])
@login_required_api
def restore_backup():
    from duty_core import _read_json
    import os
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", ""))
    path = os.path.join(core.backup_dir, name)
    if not name.startswith("config_") or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "备份不存在"}), 404
    cfg = _read_json(path, {})
    ok, err = core.validate_config(cfg)
    if not ok:
        return jsonify({"ok": False, "error": f"备份无效：{err}"}), 400
    cur = core.load_config()
    cfg["secret_key"] = cur.get("secret_key", "")
    cfg.setdefault("admin_password", cur.get("admin_password", ""))
    core.save_config(cfg)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# 部署 / 安全 信息（需登录）
# --------------------------------------------------------------------------- #
@app.route("/api/admin/network")
@login_required_api
def admin_network():
    cfg = core.load_config()
    port = int(cfg.get("port", 8848))
    return jsonify({
        "local": f"http://127.0.0.1:{port}",
        "lan": f"http://{_lan_ip()}:{port}",
        "port": port,
        "public_mode_enabled": cfg.get("public_mode_enabled", False),
        "public_url": cfg.get("public_url", ""),
    })


@app.route("/api/admin/security")
@login_required_api
def admin_security():
    cfg = core.load_config()
    logs = core.read_auth_log(20)
    fails = [l for l in logs if not l.get("success")]
    return jsonify({
        "is_default_password": cfg.get("admin_password", "") == "d404admin",
        "recent_fail_count": len(fails),
        "recent_fails": fails[:5],
    })


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def _open_browser_later(url: str, delay: float = 1.5) -> None:
    timer = threading.Timer(delay, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def _lan_ip() -> str:
    """获取本机局域网 IP（失败返回 127.0.0.1）。"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main() -> None:
    cfg = core.load_config()
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", 8848))
    lan = _lan_ip()
    print("=" * 60)
    print("  D404 实验室值日看板（在线可保存版）已启动")
    print(f"  本机访问：  http://127.0.0.1:{port}")
    print(f"  局域网访问：http://{lan}:{port}   （手机与电脑同 WiFi 即可）")
    print(f"  管理后台：  http://127.0.0.1:{port}/admin   （默认密码 d404admin）")
    print("  关闭本窗口即停止服务。")
    print("=" * 60)
    _open_browser_later(f"http://127.0.0.1:{port}/")
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    except OSError as exc:
        print(f"\n[启动失败] 端口 {port} 可能被占用：{exc}")


if __name__ == "__main__":
    main()
