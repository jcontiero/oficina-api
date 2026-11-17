from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    database_url: str = "sqlite:///./test.db"
    secret_key: str = "default-secret-key-for-dev-and-tests-min-32-chars"
    algorithm: str = "RS256"

    admin_jwt_key_id: str = "oficina-admin-rsa-key-2026"
    admin_jwt_private_key_pem: str = ""
    allow_ephemeral_admin_jwt_key: bool = False
    jwt_audience: str = "oficina-backend-homolog"
    jwt_admin_issuer: str = "oficina-admin-homolog"
    jwt_client_issuer: str = "oficina-auth-homolog"
    jwks_url: str = "http://localhost/.well-known/jwks.json"

    internal_auth_audience: str = (
        "https://api.oficina.internal/internal/clientes/autenticacao"
    )
    internal_auth_allowed_service_accounts: str = ""
    internal_auth_test_tokens_json: str = ""
    enable_legacy_monolith_domains: bool = True

    token_expire_horas: int = 8
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_remetente: str = "noreply@oficina.com"
    email_admin: str = ""
