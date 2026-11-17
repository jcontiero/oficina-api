import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from src.atendimento.infraestrutura.repositorios import ClienteRepositorioImpl
from src.container import DBDep, get_autenticar_usuario
from src.identidade.aplicacao.casos_de_uso import AutenticarUsuario
from src.identidade.apresentacao.schemas import (
    LoginRequest,
    TokenResponse,
    UsuarioResponse,
)
from src.identidade.dominio.excecoes import CredenciaisInvalidasError

router = APIRouter(tags=["Autenticação"])


class LookupClienteInternoRequest(BaseModel):
    cpf: str


def _validar_google_oidc_token(authorization: str, config) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Header Authorization Bearer OIDC obrigatório"
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token OIDC vazio")

    claims: dict | None = None
    if config.internal_auth_test_tokens_json:
        test_tokens = json.loads(config.internal_auth_test_tokens_json)
        claims = test_tokens.get(token)

    if claims is None:
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token

            claims = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=config.internal_auth_audience,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=401, detail=f"Token OIDC interno inválido: {exc}"
            ) from exc

    iss = str(claims.get("iss", ""))
    if iss not in {"https://accounts.google.com", "accounts.google.com"}:
        raise HTTPException(status_code=401, detail="Issuer OIDC inválido")

    if claims.get("aud") != config.internal_auth_audience:
        raise HTTPException(status_code=403, detail="Audience OIDC não autorizada")

    allowed_raw = config.internal_auth_allowed_service_accounts
    allowed = {s.strip() for s in allowed_raw.split(",") if s.strip()}
    email = str(claims.get("email", ""))
    if not claims.get("email_verified", False) or (allowed and email not in allowed):
        raise HTTPException(
            status_code=403,
            detail="Service Account não autorizada para consulta interna",
        )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Nenhuma Service Account autorizada configurada",
        )
    return claims


@router.post("/auth/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    caso_de_uso: Annotated[AutenticarUsuario, Depends(get_autenticar_usuario)],
):
    try:
        resultado = caso_de_uso.executar(body.email, body.senha)
        usuario = resultado["usuario"]
        return TokenResponse(
            token=resultado["token"],
            usuario=UsuarioResponse(
                id=str(usuario.id),
                email=usuario.email,
                perfil=usuario.perfil.value,
            ),
        )
    except CredenciaisInvalidasError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/.well-known/admin-jwks.json")
def obter_admin_jwks(request: Request) -> dict:
    return request.app.state.container.token_provider.obter_jwks()


@router.post("/internal/clientes/autenticacao")
def autenticar_cliente_interno(
    body: LookupClienteInternoRequest,
    request: Request,
    db: DBDep,
    authorization: str = Header(default=""),
) -> dict:
    """
    Endpoint interno autenticado via Google OIDC ID Token para a Cloud Function
    de autenticação de clientes consultar o OS Service sem acesso direto ao SQL.
    """
    config = request.app.state.container.config
    _validar_google_oidc_token(authorization, config)

    cpf_limpo = re.sub(r"\D", "", body.cpf)
    cliente = ClienteRepositorioImpl(db).buscar_por_cpf(cpf_limpo)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    return {
        "id": str(cliente.id),
        "nome": cliente.nome,
        "cpf": cliente.cpf.valor if cliente.cpf else cpf_limpo,
        "email": cliente.email,
        "status": cliente.status.value,
    }
