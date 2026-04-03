from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import async_session
from app.models import AgentEquityPoint
from app.services.fx import FXService
from app.services.market_data import MarketDataService
from app.services.ranking import RankingService

logger = logging.getLogger(__name__)

_ADVISORY_LOCK_ID = 450021907


class EquitySamplerService:
    """Periodically samples each agent equity and stores 5-minute points."""

    def __init__(self, redis, market_svc: MarketDataService | None = None, fx_service: FXService | None = None) -> None:
        self.redis = redis
        self.market_svc = market_svc
        self.fx_service = fx_service
        self._task: asyncio.Task | None = None

    @staticmethod
    def _is_postgres() -> bool:
        return settings.database_url.startswith("postgresql")

    @staticmethod
    def _floor_to_five_minutes(ts: datetime) -> datetime:
        return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)

    @staticmethod
    def _seconds_until_next_tick(now: datetime) -> int:
        floored = EquitySamplerService._floor_to_five_minutes(now)
        next_tick = floored + timedelta(minutes=5)
        wait_seconds = int((next_tick - now).total_seconds())
        return max(wait_seconds, 1)

    async def start(self) -> None:
        if not self._is_postgres():
            logger.info("Equity sampler skipped: non-postgres database")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="equity-sampler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Equity sampler tick failed: %s", exc)

            wait_seconds = self._seconds_until_next_tick(datetime.utcnow())
            await asyncio.sleep(wait_seconds)

    async def run_once(self) -> None:
        point_time = self._floor_to_five_minutes(datetime.utcnow())

        async with async_session() as db:
            got_lock = await db.scalar(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": _ADVISORY_LOCK_ID},
            )
            if not got_lock:
                return

            try:
                ranking_svc = RankingService(
                    db,
                    self.redis,
                    market_svc=self.market_svc,
                    fx_service=self.fx_service,
                )
                leaderboard = await ranking_svc.get_leaderboard("overall")
                if not leaderboard.rankings:
                    await db.commit()
                    return

                rows: list[dict] = []
                for ranking in leaderboard.rankings:
                    us_asset = ranking.us_asset_cny or Decimal("0")
                    cn_asset = ranking.cn_asset_cny or Decimal("0")
                    hk_asset = ranking.hk_asset_cny or Decimal("0")
                    position_value = us_asset + cn_asset + hk_asset
                    equity = ranking.total_asset_cny
                    cash = equity - position_value
                    rows.append(
                        {
                            "agent_id": ranking.agent_id,
                            "point_time": point_time,
                            "equity_cny": equity,
                            "return_pct": Decimal(str(ranking.return_pct)),
                            "cash_cny": cash,
                            "position_value_cny": position_value,
                        }
                    )

                stmt = insert(AgentEquityPoint).values(rows)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_agent_equity_points_agent_time",
                    set_={
                        "equity_cny": stmt.excluded.equity_cny,
                        "return_pct": stmt.excluded.return_pct,
                        "cash_cny": stmt.excluded.cash_cny,
                        "position_value_cny": stmt.excluded.position_value_cny,
                    },
                )
                await db.execute(stmt)
                await db.commit()
            finally:
                await db.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": _ADVISORY_LOCK_ID},
                )
                await db.commit()
