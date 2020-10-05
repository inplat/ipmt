# -*- coding: utf-8 -*-
import pytest
import yaml
from mock import patch
import ipmt.permissions
from ipmt.permissions import (
    is_all_privileges, privilege_to_string,
    ACL_INSERT, ACL_SELECT, ACL_UPDATE,
    ACL_ALL_RIGHTS_NAMESPACE, ACL_ALL_RIGHTS_RELATION, ACL_ALL_RIGHTS_SEQUENCE,
    ACL_ALL_RIGHTS_FUNCTION,
    RELKIND_NAMESPACE, RELKIND_TABLE, RELKIND_VIEW, RELKIND_MATVIEW,
    RELKIND_FOREIGN_TABLE, RELKIND_SEQUENCE, RELKIND_FUNCTION
)


def test_is_all_privileges():
    assert is_all_privileges(ACL_ALL_RIGHTS_NAMESPACE, RELKIND_NAMESPACE)
    assert not is_all_privileges(ACL_INSERT, RELKIND_NAMESPACE)
    assert not is_all_privileges(ACL_SELECT, RELKIND_NAMESPACE)
    assert is_all_privileges(ACL_ALL_RIGHTS_RELATION, RELKIND_TABLE)
    assert not is_all_privileges(ACL_INSERT, RELKIND_TABLE)
    assert is_all_privileges(ACL_ALL_RIGHTS_RELATION, RELKIND_VIEW)
    assert not is_all_privileges(ACL_SELECT | ACL_INSERT, RELKIND_VIEW)
    assert is_all_privileges(ACL_ALL_RIGHTS_RELATION, RELKIND_MATVIEW)
    assert is_all_privileges(ACL_ALL_RIGHTS_RELATION, RELKIND_FOREIGN_TABLE)
    assert is_all_privileges(ACL_ALL_RIGHTS_SEQUENCE, RELKIND_SEQUENCE)
    assert is_all_privileges(ACL_ALL_RIGHTS_FUNCTION, RELKIND_FUNCTION)


def test_privilege_to_string():
    assert privilege_to_string(ACL_INSERT) == "INSERT"
    assert privilege_to_string(ACL_SELECT) == "SELECT"
    with pytest.raises(NotImplementedError):
        privilege_to_string(-1)


@patch("psycopg2.connect")
def test_load_acl_base(mock_connect):
    given_acl = [
        ("schema1", "table1", "{usr1=r/usr3}", RELKIND_TABLE),
        ("schema1", "view1", "{usr2=w/usr3,usr4=r/usr3}", RELKIND_VIEW),
    ]
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    perm = ipmt.permissions.load_acl(
        ipmt.permissions.get_db('test@host/test'), None, None)
    assert perm == [
        ['schema1.table1', {'usr1': [ACL_SELECT]}, RELKIND_TABLE],
        ['schema1.view1', {'usr2': [ACL_UPDATE], 'usr4': [ACL_SELECT]},
         RELKIND_VIEW],
    ]


@patch("psycopg2.connect")
def test_load_acl_with_excl(mock_connect):
    given_acl = [
        ("schema1", "table1", "{usr1=r/usr3}", RELKIND_TABLE),
        ("schema1", "view1", "{usr2=w/usr3,usr4=r/usr3}", RELKIND_VIEW),
    ]
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    perm = ipmt.permissions.load_acl(
        ipmt.permissions.get_db('test@host/test'), ["schema1.table1"],
        None)
    assert perm == [
        ['schema1.view1', {'usr2': [ACL_UPDATE], 'usr4': [ACL_SELECT]},
         RELKIND_VIEW],
    ]


@patch("psycopg2.connect")
def test_load_acl_excl_regex(mock_connect):
    given_acl = [
        ("schema1", "table1", "{usr1=r/usr3}", RELKIND_TABLE),
        ("schema1", "view1", "{usr2=w/usr3,usr4=r/usr3}", RELKIND_VIEW),
    ]
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    perm = ipmt.permissions.load_acl(
        ipmt.permissions.get_db('test@host/test'), [r"~schema1\.table.*$"],
        None)
    assert perm == [
        ['schema1.view1', {'usr2': [ACL_UPDATE], 'usr4': [ACL_SELECT]},
         RELKIND_VIEW],
    ]


@patch("psycopg2.connect")
def test_load_acl_with_roles(mock_connect):
    given_acl = [
        ("schema1", "table1", "{usr1=r/usr3}", RELKIND_TABLE),
        ("schema1", "view1", "{usr2=w/usr3,usr4=r/usr3}", RELKIND_VIEW),
    ]
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    perm = ipmt.permissions.load_acl(
        ipmt.permissions.get_db('test@host/test'), None, ["usr1"])
    assert perm == [
        ['schema1.table1', {'usr1': [ACL_SELECT]}, RELKIND_TABLE],
        ['schema1.view1', {}, RELKIND_VIEW],
    ]


@patch("psycopg2.connect")
def test_investigate_base(mock_connect, tmpfile):
    given_acl = [
        ("schema1", "table1", "{user1=rwa/user1}", RELKIND_TABLE),
        ("schema2", "table2", "{user2=r/user2}", RELKIND_TABLE),
    ]
    expected_yml = u"""\
        objects:
          schema1.table1:
            user1: select, update, insert
          schema2.table2:
            user2: select
        roles:
        - user1
        - user2
    """
    # prepare
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    # execute
    ipmt.permissions.investigate('test@host/test', tmpfile, None, None)
    tmpfile.seek(0)
    assert yaml.safe_load(tmpfile) == yaml.safe_load(expected_yml)


@patch("psycopg2.connect")
def test_investigate_with_roles(mock_connect, tmpfile):
    given_acl = [
        ("schema1", "table1", "{user1=rwa/user1}", RELKIND_TABLE),
        ("schema2", "table2", "{user2=r/user2}", RELKIND_TABLE),
    ]
    expected_yml = u"""\
        objects:
          schema1.table1:
            user1: select, update, insert
        roles:
        - user1
    """
    # prepare
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    # execute
    ipmt.permissions.investigate('test@host/test', tmpfile, ['user1'],
                                 None)
    tmpfile.seek(0)
    assert yaml.safe_load(tmpfile) == yaml.safe_load(expected_yml)


@patch("psycopg2.connect")
def test_investigate_with_excl(mock_connect, tmpfile):
    given_acl = [
        ("schema2", "table2", "{user2=r/user1}", RELKIND_TABLE),
    ]
    expected_yml = u"""\
        exclude:
        - schema1.table1
        objects:
          schema2.table2:
            user2: select
        roles:
        - user2
    """
    # prepare
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    # execute
    ipmt.permissions.investigate('test@host/test', tmpfile, None,
                                 ['schema1.table1'])
    tmpfile.seek(0)
    assert yaml.safe_load(tmpfile) == yaml.safe_load(expected_yml)


@patch("psycopg2.connect")
def test_update_base(mock_connect, tmpfile):
    given_acl = [
        ("schema1", "table1", "{user1=raw/user1}", RELKIND_TABLE),
        ("schema1", "table2", "{user1=r/user1}", RELKIND_TABLE),
        ("schema2", "table1", "{user2=U/user2}", RELKIND_TABLE),
    ]
    given_yml = u"""\
        objects:
          schema1.table1:
            user1: select, update, insert
          schema1.table2:
            user1: select, update
          schema2.table1:
            user2: select, update, insert
        roles:
        - user1
        - user2
    """
    expected_sql = (
        'BEGIN ISOLATION LEVEL READ COMMITTED;\n'
        'GRANT UPDATE ON TABLE schema1.table2 TO user1;\n'
        'GRANT INSERT,SELECT,UPDATE ON TABLE schema2.table1 TO user2;\n'
        'COMMIT;'
    )
    # prepare
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    tmpfile.write(given_yml)
    tmpfile.seek(0)
    # execute
    queries = ipmt.permissions.update('test@host/test', tmpfile, None,
                                      None, True)
    assert expected_sql == queries


@patch("psycopg2.connect")
def test_update_with_roles(mock_connect, tmpfile):
    given_acl = [
        ("schema1", "table1", "{user1=raw/user1}", RELKIND_TABLE),
        ("schema1", "table2", "{user1=r/user1}", RELKIND_TABLE),
        ("schema2", "table1", "{user2=U/user2}", RELKIND_TABLE),
    ]
    given_yml = u"""\
        objects:
          schema1.table1:
            user1: select, update, insert
          schema1.table2:
            user1: select, update
          schema2.table1:
            user2: select, update, insert
        roles:
        - user1
        - user2
    """
    expected_sql = (
        'BEGIN ISOLATION LEVEL READ COMMITTED;\n'
        'GRANT UPDATE ON TABLE schema1.table2 TO user1;\n'
        'COMMIT;'
    )
    # prepare
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    tmpfile.write(given_yml)
    tmpfile.seek(0)
    # execute
    queries = ipmt.permissions.update('test@host/test', tmpfile, ["user1"],
                                      None, True)
    assert expected_sql == queries


@patch("psycopg2.connect")
def test_update_with_excl(mock_connect, tmpfile):
    given_acl = [
        ("schema1", "table1", "{user1=r/user1}", RELKIND_TABLE),
        ("schema1", "table2", "{user1=r/user1}", RELKIND_TABLE),
        ("schema2", "table1", "{user2=r/user2}", RELKIND_TABLE),
    ]
    given_yml = u"""\
        objects:
          schema1.table1:
            user1: select
          schema1.table2:
            user1: select, update
          schema2.table1:
            user2: none
        roles:
        - user1
        - user2
    """
    expected_sql = (
        'BEGIN ISOLATION LEVEL READ COMMITTED;\n'
        'GRANT UPDATE ON TABLE schema1.table2 TO user1;\n'
        'COMMIT;'
    )
    # prepare
    mock_con = mock_connect.return_value
    mock_cur = mock_con.cursor.return_value
    mock_cur.fetchall.return_value = given_acl
    tmpfile.write(given_yml)
    tmpfile.seek(0)
    # execute
    queries = ipmt.permissions.update('test@host/test', tmpfile, None,
                                      ["schema2.table1"], True)
    assert expected_sql == queries
