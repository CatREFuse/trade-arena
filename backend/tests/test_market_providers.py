from __future__ import annotations

import pandas as pd

from app.services.market_providers import AkshareProvider, TencentProvider, YahooProvider


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


def test_tencent_parse_quote_payload_for_cn_stock():
    payload = (
        "1~贵州茅台~600519~1445.00~1452.87~1452.96~26132~12499~13633~1442.65~1"
        "~1441.05~1~1441.02~1~1441.00~7~1440.80~1~~20260320161407~-7.87~-0.54"
    )

    quote = TencentProvider._parse_quote_payload("600519.SH", payload)

    assert quote is not None
    assert quote.ticker == "600519.SH"
    assert quote.name == "贵州茅台"
    assert quote.price == 1445.0
    assert quote.previous_close == 1452.87
    assert quote.change_pct == -0.54
    assert quote.volume == 2613200


def test_tencent_parse_index_payload_for_cn_index():
    payload = "1~上证指数~000001~3957.05~-49.50~-1.24~666798387~96486311~~650089.54~ZS~"

    quote = TencentProvider._parse_index_payload("SH", "s_sh000001", payload)

    assert quote is not None
    assert quote.ticker == "SH"
    assert quote.name == "上证指数"
    assert quote.price == 3957.05
    assert quote.change_pct == -1.24


def test_akshare_parse_cn_quote_frame_from_em_schema():
    provider = AkshareProvider()
    frame = pd.DataFrame(
        [
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1445.0,
                "涨跌幅": -0.54,
                "昨收": 1452.87,
                "成交量": 2613200,
            }
        ]
    )

    quotes = provider._parse_cn_quote_frame(frame)
    quote = quotes.get("600519.SH")

    assert quote is not None
    assert quote.ticker == "600519.SH"
    assert quote.name == "贵州茅台"
    assert quote.price == 1445.0
    assert quote.previous_close == 1452.87
    assert quote.change_pct == -0.54


def test_akshare_parse_hk_index_frame_for_hsi():
    provider = AkshareProvider()
    frame = pd.DataFrame(
        [
            {
                "代码": "HSI",
                "名称": "恒生指数",
                "最新价": 20000.0,
                "涨跌幅": 1.2,
                "昨收": 19763.0,
            }
        ]
    )

    quotes = provider._parse_hk_index_frame(frame)
    quote = quotes.get("HSI")

    assert quote is not None
    assert quote.ticker == "HSI"
    assert quote.name == "恒生指数"
    assert quote.price == 20000.0
    assert quote.change_pct == 1.2
