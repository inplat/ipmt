# -*- coding: utf-8 -*-
import os
import sys
import string
import random
import getpass
import subprocess
from importlib import machinery
from urllib.parse import urlparse, unquote, parse_qs

PLATFORM_IS_WINDOWS = sys.platform.lower().startswith("win")


def random_str(size=6, chars=string.ascii_uppercase + string.digits):
    """
    Формирует строку из случайных символов

    :param size: размер строки
    :param chars: сприсок символов для формирования строки
    :type size: int
    :type chars: str
    :return: случайная строка
    :rtype: str
    """
    return "".join(random.choice(chars) for _ in range(size))


def autodetect_pg_dump_path():
    """Find and return the path to the pg_dump executable."""
    if PLATFORM_IS_WINDOWS:
        return _autodetect_pg_dump_path_windows()
    else:
        return _find_on_path("pg_dump")


def _find_on_path(exename, path_directories=None):
    if not path_directories:
        path_directories = os.environ["PATH"].split(os.pathsep)
    for dir_name in path_directories:
        fullpath = os.path.join(dir_name, exename)
        if os.path.isfile(fullpath):
            return fullpath
    return None


def _autodetect_pg_dump_path_windows():
    """Attempt several different ways of finding the pg_dump
    executable on Windows, and return its full path, if found."""

    # First, check for pg_dump.exe on the PATH, and use that if found.
    pg_dump_exe = _find_on_path("pg_dump.exe")
    if pg_dump_exe:
        return pg_dump_exe

    # Now, try looking in the Windows Registry to find a PostgreSQL
    # installation, and infer the path from that.
    pg_dump_exe = _get_pg_dump_from_registry()
    if pg_dump_exe:
        return pg_dump_exe

    return None


def _get_pg_dump_from_registry():
    try:
        import winreg
    except ImportError:
        import _winreg as winreg

    reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
    try:
        pg_inst_list_key = winreg.OpenKey(
            reg, "SOFTWARE\\PostgreSQL\\Installations"
        )
    except EnvironmentError:
        # No PostgreSQL installation, as best as we can tell.
        return None

    try:
        # Determine the name of the first subkey, if any:
        try:
            first_sub_key_name = winreg.EnumKey(pg_inst_list_key, 0)
        except EnvironmentError:
            return None

        pg_first_inst_key = winreg.OpenKey(
            reg, "SOFTWARE\\PostgreSQL\\Installations\\" + first_sub_key_name
        )
        try:
            pg_inst_base_dir = winreg.QueryValueEx(
                pg_first_inst_key, "Base Directory"
            )[0]
        finally:
            winreg.CloseKey(pg_first_inst_key)

    finally:
        winreg.CloseKey(pg_inst_list_key)

    pg_dump_path = os.path.join(pg_inst_base_dir, "bin", "pg_dump.exe")
    if not os.path.exists(pg_dump_path):
        return None

    # Support unicode paths, if this version of Python provides the
    # necessary infrastructure:
    if sys.version_info[0] < 3 and hasattr(sys, "getfilesystemencoding"):
        pg_dump_path = pg_dump_path.encode(sys.getfilesystemencoding())

    return pg_dump_path


def parse_dsn(dsn):
    """
    Разбирает строку подключения к БД и возвращает список из (host, port,
    username, password, dbname, unix_socket_path)
    Путь к unix сокету передается так:
    username@:5432/dname?host=/var/run/postgresql

    :param dsn: Строка подключения. Например: username@localhost:5432/dname
    :type: str
    :return: [host, port, username, password, dbname, unix_socket_path]
    :rtype: list
    """
    parsed = urlparse("pg://" + dsn)
    unix_socket_path = None
    if parsed.query:
        query = parse_qs(parsed.query)
        if 'host' in query:
            unix_socket_path = query['host'][0]

    return [
        parsed.hostname or "localhost",
        parsed.port or 5432,
        unquote(parsed.username)
        if parsed.username is not None
        else getpass.getuser(),
        unquote(parsed.password) if parsed.password is not None else None,
        parsed.path.lstrip("/"),
        unix_socket_path,
    ]


def pg_dump(dsn, output):
    """
    Сохраняет схему БД в файл

    :param dsn: Строка подключения. Например: username@localhost:5432/dname
    :param output: Имя файла для сохранения DDL
    :type dsn: str
    :type output: str
    """
    host, port, user, pwd, dbname, socket = parse_dsn(dsn)

    args = [
        autodetect_pg_dump_path(),
        "-h",
        socket or host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        dbname,
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "--no-tablespaces",
        "--no-unlogged-table-data",
        "-F",
        "p",
        "-f",
        output,
    ]
    env = os.environ.copy()
    if pwd:
        env["PGPASSWORD"] = pwd
    else:
        args.append("--no-password")

    return shell(args, env)


def shell(cmd, env=None, shell=False):
    """
    Запускает приложение по аргументам командной строки.

    :param cmd: аргументы командной строки
    :param env: переменные окружения
    :param shell:
    :type cmd: list
    :type env: dict
    :type shell: bool
    :return: Кортеж из returncode, stdout, stderr
    :rtype: tuple
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell,
        env=env,
    )
    stdoutdata, stderrdata = proc.communicate()
    try:
        stdoutdata = stdoutdata.decode("UTF8")
    except Exception:
        stdoutdata = str(stdoutdata)
    try:
        stderrdata = stderrdata.decode("UTF8")
    except Exception:
        stderrdata = str(stderrdata)
    return proc.returncode, stdoutdata, stderrdata


def repr_str_multiline(s):
    """
    Аналог repr(s), но в многосторочном варианте

    :param s: строка
    :type s: str
    :rtype: str
    """
    return 'r"""\n' + s.replace("\\", "\\\\").replace('"', '\\"') + '\n"""'


def load_module_py(module_id, path):
    return machinery.SourceFileLoader(module_id, path).load_module(module_id)
