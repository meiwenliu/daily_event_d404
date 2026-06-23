# D404 值日看板 — 任务计划（v3，在线可保存 Flask 系统）

## 目标
从「GitHub Pages 静态本地改」升级为「常驻 Flask 在线编辑系统」：
- 普通同学访问 / 只读看板；管理员 /login 密码登录后 /admin 在线改值日表；
- 单一数据源 data/config.json（含全部配置）；保存前自动备份到 data/backup；
- 新增「今日状态覆盖」「指定日期覆盖」；导入导出 JSON/CSV；
- Flask 监听 0.0.0.0:8848，局域网手机可访问；不再依赖 localStorage 作主数据源。
- GitHub Pages 静态模型废弃（无法在线保存），移除 static_exporter/dist/部署工作流。

## 架构决策
- 单 config.json（settings+rotation+groups+skip_days+templates+date_overrides+admin_password+secret_key+host/port）。
- 覆盖统一进 date_overrides：今日状态 = 操作今天那条 date_override；优先级 date_override > 节假日/放假 > 星期规则。
- public 页 fetch /api/public（服务端算好视图）；admin 页 JS tabs 编辑，POST 受登录保护。
- 鉴权：Flask session + secret_key；写接口与 /admin 全部要求登录；/ 与 /api/public 开放。

## 阶段
- [x] 计划 v3
- [ ] P0 duty_core.py：单 config、覆盖、视图、复制、CSV/JSON、备份
- [ ] P0 app.py：session 鉴权、/ /login /admin /logout、/api/public、/api/admin/* 受保护
- [ ] P0 data/config.json 合并（迁移现有数据）
- [ ] P1 前端：public 页(精简,无提醒卡/页脚)、login 页、admin 页(7 tabs)、admin.js、style.css
- [ ] P1 移除过时文件：static_exporter.py、dist/、.github/workflows、拆分数据文件、旧 admin 子页、manifest
- [ ] P1 install/start(0.0.0.0)/README/requirements
- [ ] P0 验证：登录/受保护、覆盖优先级、今日暂停、CSV/JSON 导入导出、备份、LAN 监听

## 验证清单
- [ ] 未登录访问 /api/admin/* → 401/重定向；/api/public 开放
- [ ] 今天手动暂停 → 首页显示暂停+原因+下一个值日日
- [ ] 手动正常 → 覆盖节假日显示正常值日
- [ ] 指定日期覆盖优先于节假日
- [ ] 保存 config → data/backup 生成备份；首页刷新见最新
- [ ] CSV 导出/导入 round-trip；JSON 导入导出
- [ ] 服务监听 0.0.0.0:8848
