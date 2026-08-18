# D404 值日助手 - 部署检查清单

## 一、本地部署

- [ ] 双击 `install.bat` 安装依赖
- [ ] 双击 `start_local.bat` 启动本地服务
- [ ] 打开浏览器访问 http://127.0.0.1:8848
- [ ] 打开浏览器访问 http://127.0.0.1:8848/admin
- [ ] 使用默认密码 `d404admin` 登录后台
- [ ] **重要：登录后立即修改默认密码**
- [ ] 检查值日人员配置是否正确
- [ ] 检查节假日和课题组放假设置

## 二、局域网访问

- [ ] 运行 `check_network.bat`
- [ ] 查看本机 IPv4 地址
- [ ] 确认端口 8848 未被占用
- [ ] 手机连接与电脑同一 WiFi
- [ ] 手机浏览器访问局域网地址（http://本机IP:8848）
- [ ] 配置 Windows 防火墙允许 Python/Flask 访问网络

## 三、公网访问（cpolar）

- [ ] 下载并安装 cpolar（https://www.cpolar.com/）
- [ ] 注册 cpolar 账号并获取 authtoken
- [ ] 运行命令：`cpolar authtoken 你的token`
- [ ] 双击 `start_public_cpolar.bat`
- [ ] 在 cpolar 窗口中找到 "Forwarding" 行
- [ ] 复制以 https:// 开头的公网链接
- [ ] 登录后台，进入"部署"页面
- [ ] 粘贴公网链接到输入框
- [ ] 开启"公网访问模式"
- [ ] 保存设置
- [ ] 刷新首页，确认显示分享链接
- [ ] 手机关闭 WiFi，使用流量测试公网链接

## 四、开机自启

- [ ] 双击 `create_startup_shortcut.bat`
- [ ] 确认快捷方式创建成功
- [ ] 设置电脑电源计划为"从不"休眠/睡眠
- [ ] 重启电脑测试是否自动启动

## 五、云部署数据持久化（Render + Neon，必做）

> Render 免费版文件系统是临时的：服务休眠重启或重新部署后，
> 后台修改的密码 / 值日表会全部丢失。接入 Neon 免费数据库后永久保存。

- [ ] 注册 https://neon.com （GitHub 登录，免费）
- [ ] Create project（区域选 Singapore），复制 Connection string
- [ ] Render 控制台 → 服务 → Environment → 添加变量 `DATABASE_URL` = 连接串
- [ ] 保存后等待自动重新部署完成
- [ ] 登录后台修改一次密码
- [ ] Render 控制台手动 Restart 服务
- [ ] 重新打开网址，确认新密码仍能登录（= 持久化生效）
- [ ] 连接串不要写进代码 / 提交 GitHub（只放 Render 环境变量）

## 六、日常维护

- [ ] 定期备份 `data/config.json`
- [ ] 定期查看 `data/auth.log` 检查登录安全
- [ ] cpolar 免费版链接变化时，更新后台公网链接
