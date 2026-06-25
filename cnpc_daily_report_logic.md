# CNPC Daily Report Quote Source

The CNPC daily closing report must use the repository-local JSON file:

```text
cnpc_daily_close.json
```

Do not use Browser, Chrome extensions, Google Finance, Eastmoney web pages, or any webpage-login flow to obtain the PetroChina A-share price.

Expected JSON fields:

- `stock`
- `code`
- `date`
- `open`
- `close`
- `high`
- `low`
- `volume`
- `fetched_at`
- `source`
- `status`
- optional `error`

Use the JSON only when `code` is `601857.SH`.

If `status` is `ok`, treat the record as the latest script-fetched trading-day close.

If `status` is `fallback_previous_close`, clearly state that the script failed and the report is using the previous available close. Include `error` and do not present the price as fresh.

If `cnpc_daily_close.json` is missing, malformed, or lacks usable price fields, report that PetroChina close data is unavailable. Do not fabricate data or use webpage fallback.
