from datetime import datetime, timedelta, timezone
import jwt

from src.config import Configuracoes

from src.identidade.dominio.entidades import Principal, ActorType
from uuid import UUID
from src.identidade.aplicacao.ports import ProvedorToken


class JwtTokenProvider(ProvedorToken):
    def __init__(self, configuracoes: Configuracoes):
        self.config = configuracoes

    def criar(self, dados: dict, expiracao_horas: int | None = None) -> str:
        payload = dados.copy()
        horas = (
            expiracao_horas
            if expiracao_horas is not None
            else self.config.token_expire_horas
        )
        expiracao = datetime.now(timezone.utc) + timedelta(hours=horas)
        payload["exp"] = expiracao
        payload["iss"] = "oficina-api-admin"
        payload["aud"] = "oficina-api"
        payload["actor_type"] = ActorType.FUNCIONARIO.value
        
        return jwt.encode(
            payload, self.config.secret_key, algorithm=self.config.algorithm
        )

    def decodificar(self, token: str) -> Principal:
        try:
            payload = jwt.decode(
                token, 
                self.config.secret_key, 
                algorithms=[self.config.algorithm],
                audience="oficina-api",
                issuer="oficina-api-admin"
            )
            
            actor = payload.get("actor_type")
            if not actor or actor != ActorType.FUNCIONARIO.value:
                raise ValueError("Token não possui actor_type=FUNCIONARIO")
                
            return Principal(
                id=UUID(payload["sub"]),
                actor_type=ActorType.FUNCIONARIO,
                perfil=payload.get("perfil")
            )
        except jwt.PyJWTError as e:
            raise jwt.PyJWTError(str(e))
