eHi Price Monitor

Monitors the price of a specific eHi (一嗨租车) booking and emails you when it changes.

Quick start

- Create a Python 3.10+ virtualenv.
- Install dependencies: `pip install -r requirements.txt`.
- Install Playwright browser binaries: `python -m playwright install chromium`.
- Copy `.env.example` to `.env` and fill in values.
- Run: `python run.py`.

How it works

- Uses Playwright to open the firstStep page (fixed URL), fills the form by your `.env` settings, then finds the listing matching the configured car name and extracts its price.
- Compares to the last observed price stored locally in `data/last_price.json`.
- On change, sends an email via your SMTP settings.
- Appends each observation as a JSON line in `logs/price_observations.jsonl`, and writes human-readable logs to `logs/monitor.log`.

Configuration

- Fill these in `.env`:
  - `PICKUP_CITY`, `RETURN_CITY`
  - `PICKUP_DATE`, `RETURN_DATE`
  - `EH_CAR_NAME`, `CHECK_INTERVAL_SECONDS`
  - SMTP: `SMTP_HOST`, `SMTP_PORT(=587 for 163)`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `EMAIL_TO`
  - Optional: `ALERT_PRICE` — only notify when price <= this value
  The script opens the fixed firstStep page `https://booking.1hai.cn/order/firstStep`, fills the form, clicks 查询, then parses results.

2) Email settings

- Use an SMTP account (e.g., Gmail with App Password, QQ Mail, 163 Mail, etc.).
- Fill `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, and `EMAIL_TO` in `.env`.

   Examples:
   - QQ 邮箱: `SMTP_HOST=smtp.qq.com`, `SMTP_PORT=587`（需开启 SMTP 并使用授权码）
   - 163 邮箱: `SMTP_HOST=smtp.163.com`, `SMTP_PORT=465/587`

3) Other settings

- `CHECK_INTERVAL_SECONDS` controls how often to check (default 600 = 10 minutes).
- `EH_CAR_NAME` is matched as plain text to find the listing block.
- Timezone is fixed to `Asia/Shanghai` in code.
- `ALERT_PRICE` (optional): only sends email when current price is less than or equal to this value. Leave empty to notify on any price change.

Run as a background job

- You can use `nohup` on macOS/Linux:
  - `nohup python run.py > monitor.log 2>&1 &`
- Or add a cron entry (checks every 10 minutes):
  - `*/10 * * * * cd /path/to/project && /path/to/venv/bin/python run.py >> monitor.log 2>&1`

Mac launchd (optional)

- Create a plist at `~/Library/LaunchAgents/com.ehi.monitor.plist` and point `ProgramArguments` to your venv’s python and `run.py`. Load with `launchctl load ~/Library/LaunchAgents/com.ehi.monitor.plist`.

Notes

- Sites change HTML occasionally. If parsing fails, tweak `EH_CAR_NAME` or update selectors in `src/fetcher.py`.
- On firstStep, store selection is no longer handled; the page's default stores are used.
  - Dates are set by clicking each date input and choosing the day from the calendar; times are set via their respective dropdowns.
- If the site requires login or captchas, prefer using a direct results URL (`EH_SEARCH_URL`) that works in a private browser window.
- For near real-time checks, lower `CHECK_INTERVAL_SECONDS` responsibly to avoid rate-limiting.

What you need to provide

- EH search URL: A full results page URL for the exact itinerary (Dunhuang pickup, Delingha dropoff, 2025-10-04 09:00 to 2025-10-08 18:00), with the target car visible; OR the firstStep form details below.
- Car name text: The listing label shown on the page for the car (defaults to 大众新探影).
- Email settings: SMTP host, port, username, app password, from, recipient.
- Optional: Check interval seconds and timezone if you want to change defaults.
- If using firstStep form mode: just pickup/return cities and date + time; stores use the page defaults.

中文说明

项目简介

- 作用：监控一嗨租车指定行程（敦煌取、德令哈还，2025-10-04 09:00 → 2025-10-08 18:00）中“大众新探影”的价格；价格变化时发送邮件提醒。

快速开始

- 准备 Python 3.10+ 虚拟环境。
- 安装依赖：`pip install -r requirements.txt`。
- 安装 Playwright 浏览器：`python -m playwright install chromium`。
- 复制 `.env.example` 为 `.env` 并填写参数。
- 运行：`python run.py`。

工作原理

- 固定使用 firstStep 页面：打开 `https://booking.1hai.cn/order/firstStep`，按 `.env` 中的城市与日期自动填表并点击“查询”。
- 在结果列表中找到包含车型名（`EH_CAR_NAME`，默认“大众新探影”）的卡片，提取价格。
- 将价格与本地 `data/last_price.json` 中上次记录对比，若有变化则通过 SMTP 发送邮件通知，并更新记录。同时，将每次价格写入 `logs/price_observations.jsonl` 并记录到 `logs/monitor.log`。

配置信息

1) 获取稳定的一嗨搜索链接（`EH_SEARCH_URL`）

- 打开 https://www.1hai.cn/。
- 设置行程条件：
  - 取车：敦煌
  - 还车：德令哈
  - 时间：2024-10-04 09:00 → 2024-10-08 18:00
- 确认结果页面包含目标车型“大众新探影”。
- 复制浏览器地址栏完整 URL，粘贴到 `.env` 的 `EH_SEARCH_URL`。
- 提示：使用隐私/无痕窗口，确保链接在无登录状态下也能打开。

使用 firstStep 页面自动填表

- 设置 `.env`：
  - `PICKUP_CITY`、`RETURN_CITY`
  - `PICKUP_DATE`（例如：2025-10-04）、`RETURN_DATE`（例如：2025-10-08）
  脚本会分别点击“取车日期”“还车日期”选择日历中的日期；时间沿用页面默认；门店保持页面默认。

2) 邮件设置

- 准备一个可用的 SMTP 账号（例如 QQ 邮箱、163 邮箱、Gmail 应用专用密码等）。
- 在 `.env` 填写：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`SMTP_FROM`、`EMAIL_TO`。
- 示例：
  - QQ 邮箱：`SMTP_HOST=smtp.qq.com`，`SMTP_PORT=587`（需开启 SMTP 并使用授权码）。
  - 163 邮箱：`SMTP_HOST=smtp.163.com`，`SMTP_PORT=465/587`。

3) 其他设置

- `CHECK_INTERVAL_SECONDS`：检查间隔秒数，默认 600（10 分钟）。
- `EH_CAR_NAME`：车型匹配文本，如页面文案不同可调整。
- `TZ`：浏览器时区，默认 `Asia/Shanghai`。
- `ALERT_PRICE`（可选）：仅当当前价格小于等于该值时才发送邮件；留空表示任意价格变动都通知。

后台运行

- 使用 nohup：
  - `nohup python run.py > monitor.log 2>&1 &`
- 使用 cron（每 10 分钟）：
  - `*/10 * * * * cd /path/to/project && /path/to/venv/bin/python run.py >> monitor.log 2>&1`
- macOS 可选 launchd：在 `~/Library/LaunchAgents/com.ehi.monitor.plist` 配置并加载。

注意事项

- 站点页面结构可能变更；如解析失败，请修改 `EH_CAR_NAME` 或在 `src/fetcher.py` 中调整解析逻辑。
- 门店沿用页面默认，不再自动选择。
 - 时间设置：统一沿用页面默认（脚本不再选择时间）。
- 如需更高频率监控，可降低 `CHECK_INTERVAL_SECONDS`，但需留意站点的访问限制。
- 若该链接需要登录或验证，请先在无痕窗口确认可直接访问；必要时可扩展脚本以支持登录 Cookie。

邮件发送（故障排查）

- 已添加 `EHLO + STARTTLS + EHLO` 流程（端口 587），端口 465 使用 SSL 直连。
- 常见问题：
  - 认证失败：确认 `SMTP_USER`/`SMTP_PASS` 为授权码，且 `SMTP_FROM` 与账号匹配。
  - 被服务商拦截：尝试改用 465/587 或换邮箱服务商，或降低发送频率。

需要提供的信息（清单）

- 一嗨搜索结果链接（EH_SEARCH_URL）：包含目标车型且对应你的行程时间和地点；或提供 firstStep 自动填表信息（见下）。
- 车型名称（EH_CAR_NAME）：页面显示的车型文本（默认“大众新探影”）。
- 邮件发送配置：SMTP 主机、端口、用户名、授权码/密码、发件人、收件人邮箱。
- 可选：检查间隔（CHECK_INTERVAL_SECONDS）和时区（TZ）。
- 仅需取/还车城市、日期；门店沿用页面默认。
