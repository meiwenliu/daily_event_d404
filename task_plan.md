# D404 实验室值日看板 — 任务计划（v2，无微信机器人）

## 目标
本地 Flask 管理器（http://127.0.0.1:8848/admin）+ 可生成静态 dist 发布的公共展示页（手机/电脑浏览器可开）。
不接微信机器人、不用 wxauto、不控制微信。管理员手动复制提醒文字转发到微信群。

## 架构关键决策
- 公共展示页 = 纯静态（fetch ./data/*.json，客户端计算轮换/停提醒/消息）。Flask 仅做本地预览 + 管理 + 生成 dist。
- 公共页用相对路径（static/x、data/x），保证 Flask 预览与 GitHub Pages/Cloudflare Pages 部署都正常。
- 管理页用 Jinja + url_for 绝对路径（仅 Flask）。
- 核心逻辑双份保持一致：duty_core.py（Python，管理/API）≈ public.js（JS，公共页）。
- data：config.json（展示+提醒时间设置）、duty_groups.json（组+轮换基准）、skip_days.json（节假日/放假）、templates.json（消息模板）。

## 阶段
- [x] P0 清理旧 wxauto 项目（保留 data 配置 + .venv）
- [ ] P0 duty_core.py：轮换/停提醒/消息/公共视图/复制文案
- [ ] P0 app.py：/ 公共预览、/admin/* 管理页、/data 路由、API、/api/export
- [ ] P0 static_exporter.py：生成 dist（index.html + data/* + static/*）
- [ ] P1 公共页：public_preview.html + public.js + manifest.json（手机优先/复制/浏览器通知/倒计时/PWA）
- [ ] P1 管理页：base/admin/duty_edit/holidays/reminder_times/message_templates + admin.js
- [ ] P1 style.css（卡片/渐变/颜色区分，手机优先，无 CDN）
- [ ] P1 数据：config.json 重构 + templates.json；requirements/install/start/README
- [ ] P0 验证：核心逻辑单测、Flask 启动、dist 生成、公共页数据 fetch、轮换/停提醒一致

## 验证清单
- [ ] 轮换跨周正确（[2,3,1]）
- [ ] 周六=大扫除负责人；周日=无固定值日；节假日=暂停+下一个值日日
- [ ] 复制文案四类（今日/明日/本周/群公告）生成
- [ ] dist 静态可独立打开（相对路径）
- [ ] Python duty_core 与 public.js 对同一日期产出一致
