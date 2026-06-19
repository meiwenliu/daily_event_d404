# -*- coding: utf-8 -*-
"""D404 实验室值日看板 · 本地管理器（Flask）。

路由：
  /                     公共展示页（本地预览，纯静态 HTML）
  /admin                管理首页（基础设置）
  /admin/duty           值日人员管理
  /admin/holidays       节假日与放假
  /admin/reminders      提醒时间
  /admin/templates      消息模板

API：
  GET/POST /api/config, /api/duty, /api/skip, /api/templates
  GET      /api/preview?date=YYYY-MM-DD   公共视图 JSON（管理端预览用）
  POST     /api/export                    生成 dist 发布文件
  GET      /api/dist_status               dist 是否存在
  GET      /data/<filename>               供公共页 fetch 读取数据

运行： python app.py   访问： http://127.0.0.1:8848  （管理： /admin）
"""
from __future__ import annotations

import logging
import threading
import webbrowser
from datetime import date
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_from_directory

from duty_core import BASE_DIR, DutyCore
from static_exporter import export_project

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

core = DutyCore()
app = Flask(__name__)
DATA_DIR = core.data_dir


# =========================================================================== #
# 数据文件路由（供公共页 fetch ./data/*.json；dist 中为真实目录）
# =========================================================================== #
@app.route("/data/<path:filename>")
def data_file(filename: str):
    return send_from_directory(DATA_DIR, filename)


@app.route("/dist/")
@app.route("/dist/<path:filename>")
def dist_preview(filename: str = "index.html"):
    """本地预览已生成的 dist 发布目录。导出前不存在则提示。"""
    import os
    dist_dir = os.path.join(BASE_DIR, "dist")
    if not os.path.exists(os.path.join(dist_dir, "index.html")):
        return "尚未生成发布文件，请先在「基础设置」页点击「生成/更新发布文件」。", 404
    return send_from_directory(dist_dir, filename)


# =========================================================================== #
# 公共展示页（纯静态 HTML，本地预览）
# =========================================================================== #
@app.route("/")
def public_page():
    return render_template("public_preview.html")


# =========================================================================== #
# 管理页
# =========================================================================== #
@app.route("/admin")
def admin_home():
    return render_template("admin.html", active="home")


@app.route("/admin/duty")
def admin_duty():
    return render_template("duty_edit.html", active="duty")


@app.route("/admin/holidays")
def admin_holidays():
    return render_template("holidays.html", active="holidays")


@app.route("/admin/reminders")
def admin_reminders():
    return render_template("reminder_times.html", active="reminders")


@app.route("/admin/templates")
def admin_templates():
    return render_template("message_templates.html", active="templates")


# =========================================================================== #
# 配置 API
# =========================================================================== #
def _body() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify(core.load_config())
    core.save_config(_body())
    return jsonify({"ok": True})


@app.route("/api/duty", methods=["GET", "POST"])
def api_duty():
    if request.method == "GET":
        return jsonify(core.load_duty())
    core.save_duty(_body())
    return jsonify({"ok": True})


@app.route("/api/skip", methods=["GET", "POST"])
def api_skip():
    if request.method == "GET":
        return jsonify(core.load_skip())
    core.save_skip(_body())
    return jsonify({"ok": True})


@app.route("/api/templates", methods=["GET", "POST"])
def api_templates():
    if request.method == "GET":
        return jsonify(core.load_templates())
    core.save_templates(_body())
    return jsonify({"ok": True})


@app.route("/api/preview")
def api_preview():
    date_str = request.args.get("date") or date.today().isoformat()
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"ok": False, "reason": "日期格式应为 YYYY-MM-DD"}), 400
    return jsonify(core.build_public_view(target))


@app.route("/api/export", methods=["POST"])
def api_export():
    try:
        result = export_project(BASE_DIR, core)
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("导出失败")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/dist_status")
def api_dist_status():
    import os
    dist = os.path.join(BASE_DIR, "dist")
    return jsonify({"exists": os.path.exists(os.path.join(dist, "index.html"))})


# =========================================================================== #
# 入口
# =========================================================================== #
def _open_browser_later(url: str, delay: float = 1.5) -> None:
    timer = threading.Timer(delay, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def main() -> None:
    config = core.load_config()
    host = config.get("host", "127.0.0.1")
    port = int(config.get("port", 8848))
    url = f"http://{host}:{port}"

    print("=" * 56)
    print("  D404 实验室值日看板 · 本地管理器")
    print(f"  公共看板预览：{url}")
    print(f"  管理页面：  {url}/admin")
    print("  关闭本窗口即可停止。")
    print("=" * 56)

    _open_browser_later(f"{url}/admin")
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    except OSError as exc:
        print(f"\n[启动失败] 端口 {port} 可能被占用：{exc}")
        print("请关闭占用端口的程序，或在 data/config.json 中修改 port。")
    finally:
        pass


if __name__ == "__main__":
    main()
