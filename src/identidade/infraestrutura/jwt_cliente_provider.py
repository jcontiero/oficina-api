import jwt
from uuid import UUID

from src.config import Configuracoes
from src.identidade.aplicacao.ports import ProvedorToken
from src.identidade.dominio.entidades import Principal, ActorType


class JwtTokenProviderCliente(ProvedorToken):
    def __init__(self, configuracoes: Configuracoes):
        self.config = configuracoes
        self.jwks_client = jwt.PyJWKClient(configuracoes.jwks_url)

    def criar(self, dados: dict, expiracao_horas: int | None = None) -> str:
        raise NotImplementedError(
            "API não emite token de cliente (isso é feito pela Function)"
        )

    def decodificar(self, token: str) -> Principal:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience="oficina-api",
                issuer=["oficina-auth-serverless", "oficina-serverless"],
            )

            actor = payload.get("actor_type")
            if not actor or actor != ActorType.CLIENTE.value:
                raise ValueError("Token não possui actor_type=CLIENTE")

            return Principal(
                id=UUID(payload["sub"]), actor_type=ActorType.CLIENTE, perfil="CLIENTE"
            )
        except jwt.PyJWTError as e:
            raise jwt.PyJWTError(str(e))
