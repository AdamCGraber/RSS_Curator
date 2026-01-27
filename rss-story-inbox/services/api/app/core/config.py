from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    cluster_time_window_hours: int = 48

    default_audience: str = "Busy industry professionals"
    default_tone: str = "Neutral, practical, no hype."
    default_include_terms: str = ""
    default_exclude_terms: str = ""

    class Config:
        env_prefix = ""
        case_sensitive = False

settings = Settings()
