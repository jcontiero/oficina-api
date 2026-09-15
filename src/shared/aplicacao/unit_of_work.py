import abc


class UnitOfWork(abc.ABC):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.rollback()

    @abc.abstractmethod
    def commit(self):
        pass

    @abc.abstractmethod
    def rollback(self):
        pass


def transactional(func):
    import functools

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        uow = getattr(self, "uow", None)
        if uow is None:
            return func(self, *args, **kwargs)
        with uow:
            result = func(self, *args, **kwargs)
            uow.commit()
            return result

    return wrapper
