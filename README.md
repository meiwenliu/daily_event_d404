# D404 值日助手

D404 实验室值日看板系统 - 在线可保存版

---

## 🚀 免费云部署（推荐！）

### 优点：
- ✅ 完全免费
- ✅ 24小时运行，不用开电脑
- ✅ 固定公网链接，不会变
- ✅ 局域网和外网都能访问

---

## 📋 部署步骤

### 第1步：把代码传到 GitHub
1. 注册 GitHub 账号：https://github.com
2. 创建新仓库，设为 Public 或 Private 都可以
3. 把这个文件夹推上去

**注意**：data/config.json 已经在 .gitignore 里，不会上传到 GitHub，所以不用担心敏感信息泄露！

---

### 第2步：用 Render 免费部署（推荐）
1. 访问 https://render.com
2. 用 GitHub 账号登录
3. 点击 "New +" → "Web Service"
4. 选择你刚上传的 GitHub 仓库
5. 配置页面：
   - **Name**: d404-duty（或其他你喜欢的名字
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - 其他选项保持默认
6. 点击 "Create Web Service"
7. 等待 2-5 分钟，部署完成！
8. 你会得到一个类似 `https://d404-duty.onrender.com` 的链接！

---

### 第3步：配置免费数据库（重要！让线上修改永久保存）

Render 免费版的文件系统是临时的：服务 15 分钟没人访问就休眠，重启后
**后台改的密码、值日表全部丢失**（退回部署时的默认配置）。
解决办法：接入 Neon 免费 PostgreSQL 数据库，配置改存数据库，重启也不丢。

1. 访问 https://neon.com ，用 GitHub 账号注册（免费，无需信用卡）
2. 登录后点击 "Create project"（区域选 Singapore 离国内最近），随便起名如 `d404-duty`
3. 创建完成后，在连接信息里复制 **Connection string**，
   形如 `postgresql://user:password@ep-xxx.aws-region.neon.tech/neondb?sslmode=require`
4. 回到 Render 控制台：你的服务 → 左侧 "Environment" → "Add Environment Variable"：
   - **Key**: `DATABASE_URL`
   - **Value**: 刚才复制的连接串
5. 保存后 Render 会自动重新部署
6. 验证：登录后台改一次密码 → Render 控制台手动 "Restart" 服务 → 再登录，密码仍是新的 ✅

> 连接串包含数据库密码，只填在 Render 环境变量里，**不要**写进代码或提交到 GitHub。
> 不配置 DATABASE_URL 也能跑，但修改会随服务重启丢失（仅本地模式不需要配置）。

---

### 第4步：初始化配置
1. 访问你的 Render 链接
2. 登录管理后台：`https://你的链接/admin`
3. 默认密码：`d404admin`
4. 立即修改密码！
5. 根据需要配置值日信息

---

### 可选：用 Railway 部署（也免费）
1. 访问 https://railway.app
2. 用 GitHub 登录
3. New Project → Deploy from repo
4. 选你的仓库
5. 配置 Start Command: `python app.py`
6. 部署完成

---

## 💡 云部署注意事项

### ✅ 数据持久化
- **已支持**：配置 DATABASE_URL（见第3步）后，密码、值日表、备份、登录日志
  全部存 Neon 数据库，Render 重启 / 休眠唤醒 / 重新部署都不会丢
- **未配置 DATABASE_URL 时**：Render/Railway 重启后 data/config.json 会重置，
  后台修改仅当次有效（本地运行不受影响）

### 🔒 安全
- 部署后立即修改默认密码！
- data/config.json 含密码与密钥，已在 .gitignore 且已退出 git 跟踪，不会上传 GitHub

---

## 🖥️ 本地运行

如果你还是想在本地运行：

### Windows：
1. 双击 `simple-start.bat`
2. 浏览器打开 http://127.0.0.1:8848

### 其他系统：
1. 创建虚拟环境
2. pip install -r requirements.txt
3. python app.py

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| app.py | Flask 主程序 |
| duty_core.py | 值日核心逻辑 |
| requirements.txt | 依赖包 |
| simple-start.bat | 本地启动脚本 |
| data/config.json | 配置文件（不上传 GitHub） |
| data/config.json.example | 配置文件示例（上传 GitHub） |

---

## 🎉 完成！

现在你有一个 24小时运行的值日助手了！
