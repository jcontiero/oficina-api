from uuid import UUID

import jwt

from src.config import Configuracoes
from src.identidade.aplicacao.ports import ProvedorToken
from src.identidade.dominio.entidades import ActorType, Principal


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
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise ValueError("Algoritmo inesperado; apenas RS256 é permitido")
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.config.jwt_audience,
                issuer=self.config.jwt_client_issuer,
                options={"require": ["sub", "exp", "iat", "iss", "aud", "actor_type"]},
            )

            actor = payload.get("actor_type")
            if not actor or actor != ActorType.CLIENTE.value:
                raise ValueError("Token não possui actor_type=CLIENTE")

            return Principal(
                id=UUID(payload["sub"]), actor_type=ActorType.CLIENTE, perfil="CLIENTE"
            )
        except jwt.PyJWTError as e:
            raise jwt.PyJWTError(str(e))
