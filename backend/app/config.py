from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://arena:arena_dev@localhost:5432/trade_arena"
    redis_url: str = "redis://localhost:6379/0"
    trade_fee_rate: float = 0.001
    max_position_ratio: float = 0.30

    model_config = {"env_file": ".env"}


settings = Settings()
