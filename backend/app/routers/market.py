from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import IndexQuoteOut, MarketBoardItemOut, MarketOverviewOut, QuoteOut
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/quote/{ticker}", response_model=QuoteOut)
async def get_quote(ticker: str, request: Request):
    redis = request.app.state.redis
    svc = MarketDataService(redis)
    return await svc.get_quote(ticker.upper())


@router.get("/index/{symbol}", response_model=IndexQuoteOut)
async def get_index(symbol: str, market: str = "us", request: Request = None):
    """获取大盘指数行情

    - symbol: SPX/NDX/DJI (美股) 或 SH/SZ/CY (A股) 或 HSI/HSCEI (港股)
    - market: us | cn | hk
    """
    redis = request.app.state.redis
    svc = MarketDataService(redis)
    return await svc.get_index(symbol.upper(), market)


@router.get("/indices", response_model=list[IndexQuoteOut])
async def get_all_indices(request: Request, refresh: bool = False):
    """获取所有大盘指数"""
    redis = request.app.state.redis
    svc = MarketDataService(redis)
    return await svc.get_all_indices(refresh=refresh)


@router.get("/overview", response_model=MarketOverviewOut)
async def get_market_overview(request: Request, refresh: bool = False):
    """获取市场总览快照"""
    redis = request.app.state.redis
    svc = MarketDataService(redis)
    return await svc.get_market_overview(refresh=refresh)


@router.get("/board", response_model=list[MarketBoardItemOut])
async def get_market_board(market: str = "us", request: Request = None, refresh: bool = False):
    """获取市场看盘榜单"""
    redis = request.app.state.redis
    svc = MarketDataService(redis)
    return await svc.get_market_board(market.lower(), refresh=refresh)
