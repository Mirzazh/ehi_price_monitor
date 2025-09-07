import os
from dataclasses import dataclass

# 固定站点与时区（不再通过环境变量配置）
EHI_BASE_URL = "https://booking.1hai.cn/order/firstStep"
EHI_TZ = "Asia/Shanghai"


@dataclass
class Settings:
    car_name: str
    check_interval_seconds: int

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    smtp_from: str
    email_to: str

    # Form mode fields
    pickup_city: str
    return_city: str
    pickup_date: str  # YYYY-MM-DD
    return_date: str  # YYYY-MM-DD

    # Debug/UX
    headful: bool
    debug: bool
    debug_dir: str

    # Alerts
    alert_price: float | None

    @staticmethod
    def from_env() -> "Settings":
        def req(name: str) -> str:
            v = os.getenv(name)
            if not v:
                raise ValueError(f"Missing required environment variable: {name}")
            return v

        return Settings(
            car_name=os.getenv("EH_CAR_NAME", "大众新探影"),
            check_interval_seconds=int(os.getenv("CHECK_INTERVAL_SECONDS", "600")),
            smtp_host=req("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),  # 163 默认 587 (STARTTLS)
            smtp_user=req("SMTP_USER"),
            smtp_pass=req("SMTP_PASS"),
            smtp_from=req("SMTP_FROM"),
            email_to=req("EMAIL_TO"),
            pickup_city=os.getenv("PICKUP_CITY", "敦煌"),
            return_city=os.getenv("RETURN_CITY", "德令哈"),
            pickup_date=os.getenv("PICKUP_DATE", "2025-10-04"),
            return_date=os.getenv("RETURN_DATE", "2025-10-08"),
            headful=os.getenv("HEADFUL", "0") in ("1", "true", "TRUE", "yes", "on"),
            debug=os.getenv("DEBUG", "0") in ("1", "true", "TRUE", "yes", "on"),
            debug_dir=os.getenv("DEBUG_DIR", "debug"),
            alert_price=(
                float(os.getenv("ALERT_PRICE", "").strip())
                if os.getenv("ALERT_PRICE", "").strip() not in ("", None)
                else None
            ),
        )
