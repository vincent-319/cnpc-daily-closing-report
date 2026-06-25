from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


EASTMONEY_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/601857.SS"
OUTPUT_FILE = Path("cnpc_daily_close.json")
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def requests_module():
    try:
        import requests
    except ModuleNotFoundError:
        from pip._vendor import requests

    return requests


def shanghai_now_iso() -> str:
    return datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")


def quote_payload(
    *,
    date: str,
    open_price: float,
    close: float,
    high: float,
    low: float,
    volume: float,
    source: str,
) -> dict[str, Any]:
    return {
        "stock": "\u4e2d\u56fd\u77f3\u6cb9",
        "code": "601857.SH",
        "date": date,
        "open": float(open_price),
        "close": float(close),
        "high": float(high),
        "low": float(low),
        "volume": float(volume),
        "fetched_at": shanghai_now_iso(),
        "source": source,
        "status": "ok",
    }


def eastmoney_session():
    requests = requests_module()
    session = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
    except ModuleNotFoundError:
        from pip._vendor.requests.adapters import HTTPAdapter
        from pip._vendor.urllib3.util.retry import Retry

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_eastmoney_kline() -> dict[str, Any]:
    response = eastmoney_session().get(
        EASTMONEY_URL,
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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close",
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    klines = ((payload.get("data") or {}).get("klines") or [])
    if not klines:
        raise RuntimeError("Eastmoney response contained no data.klines rows")

    fields = str(klines[-1]).split(",")
    if len(fields) < 6:
        raise RuntimeError(f"Unexpected Eastmoney kline field count: {len(fields)}")

    date, open_price, close, high, low, volume = fields[:6]
    return quote_payload(
        date=date,
        open_price=float(open_price),
        close=float(close),
        high=float(high),
        low=float(low),
        volume=float(volume),
        source="eastmoney_push2his_kline",
    )


def fetch_yahoo_chart() -> dict[str, Any]:
    requests = requests_module()
    response = requests.get(
        YAHOO_URL,
        params={"range": "10d", "interval": "1d"},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close",
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    result = (((payload.get("chart") or {}).get("result") or [None])[0]) or {}
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [None])[0]) or {}

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    for idx in range(len(closes) - 1, -1, -1):
        close = closes[idx]
        if close is None:
            continue
        try:
            timestamp = timestamps[idx]
            open_price = opens[idx]
            high = highs[idx]
            low = lows[idx]
            volume = volumes[idx]
        except IndexError as exc:
            raise RuntimeError("Yahoo chart arrays had inconsistent lengths") from exc
        if None in (timestamp, open_price, high, low, volume):
            continue

        date = datetime.fromtimestamp(int(timestamp), SHANGHAI_TZ).date().isoformat()
        return quote_payload(
            date=date,
            open_price=float(open_price),
            close=float(close),
            high=float(high),
            low=float(low),
            volume=float(volume),
            source="yahoo_chart",
        )

    raise RuntimeError("Yahoo chart response contained no non-null close values")


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


def fetch_latest_close() -> dict[str, Any]:
    errors: list[str] = []
    for source_name, fetcher in (
        ("Eastmoney", fetch_eastmoney_kline),
        ("Yahoo", fetch_yahoo_chart),
    ):
        try:
            return fetcher()
        except Exception as exc:
            message = f"{source_name} fetch failed: {exc}"
            print(f"WARNING: {message}", file=sys.stderr)
            errors.append(message)

    raise RuntimeError("; ".join(errors))


def main() -> int:
    try:
        write_json(fetch_latest_close())
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
