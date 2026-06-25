from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo


API_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
OUTPUT_FILE = Path("cnpc_daily_close.json")
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def shanghai_now_iso() -> str:
    return datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")


def fetch_latest_kline() -> dict[str, Any]:
    try:
        import requests
    except ModuleNotFoundError:
        from pip._vendor import requests

    response = requests.get(
        API_URL,
        params={
            "secid": "1.601857",
            "klt": "101",
            "fqt": "0",
            "lmt": "5",
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    klines = ((payload.get("data") or {}).get("klines") or [])
    if not klines:
        raise RuntimeError("Eastmoney response contained no data.klines rows")

    fields = str(klines[-1]).split(",")
    if len(fields) < 6:
        raise RuntimeError(f"Unexpected kline field count: {len(fields)}")

    date, open_price, close, high, low, volume = fields[:6]
    return {
        "stock": "中国石油",
        "code": "601857.SH",
        "date": date,
        "open": float(open_price),
        "close": float(close),
        "high": float(high),
        "low": float(low),
        "volume": float(volume),
        "fetched_at": shanghai_now_iso(),
        "source": "eastmoney_push2his_kline",
        "status": "ok",
    }


def write_json(data: dict[str, Any]) -> None:
    OUTPUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_previous() -> dict[str, Any] | None:
    if not OUTPUT_FILE.exists():
        return None
    try:
        return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Existing {OUTPUT_FILE} is invalid JSON: {exc}") from exc


def main() -> int:
    try:
        write_json(fetch_latest_kline())
        return 0
    except Exception as exc:
        previous = load_previous()
        if previous is None:
            raise

        previous["status"] = "fallback_previous_close"
        previous["error"] = str(exc)
        write_json(previous)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
