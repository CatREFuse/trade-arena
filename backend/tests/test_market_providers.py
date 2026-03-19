from __future__ import annotations

from app.services.market_providers import YahooProvider


def test_parse_stooq_snapshot_csv_batch_uses_prev_close_and_name_map():
    text = (
        "AAPL.US,2026-03-18,21:00:19,252.625,254.94,249,249.94,35757874,APPLE INC,254.23\n"
        "BRK-B.US,2026-03-18,21:04:21,491.14,491.38,483.8,484.47,4356429,BERKSHIRE HATHAWAY INC,492.58\n"
    )

    quotes = YahooProvider._parse_stooq_snapshot_csv(
        text,
        {
            "aapl.us": "AAPL",
            "brk-b.us": "BRK.B",
        },
    )

    assert set(quotes) == {"AAPL", "BRK.B"}
    assert quotes["AAPL"].price == 249.94
    assert quotes["AAPL"].previous_close == 254.23
    assert quotes["AAPL"].change_pct == -1.69
    assert quotes["BRK.B"].name == "Berkshire Hathaway"
    assert quotes["BRK.B"].market_status == "closed"
