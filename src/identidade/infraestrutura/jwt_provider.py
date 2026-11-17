import base64
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from src.config import Configuracoes
from src.identidade.aplicacao.ports import ProvedorToken
from src.identidade.dominio.entidades import ActorType, Principal


def _carregar_ou_gerar_chave_privada(pem: str):
    if pem:
        return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class JwtTokenProvider(ProvedorToken):
    """
    Emite e valida tokens RS256 para funcionários (ADMIN/MECANICO) com `kid`
    e publica a chave pública via `/.well-known/admin-jwks.json` para validação
    distribuída em oficina-billing e oficina-execucao.
    """

    def __init__(self, configuracoes: Configuracoes):
        self.config = configuracoes
        self.key_id = configuracoes.admin_jwt_key_id
        self.private_key = _carregar_ou_gerar_chave_privada(
            configuracoes.admin_jwt_private_key_pem
        )
        self.public_key = self.private_key.public_key()

    def obter_jwks(self) -> dict:
        public_numbers = self.public_key.public_numbers()

        def _int_to_base64(n: int) -> str:
            b = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big")
            return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self.key_id,
                    "n": _int_to_base64(public_numbers.n),
                    "e": _int_to_base64(public_numbers.e),
                }
            ]
        }

    def criar(self, dados: dict, expiracao_horas: int | None = None) -> str:
        payload = dados.copy()
        horas = (
            expiracao_horas
            if expiracao_horas is not None
            else self.config.token_expire_horas
        )
        agora = datetime.now(timezone.utc)
        payload["iat"] = int(agora.timestamp())
        payload["exp"] = int((agora + timedelta(hours=horas)).timestamp())
        payload["iss"] = self.config.jwt_admin_issuer
        payload["aud"] = self.config.jwt_audience
        payload["actor_type"] = ActorType.FUNCIONARIO.value

        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.key_id, "alg": "RS256", "typ": "JWT"},
        )

    def decodificar(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise ValueError("Algoritmo inesperado; apenas RS256 é permitido")
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience=self.config.jwt_audience,
                issuer=self.config.jwt_admin_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "actor_type"]},
            )

            actor = payload.get("actor_type")
            if not actor or actor != ActorType.FUNCIONARIO.value:
                raise ValueError("Token não possui actor_type=FUNCIONARIO")

            sub_val = payload.get("sub") or payload.get("os_id")
            return Principal(
                id=UUID(str(sub_val)),
                actor_type=ActorType.FUNCIONARIO,
                perfil=payload.get("perfil"),
            )
        except jwt.PyJWTError as e:
            raise jwt.PyJWTError(str(e))
