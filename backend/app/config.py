from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://arena:arena_dev@localhost:5432/trade_arena"
    )
    redis_url: str = "redis://localhost:6379/0"
    trade_fee_rate: float = 0.001
    max_position_ratio: float = 0.30
    exchange_rate: float = 7.2  # CNY to USD exchange rate
    total_starting_capital_cny: float = 1000000  # Total capital in CNY
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Trade Arena"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    email_verification_dev_mode: bool = True
    market_enable_mock_fallback: bool = False
    market_provider_failure_threshold: int = 3
    market_provider_cooldown_seconds: int = 60
    hosted_files_dir: str = "hosted-files"
    hosted_skill_filename: str = "cocoloop-trade-arena.zip"

    model_config = {"env_file": ".env"}


settings = Settings()
