import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from .config import Settings, EHI_BASE_URL

def _send_email_with_fallback(settings: Settings, msg: EmailMessage) -> None:
    last_err: Exception | None = None
    # 尝试顺序：按配置端口 -> 465(SSL) -> 587(STARTTLS)
    attempts: list[tuple[str,int,str]] = []
    if settings.smtp_port == 465:
        attempts.append(("SSL", settings.smtp_port, settings.smtp_host))
        attempts.append(("STARTTLS", 587, settings.smtp_host))
    else:
        attempts.append(("STARTTLS", settings.smtp_port, settings.smtp_host))
        attempts.append(("SSL", 465, settings.smtp_host))

    context = ssl.create_default_context()
    for mode, port, host in attempts:
        try:
            if mode == "SSL":
                with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                    server.ehlo()
                    if settings.debug:
                        server.set_debuglevel(1)
                    server.login(settings.smtp_user, settings.smtp_pass)
                    server.send_message(msg)
                    return
            else:
                with smtplib.SMTP(host, port, timeout=20) as server:
                    server.ehlo()
                    if settings.debug:
                        server.set_debuglevel(1)
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(settings.smtp_user, settings.smtp_pass)
                    server.send_message(msg)
                    return
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err


def send_price_change_email(settings: Settings, old_price: Optional[float], new_price: float) -> None:
    subject = "一嗨租车价格变动通知"
    lines = []
    lines.append(f"车型：{settings.car_name}")
    lines.append(f"链接：{EHI_BASE_URL}")
    if old_price is None:
        lines.append(f"当前价格：{new_price}")
    else:
        delta = new_price - old_price
        sign = "+" if delta >= 0 else "-"
        lines.append(f"原价：{old_price}")
        lines.append(f"现价：{new_price}（{sign}{abs(delta)}）")

    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.email_to
    msg.set_content(body)

    _send_email_with_fallback(settings, msg)


def send_current_price_email(settings: Settings, price: float) -> None:
    subject = "一嗨租车价格测试通知"
    lines = [
        f"车型：{settings.car_name}",
        f"模式：firstStep 自动填表",
        f"链接：{EHI_BASE_URL}",
        f"当前价格：{price}",
    ]
    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.email_to
    msg.set_content(body)

    _send_email_with_fallback(settings, msg)
