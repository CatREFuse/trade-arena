from fastapi import HTTPException


class TradeError(HTTPException):
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 422,
        detail: dict | None = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={"error": error_code, "message": message, "detail": detail},
        )


class InsufficientFunds(TradeError):
    def __init__(self, available: float, requested: float):
        super().__init__(
            "INSUFFICIENT_FUNDS",
            f"余额不足，可用 {available:.2f}，请求 {requested:.2f}",
        )


class InvalidTradeAmount(TradeError):
    def __init__(self):
        super().__init__("INVALID_TRADE_AMOUNT", "买入金额必须大于 0")


class InvalidTradeShares(TradeError):
    def __init__(self):
        super().__init__("INVALID_TRADE_SHARES", "卖出数量必须大于 0")


class PositionLimitExceeded(TradeError):
    def __init__(self):
        super().__init__("POSITION_LIMIT_EXCEEDED", "超过单股仓位上限 30%")


class MarketClosed(TradeError):
    def __init__(
        self,
        *,
        market: str,
        now_local: str | None = None,
        next_open_at: str | None = None,
    ):
        super().__init__(
            "MARKET_CLOSED",
            "当前非交易时段",
            status_code=400,
            detail={
                "market": market,
                "now_local": now_local,
                "next_open_at": next_open_at,
            },
        )


class InsufficientShares(TradeError):
    def __init__(self):
        super().__init__("INSUFFICIENT_SHARES", "持仓不足，禁止卖空")


class DuplicateTrade(TradeError):
    def __init__(self):
        super().__init__(
            "DUPLICATE_TRADE", "重复交易（idempotency_key 已存在）", status_code=409
        )
