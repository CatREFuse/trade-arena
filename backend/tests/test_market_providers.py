from __future__ import annotations

import pandas as pd

from app.services.market_providers import (
    AkshareProvider,
    AlphaVantageProvider,
    FinnhubProvider,
    TencentProvider,
    TwelveDataProvider,
    YahooProvider,
)


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


def test_tencent_quote_symbol_supports_us_tickers():
    assert TencentProvider._to_quote_symbol("AAPL") == "usAAPL"
    assert TencentProvider._to_quote_symbol("brk.b") == "usBRK.B"
    assert TencentProvider._to_quote_symbol("0700.HK") == "hk00700"
    assert TencentProvider._to_quote_symbol("600519.SH") == "sh600519"


def test_tencent_parse_index_payload_for_us_index():
    payload = "200~标普500~.INX~6766.36~6616.85~6754.36~1357618895~0~0~~"
    quote = TencentProvider._parse_index_payload("SPX", "usINX", payload)

    assert quote is not None
    assert quote.ticker == "SPX"
    assert quote.name == "标普500"
    assert quote.price == 6766.36
    assert quote.previous_close == 6616.85
    assert quote.change_pct == 2.26


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


def test_twelvedata_parse_quote_payload_supports_single_and_batch():
    single_payload = {
        "symbol": "AAPL",
        "name": "Apple Inc",
        "close": "245.07",
        "previous_close": "246.74",
        "percent_change": "-0.6768",
        "volume": "2356072",
        "is_market_open": False,
    }
    single = TwelveDataProvider._parse_quote_payload(single_payload)
    assert set(single.keys()) == {"AAPL"}
    assert single["AAPL"] is not None
    assert single["AAPL"].price == 245.07
    assert single["AAPL"].previous_close == 246.74
    assert single["AAPL"].change_pct == -0.68
    assert single["AAPL"].market_status == "closed"

    batch_payload = {
        "AAPL": {
            "symbol": "AAPL",
            "name": "Apple Inc",
            "close": "245.07",
            "previous_close": "246.74",
            "percent_change": "-0.6768",
            "volume": "2356072",
            "is_market_open": False,
        },
        "BRK-B": {
            "symbol": "BRK-B",
            "name": "Berkshire Hathaway",
            "close": "484.47",
            "previous_close": "492.58",
            "percent_change": "-1.6463",
            "volume": "4356429",
            "is_market_open": True,
        },
    }
    batch = TwelveDataProvider._parse_quote_payload(batch_payload)
    assert set(batch.keys()) == {"AAPL", "BRK-B"}
    assert batch["BRK-B"] is not None
    assert batch["BRK-B"].price == 484.47
    assert batch["BRK-B"].change_pct == -1.65
    assert batch["BRK-B"].market_status == "open"


def test_alphavantage_parse_global_quote():
    payload = {
        "Global Quote": {
            "01. symbol": "IBM",
            "05. price": "245.0700",
            "06. volume": "2356072",
            "08. previous close": "246.7400",
            "10. change percent": "-0.6768%",
        }
    }

    quote = AlphaVantageProvider._parse_global_quote("IBM", payload)

    assert quote is not None
    assert quote.ticker == "IBM"
    assert quote.price == 245.07
    assert quote.previous_close == 246.74
    assert quote.change_pct == -0.68
    assert quote.volume == 2356072
    assert quote.market_status == "unknown"


def test_finnhub_parse_quote_payload():
    payload = {
        "c": 245.07,
        "d": -1.67,
        "dp": -0.6768,
        "h": 245.76,
        "l": 241.1,
        "o": 245.32,
        "pc": 246.74,
        "t": 1775606400,
    }

    quote = FinnhubProvider._parse_quote_payload("IBM", payload)

    assert quote is not None
    assert quote.ticker == "IBM"
    assert quote.price == 245.07
    assert quote.previous_close == 246.74
    assert quote.change_pct == -0.68
    assert quote.volume == 0
