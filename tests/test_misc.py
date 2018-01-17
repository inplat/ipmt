# -*- coding: utf-8 -*-
"""
test_ipmt
----------------------------------
Tests for `ipmt` project.
"""
import getpass
from ipmt.misc import repr_str_multiline, parse_dsn


def test_repr_str_multiline():
    assert repr_str_multiline('qwe\nasd') == 'r"""\nqwe\nasd\n"""'


def test_parse_dsn():
    assert parse_dsn('user@localhost/dbname') == ['localhost', 5432, 'user',
                                                  None, 'dbname']
    assert parse_dsn('user:pw@localhost/dbname') == ['localhost', 5432, 'user',
                                                     'pw', 'dbname']
    assert parse_dsn('user:pw@localhost:8888/dbname') == ['localhost', 8888,
                                                          'user', 'pw',
                                                          'dbname']
    assert parse_dsn('localhost/db') == ['localhost', 5432, getpass.getuser(),
                                         None, 'db']
    assert parse_dsn('user:p%20w@localhost:8888/dbname') == ['localhost', 8888,
                                                             'user', 'p w',
                                                             'dbname']
