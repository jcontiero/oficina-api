from src.identidade.dominio.entidades import Principal
from abc import ABC, abstractmethod


class ProvedorToken(ABC):
    @abstractmethod
    def criar(self, dados: dict, expiracao_horas: int | None = None) -> str: ...

    @abstractmethod
    def decodificar(self, token: str) -> Principal: ...


class ProvedorHashSenha(ABC):
    @abstractmethod
    def hash(self, senha: str) -> str: ...

    @abstractmethod
    def verificar(self, senha: str, hash: str) -> bool: ...
