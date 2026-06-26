from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


INPUT_FILE = Path("cnpc_daily_close.json")
OUTPUT_FILE = Path("cnpc_daily_report.md")
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
COST_BASIS = 11.20
REQUIRED_FIELDS = ("open", "close", "high", "low", "volume")


def shanghai_now() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def load_quote() -> dict[str, Any]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"{INPUT_FILE} does not exist")

    quote = json.loads(INPUT_FILE.read_text(encoding="utf-8-sig"))
    if quote.get("code") != "601857.SH":
        raise ValueError(f"Unexpected code: {quote.get('code')!r}")
    if quote.get("status") not in {"ok", "fallback_previous_close"}:
        raise ValueError(f"Unsupported status: {quote.get('status')!r}")

    missing = [
        field
        for field in ("stock", "code", "date", "source", "status", "fetched_at", *REQUIRED_FIELDS)
        if quote.get(field) in (None, "")
    ]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    for field in REQUIRED_FIELDS:
        try:
            float(quote[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Field {field} is not numeric: {quote[field]!r}") from exc

    return quote


def fmt_num(value: Any, digits: int = 2) -> str:
    return f"{float(value):.{digits}f}"


def fmt_volume(value: Any) -> str:
    volume = float(value)
    if volume >= 100_000_000:
        return f"{volume / 100_000_000:.2f} 亿"
    if volume >= 10_000:
        return f"{volume / 10_000:.2f} 万"
    return f"{volume:.0f}"


def freshness_text(quote: dict[str, Any]) -> str:
    if quote["status"] == "ok":
        return "最新脚本抓取交易日收盘数据"
    return "脚本抓取失败，使用上一条可用收盘数据；不要视为当日新鲜价格"


def conclusion(quote: dict[str, Any]) -> str:
    close = float(quote["close"])
    open_price = float(quote["open"])
    high = float(quote["high"])
    low = float(quote["low"])

    intraday = "收平"
    if close > open_price:
        intraday = "收高"
    elif close < open_price:
        intraday = "收低"

    range_text = f"日内区间 {fmt_num(low)}-{fmt_num(high)} 元"
    if quote["status"] == "fallback_previous_close":
        return f"今日数据为备用上一收盘价，不能代表最新交易日走势；参考价 {fmt_num(close)} 元，{range_text}。"

    return f"中国石油A股报收 {fmt_num(close)} 元，较开盘价{intraday}，{range_text}。短线先按震荡处理，避免因单日波动放大仓位。"


def position_note(quote: dict[str, Any]) -> str:
    close = float(quote["close"])
    gap = (close - COST_BASIS) / COST_BASIS * 100
    if gap >= 0:
        cost_line = f"现价高于 11.20 元成本约 {gap:.2f}%。"
    else:
        cost_line = f"现价低于 11.20 元成本约 {abs(gap):.2f}%。"

    if quote["status"] == "fallback_previous_close":
        prefix = "由于本次为 fallback_previous_close，先不要用这份价格做加仓或减仓触发。"
    else:
        prefix = cost_line

    return (
        f"{prefix} 对此前仓位较集中的持仓，建议继续控制单一股票暴露，短线不追涨、不因亏损机械补仓；"
        "中期以分批降集中度、保留现金弹性和重新评估油价/政策/分红预期为主。本报告不保证收益。"
    )


def render_report(quote: dict[str, Any]) -> str:
    report_date = shanghai_now().isoformat(timespec="seconds")
    error_line = ""
    if quote["status"] == "fallback_previous_close":
        error_line = f"\n- Error: {quote.get('error', '未提供')}"

    return f"""# PetroChina A-share Daily Closing Report

- Report date: {report_date}
- JSON quote date: {quote["date"]}
- Stock/code: {quote["stock"]} / {quote["code"]}
- Open: {fmt_num(quote["open"])} CNY
- Close: {fmt_num(quote["close"])} CNY
- High: {fmt_num(quote["high"])} CNY
- Low: {fmt_num(quote["low"])} CNY
- Volume: {fmt_volume(quote["volume"])}
- Source: {quote["source"]}
- Status/freshness: {quote["status"]} - {freshness_text(quote)}
- fetched_at: {quote["fetched_at"]}{error_line}

## 简短结论

{conclusion(quote)}

## 成本 11.20 元持仓提示

{position_note(quote)}
"""


def main() -> int:
    quote = load_quote()
    OUTPUT_FILE.write_text(render_report(quote), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
