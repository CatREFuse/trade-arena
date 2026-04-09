from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import get_current_account
from app.config import settings
from app.database import get_db
from app.main import app as fastapi_app
from app.models import Account, Agent, AgentEquityPoint, Position, Trade, Wallet


@dataclass(slots=True)
class SeededAccounts:
    agent_id: str
    us_account_id: str
    cn_account_id: str
    hk_account_id: str
    token: str


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.hash_store: dict[str, dict[str, int]] = {}
        self.set_calls: list[tuple[str, int, str]] = []

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value.encode("utf-8")
        self.set_calls.append((key, ttl, value))

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
            if key in self.hash_store:
                del self.hash_store[key]
                deleted += 1
        return deleted

    async def incr(self, key: str) -> int:
        current = self.store.get(key)
        value = int((current.decode("utf-8") if isinstance(current, bytes) else current) or 0) + 1
        self.store[key] = str(value).encode("utf-8")
        return value

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        bucket = self.hash_store.setdefault(key, {})
        bucket[field] = int(bucket.get(field, 0)) + int(amount)
        return bucket[field]

    async def hgetall(self, key: str) -> dict[bytes, bytes]:
        bucket = self.hash_store.get(key, {})
        return {
            str(field).encode("utf-8"): str(value).encode("utf-8")
            for field, value in bucket.items()
        }

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True

    async def ping(self) -> bool:
        return True

    async def publish(self, *_args, **_kwargs) -> int:
        return 0

    async def lpush(self, *_args, **_kwargs) -> int:
        return 0

    async def ltrim(self, *_args, **_kwargs) -> bool:
        return True


def _create_test_tables(sync_connection) -> None:
    for table in (
        Agent.__table__,
        Account.__table__,
        Wallet.__table__,
        Position.__table__,
        Trade.__table__,
        AgentEquityPoint.__table__,
    ):
        table.create(sync_connection, checkfirst=True)


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
async def db_session_factory(
    tmp_path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'trade_arena_test.db'}",
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(_create_test_tables)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield session_factory
    finally:
        await engine.dispose()


@pytest.fixture
async def seeded_accounts(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[SeededAccounts]:
    async with db_session_factory() as session:
        session.add(
            Agent(
                id="alpha",
                name="Alpha Trader",
                avatar="avatar",
                model="gpt-5.4",
                camp="open",
                style="test",
                framework="pytest",
            )
        )

        token = "shared-token-for-tests"
        total_cny = Decimal(str(settings.total_starting_capital_cny))
        wallet_cash = total_cny.quantize(Decimal("0.01"))
        session.add(
            Wallet(
                id="alpha-wallet",
                agent_id="alpha",
                currency="CNY",
                initial_cash=wallet_cash,
                cash=wallet_cash,
            )
        )
        us_account = Account(
            id="alpha-us",
            agent_id="alpha",
            market="us",
            currency="CNY",
            initial_cash=Decimal("0.00"),
            cash=wallet_cash,
            api_token=token,
        )
        cn_account = Account(
            id="alpha-cn",
            agent_id="alpha",
            market="cn",
            currency="CNY",
            initial_cash=Decimal("0.00"),
            cash=wallet_cash,
            api_token=token,
        )
        hk_account = Account(
            id="alpha-hk",
            agent_id="alpha",
            market="hk",
            currency="CNY",
            initial_cash=Decimal("0.00"),
            cash=wallet_cash,
            api_token=token,
        )
        session.add_all([us_account, cn_account, hk_account])
        session.add_all(
            [
                Position(
                    account_id="alpha-us",
                    ticker="AAPL",
                    shares=Decimal("2"),
                    avg_cost=Decimal("150.00"),
                ),
                Trade(
                    account_id="alpha-us",
                    ticker="AAPL",
                    action="buy",
                    shares=Decimal("2"),
                    price=Decimal("150.00"),
                    amount=Decimal("300.00"),
                    fee=Decimal("0.30"),
                    fx_pair="USD/CNY",
                    fx_rate=Decimal("7.20"),
                    amount_cny=Decimal("2160.00"),
                    fee_cny=Decimal("2.16"),
                    cash_after_cny=Decimal("997837.84"),
                    reasoning="seed us trade",
                    idempotency_key="seed-us-trade",
                ),
                Trade(
                    account_id="alpha-cn",
                    ticker="600519.SH",
                    action="buy",
                    shares=Decimal("3"),
                    price=Decimal("1600.00"),
                    amount=Decimal("4800.00"),
                    fee=Decimal("4.80"),
                    fx_pair="CNY/CNY",
                    fx_rate=Decimal("1"),
                    amount_cny=Decimal("4800.00"),
                    fee_cny=Decimal("4.80"),
                    cash_after_cny=Decimal("993033.04"),
                    reasoning="seed cn trade",
                    idempotency_key="seed-cn-trade",
                ),
            ]
        )

        await session.commit()

    yield SeededAccounts(
        agent_id="alpha",
        us_account_id="alpha-us",
        cn_account_id="alpha-cn",
        hk_account_id="alpha-hk",
        token=token,
    )


@pytest.fixture
async def app(
    db_session_factory: async_sessionmaker[AsyncSession],
    fake_redis: FakeRedis,
) -> AsyncIterator:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with db_session_factory() as session:
            yield session

    fastapi_app.state.redis = fake_redis
    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        fastapi_app.dependency_overrides.pop(get_current_account, None)


@pytest.fixture
async def client(app, seeded_accounts) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
