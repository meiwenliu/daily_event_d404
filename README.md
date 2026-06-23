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

### 第3步：初始化配置
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

### ⚠️ 数据持久化
- 免费平台（Render/Railway 重启后，data/config.json 会重置为默认值
- 解决办法：
  1. 配置好后，在后台导出 config.json，保存到本地
  2. 万一重置了就重新导入一下

### 🔒 安全
- 部署后立即修改默认密码！
- data/config.json 不会上传到 GitHub（已在 .gitignore

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
