import json
import os
import time
import sys
import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from src.config import Settings, EHI_BASE_URL
from src.fetcher import get_current_price
from src.notifier import send_price_change_email, send_current_price_email


def load_last_price(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return float(data.get("price"))
    except Exception:
        return None


def save_last_price(path: Path, price: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"price": price, "timestamp": int(time.time())}, f, ensure_ascii=False)


def setup_logging(debug: bool) -> logging.Logger:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ehi_monitor")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if debug else logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    # File
    fh = logging.FileHandler(logs_dir / "monitor.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG if debug else logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    # Attach once
    if not logger.handlers:
        logger.addHandler(ch)
        logger.addHandler(fh)
    return logger


def append_price_observation(settings: Settings, price: float, last_price: float | None) -> None:
    # 以 JSONL 形式落盘，便于分析
    record = {
        "ts": int(time.time()),
        "car_name": settings.car_name,
        "mode": "form",
        "url": EHI_BASE_URL,
        "pickup": {
            "city": settings.pickup_city,
            "date": settings.pickup_date,
        },
        "return": {
            "city": settings.return_city,
            "date": settings.return_date,
        },
        "price": price,
        "last_price": last_price,
        "alert_price": settings.alert_price,
    }
    path = Path("logs/price_observations.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="eHi price monitor")
    parser.add_argument("--once", action="store_true", help="Run a single check and send a test email with current price")
    args = parser.parse_args()

    load_dotenv()
    settings = Settings.from_env()
    logger = setup_logging(settings.debug)

    data_file = Path("data/last_price.json")

    logger.info("eHi price monitor started.")
    logger.info(f"Target: {settings.car_name}")
    logger.info("Mode: firstStep form fill")
    logger.info(f"Base URL: {EHI_BASE_URL}")
    logger.info(f"Pickup: {settings.pickup_city} {settings.pickup_date}")
    logger.info(f"Return: {settings.return_city} {settings.return_date}")
    if settings.alert_price is not None:
        logger.info(f"Alert threshold: <= {settings.alert_price}")
    logger.info(f"Interval: {settings.check_interval_seconds}s")

    # One-shot test mode: fetch once and email regardless of change
    if args.once:
        try:
            price = get_current_price(settings)
            if price is None:
                logger.warning("Could not find price for the target car.")
                sys.exit(2)
            logger.info(f"Current price: {price}")
            append_price_observation(settings, price, last_price=None)
            # If alert threshold is set, only send when price <= threshold
            if (settings.alert_price is not None) and (price > settings.alert_price):
                logger.info(f"Skip email: price {price} exceeds alert threshold {settings.alert_price}.")
            else:
                try:
                    send_current_price_email(settings, price)
                    logger.info("Test email sent.")
                except Exception as e:
                    logger.error(f"Failed to send email: {e}")
                    sys.exit(3)
            sys.exit(0)
        except KeyboardInterrupt:
            print("Exiting on user request.")
            sys.exit(1)
        except Exception as e:
            print(f"Error during check: {e}")
            sys.exit(1)

    last_price = load_last_price(data_file)
    if last_price is not None:
        logger.info(f"Last known price: {last_price}")

    while True:
        try:
            price = get_current_price(settings)
            if price is None:
                logger.warning("Could not find price for the target car. Will retry later.")
            else:
                logger.info(f"Current price: {price}")
                append_price_observation(settings, price, last_price)
                # Only notify when price changed AND below/equal to alert threshold if set
                should_notify = True
                if settings.alert_price is not None and price > settings.alert_price:
                    should_notify = False
                    logger.info(f"Skip notify: price {price} exceeds alert threshold {settings.alert_price}.")
                if ((last_price is None) or (price != last_price)) and should_notify:
                    change = None if last_price is None else price - last_price
                    logger.info(f"Price change detected: {last_price} -> {price}")
                    try:
                        send_price_change_email(settings, old_price=last_price, new_price=price)
                        logger.info("Notification email sent.")
                    except Exception as e:
                        logger.error(f"Failed to send email: {e}")
                    save_last_price(data_file, price)
                    last_price = price
        except KeyboardInterrupt:
            logger.info("Exiting on user request.")
            break
        except Exception as e:
            logger.error(f"Error during check: {e}")

        time.sleep(settings.check_interval_seconds)


if __name__ == "__main__":
    main()
