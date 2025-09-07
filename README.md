简体中文 | English

# eHi 价格监控

> 监控一嗨租车指定车型价格变化，并在变化或达到阈值时邮件通知。

[English version](README.en.md)

# 快速开始（Docker 推荐）

- 复制配置：`cp .env.example .env` 并按需填写。
- 构建并后台运行：
  - `cd ehi_price_monitor && docker compose up -d --build`
- 查看日志：`docker compose logs -f ehi-monitor` 或 `docker logs -f ehi-price-monitor`
- 单次测试邮件：`docker compose run --rm ehi-monitor python run.py --once`

- 容器会把 `./logs`、`./data`、`./debug` 挂载到宿主机，数据与截图会持久化。

# 本地运行（可选）

- 建议在 macOS/新 Linux 使用；旧 Linux（如 CentOS 7）优先用 Docker。
  - Python 3.10+ 虚拟环境
  - 安装依赖：`pip install -r requirements.txt`
  - 安装浏览器：`python -m playwright install chromium`
  - 运行：`python run.py` 或 `python run.py --once`

# 配置项（.env）

- 基本：`PICKUP_CITY`、`RETURN_CITY`、`PICKUP_DATE`、`RETURN_DATE`、`EH_CAR_NAME`、`CHECK_INTERVAL_SECONDS`
- 邮件：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`SMTP_FROM`、`EMAIL_TO`
- 可选：`ALERT_PRICE`（仅当当前价格 ≤ 阈值时发通知）
- 示例见 `ehi_price_monitor/.env.example`

# 工作原理

- 打开固定页面 `https://booking.1hai.cn/order/firstStep`，按 `.env` 自动填表并点击“查询”。
- 在结果中查找包含车型文本（默认“大众新探影”）的卡片，解析价格。
- 把最新价格与 `data/last_price.json` 对比，变化则发送邮件，并写入 `logs/price_observations.jsonl`，日志写入 `logs/monitor.log`。

# 运行与维护

- 重启：`docker compose restart ehi-monitor`
- 进入容器：`docker compose exec ehi-monitor bash`
- 停止：`docker compose stop ehi-monitor`；移除：`docker compose down`
- 修改 `.env` 后通常只需 `restart`；依赖或代码大改再 `--build`

# 常见问题

- 服务器报 `GLIBC_2.27/GLIBCXX_3.4.21 not found`：系统库过旧，使用本项目 Docker 镜像即可。
- 邮件发不出：确认 `SMTP_USER/SMTP_PASS` 为授权码且与 `SMTP_FROM` 匹配；尝试端口 465/587；开启服务商 SMTP。
- 页面解析失败：调整 `EH_CAR_NAME` 或在 `src/fetcher.py` 中微调选择器。

你可能需要提供

- 车型名称（`EH_CAR_NAME`，默认“大众新探影”）。
- 邮件配置：SMTP 主机、端口、用户名、授权码/密码、发件人、收件人邮箱。
- 行程条件：取/还车城市、日期（时间沿用页面默认）。

# 服务器兼容性（glibc 问题）

- 旧版 CentOS/RHEL 可能出现 `GLIBC_2.27`/`GLIBCXX_3.4.21 not found`，这是系统库过旧所致。
- 本仓库提供的 Docker 方案已内置兼容依赖，优先使用 Docker 部署即可规避该问题。
