# -*- coding: utf-8 -*-
"""
test_ipmt
----------------------------------
Tests for `ipmt` project.
"""
import os
from ipmt.migration import Version, Repository, Action, Plan, Branch
from ipmt.error import OperationError
import pytest
from mock import Mock


def test_repository_create(repository):
    assert repository.is_empty
    repository.create("test", None)
    assert not repository.is_empty
    assert os.path.exists(os.path.join(repository.path, "000001#test.py"))
    repository.create("test2", None)
    assert repository.root.find_version("000002") is not None
    repository2 = Repository.load(repository.path)
    assert repository2.root.find_version("000002") is not None
    assert (
        repository2.root.find_version("000002").prev.full_version == "000001"
    )


def test_repository_meta(repository):
    assert repository.meta is None
    repository.meta = {"ok": True}
    meta = repository.meta
    assert meta["ok"]
    assert os.path.exists(os.path.join(repository.path, "meta.yml"))


def test_version():
    ver = Version(
        ["000001", "B1", "1"], "000001.B1.1_test.py", "test", None, None
    )
    assert ver.vpath == ["000001", "B1", "1"]
    assert ver.name == "test"
    assert ver.filename == "000001.B1.1_test.py"
    assert ver.full_version == "000001.B1.1"


def test_action():
    branch = Branch(["000001", "B1"], None, None)
    prev_ver = Version(
        ["000001", "B1", "1"], "000001.B1.1_test.py", "test", None, branch
    )
    branch.append(prev_ver)
    ver = Version(
        ["000001", "B1", "2"], "000001.B1.2_test.py", "test", None, branch
    )
    branch.append(ver)
    ver.is_up_transactional = True
    ver.is_down_transactional = True
    ver.isolation_level_up = "read committed"
    ver.isolation_level_down = "read committed"
    ver.up = Mock()
    ver.down = Mock()
    up_db = Mock()
    down_db = Mock()
    action = Action(True, ver)
    action.execute(up_db)
    ver.up.assert_called_with(up_db)
    up_db.ops_add.assert_called_with("up", "000001.B1.1", "000001.B1.2")
    action = Action(False, ver)
    action.execute(down_db)
    ver.down.assert_called_with(down_db)
    down_db.ops_add.assert_called_with("down", "000001.B1.2", "000001.B1.1")


def test_get_plan(repository):
    assert repository.is_empty
    repository.create("test", None)
    repository.create("test", None)
    v = repository.root.find_version("000002")
    plan = Plan.get_plan(v, repository)
    assert len(plan) == 2
    assert plan[0].is_up
    assert plan[0].version.full_version == "000001"
    assert plan[1].is_up
    assert plan[1].version.full_version == "000002"


def test_get_switch_plan(repository):
    repository.create("test_0", None)
    repository.create("test_1", "000001.B1")
    repository.create("test_2", "000001.B1")
    repository.create("test_0", None)
    cur = repository.root.find_version("000001.B1.2")
    tgt = repository.root.find_version("000002")
    plan = Plan.get_switch_plan(cur, tgt, repository)
    assert not plan[0].is_up
    assert plan[0].version.full_version == "000001.B1.2"
    assert not plan[1].is_up
    assert plan[1].version.full_version == "000001.B1.1"
    assert plan[2].is_up
    assert plan[2].version.full_version == "000002"


def test_rebase(repository):
    repository.create("test_0", None)
    repository.create("test_1", "000001.B1")
    repository.create("test_2", "000001.B1")
    repository.create("test_0", None)
    repository.rebase("000001.B1")
    assert os.path.exists(os.path.join(repository.path, "000003#test_1.py"))
    assert os.path.exists(os.path.join(repository.path, "000004#test_2.py"))
    repository.current = Mock(return_value="000001")
    repository._check_consistency(None)
    repository.current = Mock(return_value="000001.B1.2")
    with pytest.raises(OperationError):
        repository._check_consistency(None)


def test_show(repository):
    repository.create("test_0", None)
    repository.create("test_1", "000001.B1")
    res = repository.root.show()
    assert "000001.B1.1" in res


def test_validate_version():
    Version.validate_version("000001.B1.1")
    with pytest.raises(OperationError):
        Version.validate_version("000001.B1.AA")
