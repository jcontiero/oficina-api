from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./test.db"
    secret_key: str = "default-secret-key-for-dev-and-tests-min-32-chars"
    algorithm: str = "HS256"
    jwks_url: str = "http://localhost/.well-known/jwks.json"

    token_expire_horas: int = 8
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_remetente: str = "noreply@oficina.com"
    email_admin: str = ""
