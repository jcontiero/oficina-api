from sqlalchemy.orm import Session
from src.shared.aplicacao.unit_of_work import UnitOfWork


class SQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
