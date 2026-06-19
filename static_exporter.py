# -*- coding: utf-8 -*-
"""静态发布文件生成器。

把公共展示页（templates/public_preview.html）+ 静态资源 + 数据 JSON 复制到 dist/，
得到的 dist 可直接部署到 GitHub Pages / Cloudflare Pages / 学校服务器，无需后端。

dist 结构：
  dist/index.html            （由 public_preview.html 复制，纯静态）
  dist/static/style.css, public.js, manifest.json
  dist/data/config.json, duty_groups.json, skip_days.json, templates.json
"""
from __future__ import annotations

import logging
import os
import shutil
from typing import Any, Dict, Optional

from duty_core import DutyCore

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_FILES = ["style.css", "public.js", "manifest.json"]
DATA_FILES = ["config.json", "duty_groups.json", "skip_days.json", "templates.json"]


def export_project(base_dir: Optional[str] = None, core: Optional[DutyCore] = None) -> Dict[str, Any]:
    """生成/刷新 dist 目录。返回生成文件清单。"""
    base_dir = base_dir or BASE_DIR
    core = core or DutyCore(os.path.join(base_dir, "data"))

    dist_dir = os.path.join(base_dir, "dist")
    dist_static = os.path.join(dist_dir, "static")
    dist_data = os.path.join(dist_dir, "data")

    # 清理重建 dist（避免残留旧文件）
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_static, exist_ok=True)
    os.makedirs(dist_data, exist_ok=True)

    copied, missing = [], []

    # 1) 公共页 → index.html（必须是纯静态 HTML，无 Jinja 标签）
    src_html = os.path.join(base_dir, "templates", "public_preview.html")
    if os.path.exists(src_html):
        shutil.copyfile(src_html, os.path.join(dist_dir, "index.html"))
        copied.append("dist/index.html")
    else:
        missing.append("templates/public_preview.html")

    # 2) 静态资源
    for fn in STATIC_FILES:
        s = os.path.join(base_dir, "static", fn)
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(dist_static, fn))
            copied.append(f"dist/static/{fn}")
        else:
            missing.append(f"static/{fn}")

    # 3) 数据文件（公共页需要全部 4 个）
    for fn in DATA_FILES:
        s = os.path.join(base_dir, "data", fn)
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(dist_data, fn))
            copied.append(f"dist/data/{fn}")
        else:
            missing.append(f"data/{fn}")

    # 4) 生成 dist/README，提示部署方式
    try:
        with open(os.path.join(dist_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(_DIST_README)
        copied.append("dist/README.md")
    except OSError:
        pass

    files_info = []
    for root, _dirs, fs in os.walk(dist_dir):
        for name in fs:
            p = os.path.join(root, name)
            files_info.append({
                "path": os.path.relpath(p, base_dir).replace("\\", "/"),
                "size": os.path.getsize(p),
            })

    logger.info("已生成 dist：%d 个文件", len(files_info))
    return {
        "ok": not missing,
        "dist": dist_dir,
        "count": len(files_info),
        "files": files_info,
        "missing": missing,
    }


_DIST_README = """# D404 实验室值日看板 · 发布目录

本目录由本地管理器「生成/更新发布文件」按钮生成，是纯静态网站，无需后端。

## 部署方式
- **GitHub Pages**：把整个 dist 内容上传到仓库（建议放仓库根目录或 docs/），仓库 Settings → Pages → Source 选对应分支/目录。
- **Cloudflare Pages**：新建项目 → 直接上传 dist 目录（或连接仓库指向 dist）。
- **学校服务器**：把 dist 内所有文件拷到 Web 服务器静态目录（如 nginx 的 html/）。
- **临时分享**：双击本目录里的 index.html 即可在本机浏览器打开（仅本机可见）。

## 复制到微信群
部署后得到一个 https 链接，把链接发到「D404实验室」群，或设为群公告即可。

## 重新生成
在本地管理页（http://127.0.0.1:8848/admin）修改配置后，再次点「生成/更新发布文件」并重新部署即可更新看板。
"""
