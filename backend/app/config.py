"""应用配置：全部从环境变量 / .env 读取，禁止硬编码密钥。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    # 直接指定完整连接串则优先用它（如本地快速试跑用 SQLite：sqlite:///./used_books.db）
    database_url: str = ""
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "used_book_recycle"

    # VLM
    vlm_provider: str = "openai_compatible"  # openai_compatible | ollama
    vlm_base_url: str = ""
    vlm_api_key: str = ""
    vlm_model: str = "qwen-vl-plus"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5vl:3b"

    # 识别
    tesseract_cmd: str = ""
    isbn_metadata_url: str = ""

    # 业务
    review_confidence_threshold: float = 0.6
    default_base_recycle_rate: float = 0.35

    # 支付与出货
    payment_provider: str = "mock"   # mock | wechat
    dispense_mechanism: str = "simulated"  # simulated | vend_channel | rfid_door

    # 微信登录与小程序
    auth_provider: str = "mock"      # mock | wechat
    wechat_appid: str = ""
    wechat_secret: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
