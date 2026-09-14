from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import PyJWTError

from src.container import get_token_provider
from src.identidade.aplicacao.ports import ProvedorToken
from src.identidade.dominio.entidades import Principal

security = HTTPBearer()


def get_usuario_atual(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Principal:
    import jwt
    from fastapi import Request
    from src.container import get_token_provider, get_token_provider_cliente
    
    token = credentials.credentials
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        actor_type = unverified.get("actor_type")
        
        # Obter dependências do FastAPI container manualmente ou via Request.
        # Mas para simplificar, usaremos as funções get_ do container diretamente.
        
        container = request.app.state.container
        if actor_type == "CLIENTE":
            provider = container.token_provider_cliente
        else:
            provider = container.token_provider
            
        return provider.decodificar(token)
    except (jwt.PyJWTError, ValueError) as e:
        msg = str(e)
        if "actor_type" in msg:
            msg = "Token antigo detectado. Por favor, faça login novamente."
        else:
            msg = "Token inválido ou expirado"
        raise HTTPException(status_code=401, detail=msg)
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")


def require_admin(payload: dict = Depends(get_usuario_atual)) -> Principal:
    if payload.perfil != "ADMIN":
        raise HTTPException(status_code=403, detail="Acesso restrito ao perfil ADMIN")
    return payload


def require_mecanico(payload: dict = Depends(get_usuario_atual)) -> Principal:
    if payload.perfil not in ("ADMIN", "MECANICO"):
        raise HTTPException(
            status_code=403, detail="Acesso restrito ao perfil MECANICO ou ADMIN"
        )
    return payload
