# -*- coding: utf-8 -*-


class IpmtError(Exception):
    pass


class RepositoryError(IpmtError):
    pass


class OperationError(IpmtError):
    pass


class DbError(IpmtError):
    pass
