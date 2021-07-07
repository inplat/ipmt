# -*- coding: utf-8 -*-
import os
import io
import shutil
import pytest
import ipmt.permissions
from ipmt.db import Database, REL_TABLE
from ipmt.error import OperationError

PERM_TEST_1 = """
roles:
  - user1
objects:
  test:
    user1: all
  test.t1:
    user1: select
  test.t1_b1:
    user1: select
exclude:
  - ~test.t_b\\d+
    """
PERM_TEST_1_QUERIES = """\
BEGIN ISOLATION LEVEL READ COMMITTED;
GRANT SELECT ON TABLE test.t1 TO user1;
GRANT USAGE,CREATE ON SCHEMA test TO user1;
COMMIT;\
"""


def v(n, b=None, bv=None):
    if b is not None:
        if bv is not None:
            return "%06d.%s.%d" % (n, b, bv)
        else:
            return "%06d.%s" % (n, b)
    if str(n) == "0":
        return "0"
    return "%06d" % n


def check_plan(plan, expected):
    return [(act.is_up, act.version.full_version) for act in plan] == expected


def test_full_postgres(postgres, repository, tmpdir):
    host, port, user, dbname, image, tag = postgres
    dsn = "%s@%s:%d/%s" % (user, host, port, dbname)
    db = Database(dsn)
    # VERSION 0
    assert repository.current(dsn) == v(0)
    assert repository.head(None) == v(0)
    filename = repository.create(
        "baseline", None, "CREATE SCHEMA test;", "DROP SCHEMA test;"
    )
    assert repository.head(None) == v(1)
    assert v(1) in filename
    assert check_plan(
        repository.up(v(1), dsn, True, False),
        [
            (True, v(1)),
        ],
    )
    assert repository.up(v(1), dsn, False, False) == v(1)
    # VERSION 1
    assert repository.current(dsn) == v(1)
    assert check_plan(
        repository.down(v(0), dsn, True, False),
        [
            (False, v(1)),
        ],
    )
    assert repository.down(None, dsn, False, False) == v(0)
    # VERSION 0
    filename = repository.create(
        "create_table", None, "CREATE TABLE test.t1();", "DROP TABLE test.t1;"
    )
    assert v(2) in filename
    filename = repository.create(
        "create_table2",
        "000001.b1",
        "CREATE TABLE test.t_b1(a int);",
        "DROP TABLE test.t_b1;",
    )
    assert repository.head(v(1, "b1")) == v(1, "b1", 1)
    repository.reload()
    assert v(1, "b1", 1) in filename
    assert repository.up(v(1, "b1", 1), dsn, False, False) == v(1, "b1", 1)
    # VERSION 1.b1.1
    assert db.search_objects("^test.t_.*", [REL_TABLE]) == ["test.t_b1"]
    assert db.search_objects("^test.t2_.*", [REL_TABLE]) == []
    assert repository.current(dsn) == v(1, "b1", 1)
    db.execute("INSERT INTO test.t_b1(a) VALUES(5);")
    assert db.query_scalar("SELECT a FROM test.t_b1") == 5
    repository.rebase(v(1, "b1"))
    assert repository.head(None) == v(3)
    with pytest.raises(OperationError):
        repository.switch(v(2), dsn, False, False)
    with pytest.raises(OperationError):
        repository.down(v(0), dsn, False, False)
    with pytest.raises(OperationError):
        repository.up(v(2), dsn, False, False)
    assert check_plan(
        repository.actualize(dsn, True, False),
        [(False, v(3)), (True, v(2)), (True, v(3))],
    )
    repository.actualize(dsn, False, False)
    # VERSION 3
    assert repository.current(dsn) == v(3)
    assert check_plan(
        repository.switch(v(0), dsn, True, False),
        [(False, v(3)), (False, v(2)), (False, v(1))],
    )
    assert repository.switch(v(0), dsn, False, False) == v(0)
    # VERSION 0
    assert repository.current(dsn) == v(0)
    assert check_plan(
        repository.switch(v(2), dsn, True, False),
        [
            (True, v(1)),
            (True, v(2)),
        ],
    )
    assert repository.switch(v(2), dsn, False, False) == v(2)
    # VERSION 2
    assert repository.current(dsn) == v(2)
    assert repository.down(v(1), dsn, False, False) == v(1)
    # VERSION 1
    assert repository.current(dsn) == v(1)
    plan = repository.up(v(3), dsn, True, False)
    # VERSION 1
    assert check_plan(plan, [(True, v(2)), (True, v(3))])
    assert repository.current(dsn) == v(1)
    repository.up(v(3), dsn, False, True)
    # VERSION 1
    assert repository.current(dsn) == v(1)
    repository.up(None, dsn, False, False)
    # VERSION 3
    assert repository.current(dsn) == v(3)
    dump = repository.dump(v(3), image, tag)
    assert "CREATE SCHEMA" in dump
    assert "CREATE TABLE" in dump
    assert "CREATE UNIQUE" in dump
    # testing permissions
    db.execute(
        "CREATE ROLE user1 LOGIN PASSWORD 'pwd' "
        "NOSUPERUSER INHERIT NOCREATEDB NOCREATEROLE NOREPLICATION"
    )
    perm_path = str(tmpdir.mkdir("perm"))
    perm_filename = os.path.join(perm_path, "permissions.yml")
    f = io.open(perm_filename, "w", encoding="UTF8")
    f.write(PERM_TEST_1)
    f.close()
    f = io.open(perm_filename, encoding="UTF8")
    queries = ipmt.permissions.update(dsn, f, None, None, True)
    assert queries == PERM_TEST_1_QUERIES
    shutil.rmtree(perm_path)


# def test_full_greenplum(greenplum, repository, tmpdir):
#     host, port, user, dbname, image, tag = greenplum
#     dsn = "%s@%s:%d/%s" % (user, host, port, dbname)
#     db = Database(dsn)
#
#     # VERSION 0
#     assert repository.current(dsn) == v(0)
#     assert repository.head(None) == v(0)
#     filename = repository.create(
#         "baseline", None, "CREATE SCHEMA test;", "DROP SCHEMA test;"
#     )
#     assert repository.head(None) == v(1)
#     assert v(1) in filename
#     assert check_plan(
#         repository.up(v(1), dsn, True, False),
#         [
#             (True, v(1)),
#         ],
#     )
#     assert repository.up(v(1), dsn, False, False) == v(1)
#
#     # VERSION 1
#     assert repository.current(dsn) == v(1)
#     assert check_plan(
#         repository.down(v(0), dsn, True, False),
#         [
#             (False, v(1)),
#         ],
#     )
#     assert repository.down(None, dsn, False, False) == v(0)
#
#     # VERSION 0
#     filename = repository.create(
#         "create_table",
#         None,
#         "CREATE TABLE test.t1(id int PRIMARY KEY);",
#         "DROP TABLE test.t1;",
#     )
#     assert v(2) in filename
#     filename = repository.create(
#         "create_table2",
#         "000001.b1",
#         "CREATE TABLE test.t_b1(a int PRIMARY KEY);",
#         "DROP TABLE test.t_b1;",
#     )
#     assert repository.head(v(1, "b1")) == v(1, "b1", 1)
#     repository.reload()
#     assert v(1, "b1", 1) in filename
#     assert repository.up(v(1, "b1", 1), dsn, False, False) == v(1, "b1", 1)
#     # VERSION 1.b1.1
#     assert db.search_objects("^test.t_.*", [REL_TABLE]) == ["test.t_b1"]
#     assert db.search_objects("^test.t2_.*", [REL_TABLE]) == []
#     assert repository.current(dsn) == v(1, "b1", 1)
#     db.execute("INSERT INTO test.t_b1(a) VALUES(5);")
#     assert db.query_scalar("SELECT a FROM test.t_b1") == 5
#     repository.rebase(v(1, "b1"))
#     assert repository.head(None) == v(3)
#     with pytest.raises(OperationError):
#         repository.switch(v(2), dsn, False, False)
#     with pytest.raises(OperationError):
#         repository.down(v(0), dsn, False, False)
#     with pytest.raises(OperationError):
#         repository.up(v(2), dsn, False, False)
#     assert check_plan(
#         repository.actualize(dsn, True, False),
#         [(False, v(3)), (True, v(2)), (True, v(3))],
#     )
#     repository.actualize(dsn, False, False)
#     # VERSION 3
#     assert repository.current(dsn) == v(3)
#     assert check_plan(
#         repository.switch(v(0), dsn, True, False),
#         [(False, v(3)), (False, v(2)), (False, v(1))],
#     )
#     assert repository.switch(v(0), dsn, False, False) == v(0)
#     # VERSION 0
#     assert repository.current(dsn) == v(0)
#     assert check_plan(
#         repository.switch(v(2), dsn, True, False),
#         [
#             (True, v(1)),
#             (True, v(2)),
#         ],
#     )
#     assert repository.switch(v(2), dsn, False, False) == v(2)
#     # VERSION 2
#     assert repository.current(dsn) == v(2)
#     assert repository.down(v(1), dsn, False, False) == v(1)
#     # VERSION 1
#     assert repository.current(dsn) == v(1)
#     plan = repository.up(v(3), dsn, True, False)
#     # VERSION 1
#     assert check_plan(plan, [(True, v(2)), (True, v(3))])
#     assert repository.current(dsn) == v(1)
#     repository.up(v(3), dsn, False, True)
#     # VERSION 1
#     assert repository.current(dsn) == v(1)
#     repository.up(None, dsn, False, False)
#     # VERSION 3
#     assert repository.current(dsn) == v(3)
#     dump = repository.dump(v(3), image, tag)
#     assert "Greenplum Database" in dump
#     assert "CREATE SCHEMA" in dump
#     assert "CREATE TABLE" in dump
#     # testing permissions
#     db.execute("CREATE ROLE user1 LOGIN PASSWORD 'pwd'")
#     perm_path = str(tmpdir.mkdir("perm"))
#     perm_filename = os.path.join(perm_path, "permissions.yml")
#     f = io.open(perm_filename, "w", encoding="UTF8")
#     f.write(PERM_TEST_1)
#     f.close()
#     f = io.open(perm_filename, encoding="UTF8")
#     queries = ipmt.permissions.update(dsn, f, None, None, True)
#     assert queries == PERM_TEST_1_QUERIES
#     shutil.rmtree(perm_path)
