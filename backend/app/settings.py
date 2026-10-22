from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    healops_db_url: str = "sqlite:///./data/healops.db"
    healops_api_token: str = ""
    healops_worker_token: str = ""
    healops_managed_containers: str = "healops-broken-app"
    healops_auto_restart: bool = False
    healops_auto_approve_names: str = ""
    healops_restart_limit: int = 2
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    @property
    def allowed_names(self) -> set[str]:
        return {n.strip() for n in self.healops_managed_containers.split(",") if n.strip()}

    @property
    def auto_approve_names(self) -> set[str]:
        return {n.strip() for n in self.healops_auto_approve_names.split(",") if n.strip()}


settings = Settings()
