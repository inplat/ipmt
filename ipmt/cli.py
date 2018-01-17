# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys
import logging
import argparse
import traceback
import ipmt
import ipmt.migration
import ipmt.permissions
from ipmt.error import IpmtError


def parse_argv(prog, options):
    """
    Разбор аргументов командной строки

    :param prog: sys.argv[0]
    :param options: sys.argv[1:]
    :type prog: str
    :type: list
    :return:
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(prog=prog)

    parser.add_argument(
        '--log-level',
        dest='log_level',
        type=str,
        default='INFO',
        choices=[
            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
        ],
        help='Logging level',
    )

    parser.add_argument(
        '--log-file',
        dest='log_file',
        type=str,
        help='Logging file name',
    )

    subparsers = parser.add_subparsers()

    parser_version = subparsers.add_parser('version')
    parser_version.set_defaults(func=version)

    parser_revision = subparsers.add_parser('create')
    parser_revision.add_argument('--branch', '-b', type=str, dest='branch')
    _add_argument_path(parser_revision)
    parser_revision.add_argument('message', type=str, nargs='+')
    parser_revision.set_defaults(func=create)

    parser_head = subparsers.add_parser('head')
    parser_head.add_argument('--branch', '-b', type=str, dest='branch')
    _add_argument_path(parser_head)
    parser_head.set_defaults(func=head)

    parser_show = subparsers.add_parser('show')
    _add_argument_path(parser_show)
    _add_argument_dsn(parser_show)
    parser_show.set_defaults(func=show)

    parser_init = subparsers.add_parser('init')
    _add_argument_path(parser_init)
    _add_argument_dsn(parser_init, False)
    parser_init.set_defaults(func=init)

    parser_current = subparsers.add_parser('current')
    _add_argument_path(parser_current)
    _add_argument_dsn(parser_current)
    parser_current.set_defaults(func=current)

    parser_actualize = subparsers.add_parser('actualize')
    _add_argument_path(parser_actualize)
    _add_argument_dsn(parser_actualize)
    _add_argument_plan(parser_actualize)
    _add_argument_dry_run(parser_actualize)
    parser_actualize.set_defaults(func=actualize)

    parser_up = subparsers.add_parser('up')
    _add_argument_path(parser_up)
    _add_argument_dsn(parser_up)
    _add_argument_plan(parser_up)
    _add_argument_dry_run(parser_up)
    parser_up.add_argument('ver', type=str, nargs='?')
    parser_up.set_defaults(func=up)

    parser_switch = subparsers.add_parser('switch')
    _add_argument_path(parser_switch)
    _add_argument_dsn(parser_switch)
    _add_argument_plan(parser_switch)
    _add_argument_dry_run(parser_switch)
    parser_switch.add_argument('ver', type=str)
    parser_switch.set_defaults(func=switch)

    parser_down = subparsers.add_parser('down')
    _add_argument_path(parser_down)
    _add_argument_dsn(parser_down)
    _add_argument_plan(parser_down)
    _add_argument_dry_run(parser_down)
    parser_down.add_argument('ver', type=str, nargs='?')
    parser_down.set_defaults(func=down)

    parser_rebase = subparsers.add_parser('rebase')
    _add_argument_path(parser_rebase)
    parser_rebase.add_argument('branch', type=str)
    parser_rebase.set_defaults(func=rebase)

    parser_grant = subparsers.add_parser('grant')
    _add_argument_dsn(parser_grant)
    _add_argument_dry_run(parser_grant)
    parser_grant.add_argument('--output', '-o', dest='output',
                              type=argparse.FileType(mode='w'),
                              )
    parser_grant.add_argument('--input', '-i', dest='input',
                              type=argparse.FileType(mode='r'),
                              )
    parser_grant.add_argument('--roles', '-r', metavar='N', type=str,
                              nargs='+', dest="roles")
    parser_grant.add_argument('--exclude', '-e', metavar='N', type=str,
                              nargs='+', dest="exclude")
    parser_grant.set_defaults(func=grant)

    parser_dump = subparsers.add_parser('dump')
    _add_argument_path(parser_dump)
    parser_dump.add_argument('--pg-version', dest="pg_version", type=str,
                             default='latest')
    parser_dump.add_argument('--output', '-o', dest='output',
                             type=argparse.FileType(mode='w'),)
    parser_dump.add_argument('ver', type=str, nargs=1)
    parser_dump.set_defaults(func=dump)

    return parser.parse_args(options)


def _add_argument_path(parser):
    """
    :param parser:
    :type parser: argparse.ArgumentParser
    """

    path = os.getenv('IPMT_PATH', 'versions')
    parser.add_argument('--path', '-p', type=str, dest='path',
                        default=path)


def _add_argument_dry_run(parser):
    """
    :param parser:
    :type parser: argparse.ArgumentParser
    """
    parser.add_argument('--dry-run', action="store_true", dest='dry_run',
                        default=False)


def _add_argument_dsn(parser, required=True):
    """
    :param parser:
    :param required:
    :type parser: argparse.ArgumentParser
    :type required: bool
    """
    dsn = os.getenv('IPMT_DSN')
    if dsn is not None:
        required = False
    parser.add_argument('--database', '-d', type=str, dest='database',
                        default=dsn, required=required)


def _add_argument_plan(parser):
    """
    :param parser:
    :type parser: argparse.ArgumentParser
    """
    parser.add_argument('--show-plan', '-s', action="store_true",
                        dest='show_plan', default=False)


def setup_logging(options):
    """
    Настройка логирования

    :param options:
    :type options: argparse.Namespace
    """
    config = dict(level=getattr(logging, options.log_level))
    if options.log_file:
        config["filename"] = options.log_file
    logging.basicConfig(**config)


def version(args):
    """
    Выводит текущую вресию IPMT

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    print(ipmt.__version__)


def init(args):
    """
    Инициализация репозитория

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    print(ipmt.migration.Repository.init(args.path, args.database))


def create(args):
    """
    Создание новой версии

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print("'Created %s'" % repo.create(" ".join(args.message), args.branch))


def head(args):
    """
    Отображает последнюю версию в репозитории

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.head(args.branch))


def show(args):
    """
    Отображает текущую структуру репозитория с выделением примененных
    миграция к текущей БД

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.show(args.database))


def current(args):
    """
    Отображает текущую версию БД

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.current(args.database))


def actualize(args):
    """
    Производит завережение слияния ветки таким, образом, чтоб
    последовательность примененных миграций на указанной БД был таким же как и
    в репозитории.
    Внимание! Эта команда может приветси к откату некоторых версий!

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.actualize(args.database, args.show_plan, args.dry_run))


def up(args):
    """
    Обновление БД к указанной версии. Либо к последнейверсии, если версия не
    была передана.

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.up(args.ver, args.database, args.show_plan, args.dry_run))


def down(args):
    """
    Откатывает БД на одну версию назад, либо к указанной. Если передать
    целевую версию как 0, то произойдет откат всех версий

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.down(args.ver, args.database, args.show_plan, args.dry_run))


def switch(args):
    """
    Обновляет/откатывает версию БД к указанной версии

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.switch(args.ver, args.database, args.show_plan, args.dry_run))


def rebase(args):
    """
    Производит слияние дочерней ветки в родительскую. После слияния может
    протребоваться вызов actualize

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.rebase(args.branch))


def grant(args):
    """
    Выдает приелегии или забирает их по файлу в формате yaml.
    Может выгрузить привелегии в файл по указанной БД

    :param args: параметры командной строки
    :type args: argparse.Namespace
    """
    if args.output:
        ipmt.permissions.investigate(args.database, args.output, args.roles,
                                     args.exclude)
    else:
        queries = ipmt.permissions.update(args.database, args.input,
                                          args.roles, args.exclude,
                                          args.dry_run)
        if args.dry_run:
            print(queries)


def dump(args):
    """
    Производит сравнение двух версий
    :param args:
    :return:
    """
    repo = ipmt.migration.Repository.load(args.path)
    print(repo.dump(args.ver[0], args.pg_version),
          file=args.output or sys.stdout)


def main(prog=None, args=None):
    """
    Точка входа

    :return: код возврата приложения
    :rtype: int
    """
    if prog is None:
        prog, args = sys.argv[0], sys.argv[1:]
    try:
        options = parse_argv(prog, args)
        setup_logging(options)
        if hasattr(options, 'func'):
            return options.func(options)
        else:
            logging.info('Nothing to do')
    except IpmtError as e:
        print(str(e), file=sys.stderr)
        return 1
    except Exception as e:
        traceback.print_exc()
        return 255
    return 0


if __name__ == "__main__":
    sys.exit(main())
