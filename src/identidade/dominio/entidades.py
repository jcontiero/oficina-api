from dataclasses import dataclass
from uuid import UUID
from enum import Enum


class ActorType(str, Enum):
    FUNCIONARIO = "FUNCIONARIO"
    CLIENTE = "CLIENTE"
    SISTEMA = "SISTEMA"


@dataclass
class Principal:
    id: UUID
    actor_type: ActorType
    perfil: str | None = None


class PerfilUsuario(str, Enum):
    ADMIN = "ADMIN"
    MECANICO = "MECANICO"


@dataclass
class Usuario:
    id: UUID
    email: str
    senha_hash: str
    perfil: PerfilUsuario
