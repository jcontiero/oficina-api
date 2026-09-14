from src.shared.aplicacao.unit_of_work import UnitOfWork

class DummyUnitOfWork(UnitOfWork):
    def commit(self): pass
    def rollback(self): pass
