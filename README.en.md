English | 简体中文

# eHi Price Monitor

Monitors the price of a specific eHi booking and emails you when it changes or meets a threshold.

[中文文档](README.md)

# Quick Start (Docker recommended)

- Copy config: `cp .env.example .env` and fill values.
- Build and run in background:
  - `cd ehi_price_monitor && docker compose up -d --build`
- View logs: `docker compose logs -f ehi-monitor` or `docker logs -f ehi-price-monitor`
- One-off test email: `docker compose run --rm ehi-monitor python run.py --once`

- The container mounts `./logs`, `./data`, and `./debug` so state persists on host.

# Local Run (optional)

- Prefer on macOS/new Linux; for older Linux (e.g., CentOS 7) use Docker.
  - Python 3.10+ venv
  - Deps: `pip install -r requirements.txt`
  - Browsers: `python -m playwright install chromium`
  - Run: `python run.py` or `python run.py --once`

# Config (.env)

- Basic: `PICKUP_CITY`, `RETURN_CITY`, `PICKUP_DATE`, `RETURN_DATE`, `EH_CAR_NAME`, `CHECK_INTERVAL_SECONDS`
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `EMAIL_TO`
- Optional: `ALERT_PRICE` (notify only when current price ≤ threshold)
- See `ehi_price_monitor/.env.example` for examples

# How It Works

- Opens fixed page `https://booking.1hai.cn/order/firstStep`, fills the form from `.env`, clicks 查询.
- Finds the listing containing the configured car name and extracts the price.
- Compares with `data/last_price.json`; on change, sends email. Appends to `logs/price_observations.jsonl`, logs to `logs/monitor.log`.

# Operate & Maintain

- Restart: `docker compose restart ehi-monitor`
- Shell: `docker compose exec ehi-monitor bash`
- Stop: `docker compose stop ehi-monitor`; remove: `docker compose down`
- After `.env` edits, usually `restart` is enough; rebuild on code/deps changes.

# Compatibility (glibc)

- On older CentOS/RHEL you may see `GLIBC_2.27` / `GLIBCXX_3.4.21 not found` from Playwright.
- Use the provided Docker setup which includes compatible system libraries.

