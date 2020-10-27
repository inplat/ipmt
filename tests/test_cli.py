# -*- coding: utf-8 -*-
"""
test_ipmt
----------------------------------
Tests for `ipmt` project.
"""
import tempfile
import pytest
from mock import patch
import ipmt
import ipmt.cli


@pytest.fixture
def response():
    """Sample pytest fixture.
    See more at: http://doc.pytest.org/en/latest/fixture.html
    """


def test_version():
    args = ipmt.cli.parse_argv("progname", ["version"])
    assert args.func == ipmt.cli.version


def test_log_level():
    args = ipmt.cli.parse_argv(
        "progname", ["--log-level", "WARNING", "version"]
    )
    assert args.log_level == "WARNING"
    with pytest.raises(SystemExit):
        ipmt.cli.parse_argv("progname", ["--log-level", "BLABLA", "version"])


def test_log_file():
    args = ipmt.cli.parse_argv(
        "progname", ["--log-file", "filename.log", "version"]
    )
    assert args.log_file == "filename.log"


@patch("ipmt.cli.version")
def test_update_cmd_version(cmd, capsys):
    ipmt.cli.main("progname", ["version"])
    assert cmd.called


@patch("ipmt.cli.up")
def test_update_cmd_up(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["up"])
    capsys.readouterr()

    ipmt.cli.main("progname", ["up", "--database", "test@host/test"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert not cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert not cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "versions"
    assert hasattr(cmd.call_args[0][0], "ver")

    ipmt.cli.main(
        "progname",
        [
            "up",
            "--database",
            "test@host/test",
            "--path",
            "ver",
            "--dry-run",
            "--show-plan",
        ],
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"
    assert hasattr(cmd.call_args[0][0], "ver")


@patch("ipmt.cli.down")
def test_update_cmd_down(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["down"])
    capsys.readouterr()

    ipmt.cli.main("progname", ["down", "--database", "test@host/test"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert not cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert not cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "versions"
    assert hasattr(cmd.call_args[0][0], "ver")

    ipmt.cli.main(
        "progname",
        [
            "down",
            "--database",
            "test@host/test",
            "--path",
            "ver",
            "--dry-run",
            "--show-plan",
        ],
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"
    assert hasattr(cmd.call_args[0][0], "ver")


@patch("ipmt.cli.switch")
def test_update_cmd_switch(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["switch"])
    capsys.readouterr()

    ipmt.cli.main(
        "progname", ["switch", "--database", "test@host/test", "000001"]
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert not cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert not cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "versions"
    assert hasattr(cmd.call_args[0][0], "ver")

    ipmt.cli.main(
        "progname",
        [
            "switch",
            "--database",
            "test@host/test",
            "--path",
            "ver",
            "--dry-run",
            "--show-plan",
            "000001",
        ],
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"
    assert hasattr(cmd.call_args[0][0], "ver")
    assert cmd.call_args[0][0].ver == "000001"


@patch("ipmt.cli.actualize")
def test_update_cmd_actualize(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["actualize"])
    capsys.readouterr()

    ipmt.cli.main("progname", ["actualize", "--database", "test@host/test"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert not cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert not cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "versions"

    ipmt.cli.main(
        "progname",
        [
            "actualize",
            "--database",
            "test@host/test",
            "--path",
            "ver",
            "--dry-run",
            "--show-plan",
        ],
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "show_plan")
    assert cmd.call_args[0][0].show_plan
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert cmd.call_args[0][0].dry_run
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"


@patch("ipmt.cli.create")
def test_update_cmd_create(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["create"])
    capsys.readouterr()

    ipmt.cli.main("progname", ["create", "test"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "branch")
    assert cmd.call_args[0][0].branch is None
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "versions"

    ipmt.cli.main(
        "progname", ["create", "-b", "001.b1", "--path", "ver", "test"]
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "branch")
    assert cmd.call_args[0][0].branch == "001.b1"
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"


@patch("ipmt.cli.head")
def test_update_cmd_head(cmd, capsys):
    ipmt.cli.main("progname", ["head"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "branch")
    assert cmd.call_args[0][0].branch is None
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "versions"

    ipmt.cli.main("progname", ["head", "-b", "001.b1", "--path", "ver"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "branch")
    assert cmd.call_args[0][0].branch == "001.b1"
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"


@patch("ipmt.cli.init")
def test_update_cmd_init(cmd, capsys):
    ipmt.cli.main("progname", ["init"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database is None
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "versions"

    ipmt.cli.main(
        "progname", ["init", "--path", "ver", "--database", "test@host/test"]
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"


@patch("ipmt.cli.show")
def test_update_cmd_show(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["show"])
    capsys.readouterr()

    ipmt.cli.main(
        "progname", ["show", "--path", "ver", "--database", "test@host/test"]
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"


@patch("ipmt.cli.current")
def test_update_cmd_current(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["switch"])
    capsys.readouterr()

    ipmt.cli.main(
        "progname",
        ["current", "--path", "ver", "--database", "test@host/test"],
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"


@patch("ipmt.cli.rebase")
def test_update_cmd_rebase(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["rebase"])
    capsys.readouterr()

    ipmt.cli.main("progname", ["rebase", "--path", "ver", "000001.b1"])
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "path")
    assert cmd.call_args[0][0].path == "ver"


@patch("ipmt.cli.grant")
def test_update_cmd_grant(cmd, capsys):
    with pytest.raises(SystemExit):
        ipmt.cli.main("progname", ["grant"])
    capsys.readouterr()

    output = tempfile.NamedTemporaryFile()
    input = tempfile.NamedTemporaryFile()

    ipmt.cli.main(
        "progname",
        [
            "grant",
            "--output",
            output.name,
            "--input",
            input.name,
            "--database",
            "test@host/test",
            "--roles",
            "user1",
            "user2",
            "--exclude",
            "obj1",
            "obj2",
            "--dry-run",
        ],
    )
    assert cmd.called
    assert hasattr(cmd.call_args[0][0], "output")
    assert cmd.call_args[0][0].output is not None
    assert hasattr(cmd.call_args[0][0].output, "write")
    assert hasattr(cmd.call_args[0][0], "input")
    assert cmd.call_args[0][0].input is not None
    assert hasattr(cmd.call_args[0][0].input, "read")
    assert hasattr(cmd.call_args[0][0], "database")
    assert cmd.call_args[0][0].database == "test@host/test"
    assert hasattr(cmd.call_args[0][0], "roles")
    assert cmd.call_args[0][0].roles == ["user1", "user2"]
    assert hasattr(cmd.call_args[0][0], "exclude")
    assert cmd.call_args[0][0].exclude == ["obj1", "obj2"]
    assert hasattr(cmd.call_args[0][0], "dry_run")
    assert cmd.call_args[0][0].dry_run
