# -*- coding: utf-8 -*-
import os
import io
import re
import time
import yaml
import uuid
import socket
import logging
import datetime
import tempfile
import psycopg2
import jinja2
from docker.client import DockerClient
from docker.utils import kwargs_from_env
from ipmt.error import RepositoryError, OperationError
from ipmt.db import Database, Transaction
from ipmt.misc import autodetect_pg_dump_path, pg_dump, repr_str_multiline, \
    load_module_py


ROOT_BRANCH_NAME = '0'
NAME_PATTERN = 'a-zA-Z0-9_'
FILE_PATTERN = r'^((\d+)(?:\.([a-zA-Z0-9-]+)\.(\d+))*)#([%s]*)\.py$' % \
               NAME_PATTERN
MIGRATION_TEMPLATE = '''\
"""
Name: {{{{ name }}}}
Version: {{{{ version }}}}
Create Date: {{{{ now.strftime('%Y-%m-%d %H:%M:%S%z') }}}}

"""
from ipmt.db import transactional


@transactional()
def up(db):
    """
    :type db: ipmt.db.Database
    """
    db.execute({sql_up})


@transactional()
def down(db):
    """
    :type db: ipmt.db.Database
    """
    db.execute({sql_down})

'''


# TODO lock timeout


class Repository(object):
    def __init__(self, path):
        self.path = path
        self.root = None
        self.db = None
        self._meta = None

    @staticmethod
    def init(path, dsn):
        pg_dump_path = None
        if dsn:
            pg_dump_path = autodetect_pg_dump_path()
            if not pg_dump_path:
                raise OperationError("Error: pg_dump executable not found.\n"
                                     "Please add the directory containing "
                                     "pg_dump to the PATH")

        if os.path.exists(path):
            raise OperationError('Directory %s already exists' % path)
        os.mkdir(path)
        try:
            if pg_dump_path:
                Repository._create_baseline(path, dsn)
        except Exception:
            os.rmdir(path)
            raise
        return 'Initialized new repository in %s' % path

    @staticmethod
    def load(path):
        """
        :type path: str
        :rtype: Repository
        """
        rep = Repository(path)
        rep._load()
        return rep

    @property
    def meta(self):
        if self._meta is not None:
            return self._meta
        filename = os.path.join(self.path, 'meta.yml')
        if os.path.exists(filename):
            with io.open(filename, 'r', encoding="UTF8") as f:
                self._meta = yaml.load(f.read())
        return self._meta

    @meta.setter
    def meta(self, value):
        self._meta = value
        filename = os.path.join(self.path, 'meta.yml')
        with io.open(filename, 'w', encoding="UTF8") as f:
            f.write(yaml.dump(value) + u"\n")

    @property
    def is_empty(self):
        return self.root is None or len(self.root) == 0

    def get_db(self, dsn):
        if self.db is None:
            self.db = Database(dsn)
        return self.db

    def create(self, message, branch, sql_up='', sql_down=''):
        if branch:
            target_branch = self.root.find_branch(branch)
            if target_branch is None:
                bpath = branch.split('.')
                if len(bpath) < 2 or len(bpath) % 2:
                    raise OperationError("Invalid branch name %s" % branch)
                else:
                    parent_ver = ".".join(bpath[0:-1])
                    parent = self.root.find_version(parent_ver)
                    if parent is None:
                        raise OperationError("Version %s does not exists"
                                             "" % parent_ver)
                    target_branch = Branch(bpath, self, parent)
                    parent.branches[bpath[-1]] = target_branch
        else:
            target_branch = self.root
        head = target_branch.head
        if head is not None:
            vpath = head.vpath[:]
            vpath[-1] = Version.format_version(int(vpath[-1]) + 1, head.branch)
        else:
            vpath = (target_branch.bpath or []) + \
                    [Version.format_version(1, target_branch)]
        name = Version._get_name(message)
        new_version = Version(vpath, None, name, self, target_branch)
        new_version.save(sql_up=sql_up, sql_down=sql_down)
        # target_branch.append(new_version)
        self.reload()
        return new_version.filename

    def head(self, branch):
        if branch:
            head_branch = self.root.find_branch(branch)
            if head_branch is None:
                raise OperationError("Branch %s not found" % branch)
        else:
            head_branch = self.root
        if head_branch.head:
            return head_branch.head.full_version
        else:
            return '0'

    def show(self, dsn):
        self.db = self.get_db(dsn)
        highlight = [self._search_newest_version(v) for v in self.db.history]
        return self.root.show(highlight=highlight).rstrip()

    def current(self, dsn):
        """
        Returns current database version
        :param dsn: Database connection string
        :type dsn: str
        :return: Current database version
        :rtype: str
        """
        db = self.get_db(dsn)
        return db.current or '0'

    def up(self, version, dsn, show_plan, dry_run):
        """
        Upgrade database to target version

        :param version: target version
        :param dsn: database connection string
        :param show_plan: if True then returns execution plan to do
        :param dry_run: if True then returns sql queries to do
        :type version: str
        :type dsn: str
        :type show_plan: bool
        :type dry_run: bool
        :return: current version as string(if show_plan=False & dry_run=False)
                 or execution plan (if show_plan=True & dry_run=False)
                 or sql queries as string (if show_plan=False & dry_run=True)
        :rtype: Union[str, Plan]
        """
        self._check_consistency(dsn)
        current = self._current_version(dsn)
        if version is not None and version != 'latest':
            target = self.root.find_version(version)
        elif current is not None:
            target = current.branch.head
        else:
            target = self.root.head
        if target is None:
            raise OperationError(
                "Target version %s not found in repository" % version)
        plan = Plan.get_switch_plan(current, target, self)
        db = self.get_db(dsn)
        if show_plan:
            return plan
        else:
            plan.execute(db, dry_run, up_only=True)
            if dry_run:
                return "\n\n".join(db.buffer)
            else:
                return self.current(dsn) or '0'

    def down(self, version, dsn, show_plan, dry_run):
        """
        Downgrade database to target version

        :param version: target version
        :param dsn: database connection string
        :param show_plan: if True then returns execution plan to do
        :param dry_run: if True then returns sql queries to do
        :type version: str
        :type dsn: str
        :type show_plan: bool
        :type dry_run: bool
        :return: current version as string(if show_plan=False & dry_run=False)
                 or execution plan (if show_plan=True & dry_run=False)
                 or sql queries as string (if show_plan=False & dry_run=True)
        :rtype: Union[str, Plan]
        """
        self._check_consistency(dsn)
        current = self._current_version(dsn)
        if version:
            if version == '0':
                target = None
            else:
                target = self.root.find_version(version)
                if target is None:
                    raise OperationError(
                        "Target version %s not found in repository" % version)
        elif current is not None:
            target = current.prev
        else:
            target = None
        plan = Plan.get_switch_plan(current, target, self)
        db = self.get_db(dsn)
        if show_plan:
            return plan
        else:
            plan.execute(db, dry_run, down_only=True)
            if dry_run:
                return "\n\n".join(db.buffer)
            else:
                return self.current(dsn) or '0'

    def actualize(self, dsn, show_plan, dry_run):
        db_current = self.current(dsn)
        new_current = self._search_newest_version(db_current)
        if db_current != new_current:
            current = self.root.find_version(new_current)

            down_hist = self.db.history
            for i in range(len(down_hist)):
                down_hist[i] = self.root.find_version(
                    self._search_newest_version(down_hist[i]))

            up_plan = Plan.get_plan(current, self)
            i = 0
            while down_hist[i].full_version == \
                    up_plan[i].version.full_version \
                    and len(up_plan) > 0:
                i += 1
            plan = Plan(
                [Action(False, v) for v in reversed(down_hist[i:])] +
                up_plan[i:],
                self, current, current
            )
            if show_plan:
                return plan
            else:
                db = self.get_db(dsn)
                plan.execute(db, dry_run)
                if dry_run:
                    return "\n\n".join(db.buffer)
                else:
                    return self.current(dsn) or '0'
        return 'Everything fine'

    def switch(self, version, dsn, show_plan, dry_run):
        self._check_consistency(dsn)
        current = self._current_version(dsn)
        if version == '0':
            target = None
        else:
            target = self.root.find_version(version)
            if target is None:
                raise OperationError(
                    "Target version %s not found in repository" % version)
        plan = Plan.get_switch_plan(current, target, self)
        db = self.get_db(dsn)
        if show_plan:
            return plan
        else:
            plan.execute(db, dry_run)
            if dry_run:
                return "\n\n".join(db.buffer)
            else:
                return self.current(dsn) or '0'

    def rebase(self, branch):
        br = self.root.find_branch(branch)
        if br is None:
            raise OperationError(
                "Target branch %s not found in repository" % branch)
        return br.rebase()

    def dump(self, ver, image, version):
        return self._create_dump(ver, image, version)

    def _create_dump(self, ver, image, version):
        dbname = 'postgres'
        user = 'postgres'
        is_greenplum = 'gpdb' in image
        if is_greenplum:
            user = 'gpadmin'

        fix = self._create_docker_pg_db(
            image=image,
            version=version,
            dbname=dbname,
            user=user,
            init_timeout=600)
        pg, cont = next(fix)

        try:
            self.db = None
            self.up(ver, '%s@%s/%s' % (user, ('%s:%s' % pg), dbname),
                    False, False)

            if is_greenplum:
                _, dump = cont.exec_run(
                    "bash -c '"
                    "ln -s /opt/gpdb/lib/libpq.so.5 /usr/lib/libpq.so.5 && "
                    "/opt/gpdb/bin/pg_dump -h 127.0.0.1 -U %s "
                    "--schema-only --no-owner --no-privileges %s'"
                    "" % (user, dbname))
            else:
                _, dump = cont.exec_run([
                    'gosu', 'postgres', 'pg_dump',
                    '--schema-only', '--no-owner',
                    '--no-privileges', '--no-tablespaces',
                    '--no-unlogged-table-data', 'postgres'
                ])
            return dump.decode("UTF-8")
        finally:
            try:
                next(fix)
            except StopIteration:
                pass

    @staticmethod
    def _create_docker_pg_db(image, version='latest', user='postgres',
                             dbname='postgres', host='127.0.0.1',
                             init_timeout=10):
        # searching free port
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()

        client = DockerClient(version='auto', **kwargs_from_env())
        cont = client.containers.run(
            f'{image}:{version}', detach=True,
            ports={'5432/tcp': (host, port)},
            environment={"POSTGRES_HOST_AUTH_METHOD": "trust"}
        )
        try:
            start_time = time.time()
            conn = None
            while conn is None:
                if start_time + init_timeout < time.time():
                    raise Exception("Initialization timeout, failed to "
                                    "initialize postgresql container")
                try:
                    conn = psycopg2.connect(f'dbname={dbname} user={user} '
                                            f'host={host} port={port}')
                except psycopg2.OperationalError:
                    time.sleep(.10)
            conn.close()
            yield (host, port), cont
        finally:
            cont.kill()
            cont.remove()

    def reload(self):
        self._load()

    def _load(self):
        logging.debug("Loading repository from %s" % self.path)
        all_files = Repository._search_rep_files(self.path)
        self.root = Branch.load(None, all_files, self, None)
        if len(all_files):
            raise RepositoryError('Found deattached versions: %s' % (
                ', '.join([item[0] for item in all_files]),))

    @staticmethod
    def _create_baseline(path, dsn):
        fileno, dump_filename = tempfile.mkstemp()
        returncode, stdout, stderr = pg_dump(dsn, dump_filename)
        if returncode != 0:
            raise OperationError(stderr)
        with open(dump_filename, 'a') as f:
            f.write('SET search_path = public, pg_catalog;\n')

        rep = Repository.load(path)
        db = rep.get_db(dsn)
        with io.open(dump_filename, 'r', encoding='UTF8') as f:
            sql_up = f.read()
            sql_down = "\n".join(db.schemas)
            filename = rep.create("baseline", None, sql_up, sql_down)
        db.ops_add('up', None, os.path.basename(filename).split('#')[0])

    @staticmethod
    def _search_rep_files(path):
        reg = re.compile(FILE_PATTERN)
        dir_files = os.listdir(path)
        rep_files = []
        for file in dir_files:
            filename = os.path.join(path, file)
            if os.path.isfile(filename):
                matches = reg.search(os.path.basename(file))
                if matches:
                    rep_files.append((file, os.path.join(path, file),
                                      matches.group(5),
                                      matches.group(1).split('.')))
                    continue
            logging.debug("Skipping %s" % filename)
        return rep_files

    def _current_version(self, dsn):
        current_ver = self.current(dsn)
        if current_ver and current_ver != '0':
            current = self.root.find_version(current_ver)
            if current is None:
                raise OperationError(
                    "Current version %s not found in repository" % current_ver)
            return current
        return None

    def _check_consistency(self, dsn):
        errors = self._check_for_actualize(dsn)
        if len(errors):
            err_str = ', '.join(["%s -> %s" % e for e in errors])
            raise OperationError('Inconsistent state: %s' % err_str)

    def _check_for_actualize(self, dsn):
        current_ver = self.current(dsn)
        errors = []
        meta = self.meta
        if meta and "rebase" in meta:
            history = []
            ver = current_ver
            while ver in meta["rebase"]:
                history.append((ver, meta["rebase"][ver]))
                ver = meta["rebase"][ver]
            for old_ver, new_ver in history:
                old_vpath = old_ver.split('.')
                new_vpath = new_ver.split('.')
                if len(old_vpath) != len(new_vpath) + 2 \
                        or int(old_vpath[-1]) + 1 != int(new_vpath[-1]):
                    errors.append((old_ver, new_ver))
        return errors

    def _search_newest_version(self, version):
        ver = version
        meta = self.meta
        if meta and "rebase" in meta:
            while ver in meta["rebase"]:
                ver = meta["rebase"][ver]
        return ver

    def _get_head(self, branch):
        """
        :param branch: Full branch name. Ex: 001.TEST.1.TEST2
        :type branch: str
        :return: Head version of selected branch or None for root
        :rtype: Version
        """
        return self.root.find_branch(branch).head

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.path)


class Version(object):
    TEMPLATE_FILENAME = "{version}#{name}.py"

    def __init__(self, vpath, filename, name, rep, branch):
        self.vpath = vpath
        self.rep = rep
        self.version = int(vpath[-1])
        self.name = name
        self.filename = filename
        self.branch = branch
        self.branches = {}
        self._mod = None
        self.is_up_transactional = True
        self.is_down_transactional = True
        self.isolation_level_up = None
        self.isolation_level_down = None

    @property
    def full_version(self):
        return ".".join(self.vpath)

    @property
    def prev(self):
        idx = self.branch.index(self)
        if idx:
            return self.branch[idx - 1]
        elif self.branch and self.branch.parent:
            return self.branch.parent
        return None

    def show(self, padding="", highlight=None, color=True):
        if highlight is not None and self.full_version in highlight:
            if color:
                res = "%s\033[1mver. %s\033[0m\n" % (padding,
                                                     self.full_version)
            else:
                res = "%s[ver. %s]\n" % (padding, self.full_version)
        else:
            res = "%sver. %s\n" % (padding, self.full_version)
        for name in sorted(self.branches.keys()):
            res += self.branches[name].show(padding=padding + "  ",
                                            highlight=highlight)
        return res

    def up(self, db):
        self._mod.up(db)

    def down(self, db):
        self._mod.down(db)

    def save(self, sql_up, sql_down):
        if self.filename:
            raise OperationError('File already exists %s' % self.filename)
        self.filename = os.path.join(
            self.rep.path,
            Version.TEMPLATE_FILENAME.format(version=self.full_version,
                                             name=self.name))
        logging.debug("Generating %s" % self.filename)
        tmpl = jinja2.Template(MIGRATION_TEMPLATE.format(
            sql_up=repr_str_multiline(sql_up),
            sql_down=repr_str_multiline(sql_down)))
        with io.open(self.filename, 'w', encoding="UTF8") as f:
            f.write(tmpl.render(
                now=datetime.datetime.utcnow(),
                version=self.full_version,
                name=self.name
            ))

    def can_rebase(self, branch):
        """
        Checks for rebase possibility
        :type branch: Branch
        :rtype: bool
        """
        return len(self.branches) == 0

    def rebase(self, branch):
        """
        :type branch: Branch
        """
        if not self.can_rebase(branch):
            raise OperationError('Version %s can not be rebased, because have '
                                 'own branches' % self.full_version)
        result = ''
        old_full_version = self.full_version
        head = branch.head
        if head:
            version = head.version + 1
        else:
            version = 1
        self.branch.remove(self)
        self.version = version
        version_str = Version.format_version(version, branch)
        self.vpath = self.vpath[0:-3] + [version_str]
        self.branch = branch
        old_filename = self.filename
        self.filename = os.path.join(
            self.rep.path,
            Version.TEMPLATE_FILENAME.format(version=self.full_version,
                                             name=self.name))
        branch.append(self)
        result += "Moving %s to %s\n" % (old_full_version, self.full_version)
        meta = self.rep.meta
        if meta is None:
            meta = {}
        if 'rebase' not in meta:
            meta['rebase'] = {}
        meta['rebase'][old_full_version] = self.full_version
        self.rep.meta = meta
        os.rename(old_filename, self.filename)
        return result

    @staticmethod
    def format_version(version, branch):
        if branch.bpath is None:
            return "%06d" % version
        else:
            return str(version)

    @staticmethod
    def validate_version(version):
        vpath = version.split('.')
        for i in range(0, len(vpath), 2):
            try:
                int(vpath[i])
            except ValueError:
                raise OperationError("Invalid version: %s" % version)

    @staticmethod
    def load(vpath, all_files, filename, name, rep, branch):
        ver = Version(vpath, filename, name, rep, branch)
        branches = Version._search_branches(vpath, all_files)
        for bfile, bfilename, bname, bpath in branches:
            if bpath[-2] not in ver.branches:
                ver.branches[bpath[-2]] = Branch.load(bpath[0:-1], all_files,
                                                      rep, ver)
        module_name = 'ipmt_' + str(uuid.uuid4()).replace('-', '')[0:16]
        ver._mod = load_module_py(module_name, filename)
        if hasattr(ver._mod, 'up'):
            if hasattr(ver._mod.up, '__transactional__'):
                ver.is_up_transactional = True
                ver.isolation_level_up = ver._mod.up.__transactional__
            else:
                ver.is_up_transactional = False
                ver.isolation_level_up = None
        if hasattr(ver._mod, 'down'):
            if hasattr(ver._mod.down, '__transactional__'):
                ver.is_down_transactional = True
                ver.isolation_level_down = ver._mod.down.__transactional__
            else:
                ver.is_down_transactional = False
                ver.isolation_level_down = None
        return ver

    @staticmethod
    def _search_branches(cpath, all_files):
        result = []
        for file, filename, name, vpath in all_files:
            if cpath == vpath[0:len(cpath)] and len(cpath) + 2 == len(vpath):
                result.append((file, filename, name, vpath))
        return result

    @staticmethod
    def _get_name(message):
        name = message.replace(' ', '_')
        name = re.compile('[^%s]' % NAME_PATTERN).sub('', name).lower()[0:64]
        return name

    def __lt__(self, other):
        return self._cmp(other, lambda a, b: a < b)

    def __le__(self, other):
        return self._cmp(other, lambda a, b: a <= b)

    def __eq__(self, other):
        return self._cmp(other, lambda a, b: a == b)

    def __ne__(self, other):
        return self._cmp(other, lambda a, b: a != b)

    def __ge__(self, other):
        return self._cmp(other, lambda a, b: a >= b)

    def __gt__(self, other):
        return self._cmp(other, lambda a, b: a > b)

    def _cmp(self, other, fn):
        # assert len(self.vpath) == len(other.vpath)
        assert self.vpath[0:-1] == other.vpath[0:-1]
        return fn(self.vpath[-1], other.vpath[-1])

    def __repr__(self):
        return '%s(%r, %r, %r, %r, %r)' % (
            self.__class__.__name__, self.vpath, self.filename, self.name,
            self.rep, self.branch)


# class Branch(List[Version]):
class Branch(list):
    def __init__(self, bpath, rep, parent):
        """
        :type bpath: list
        :type rep: Repository
        :type parent: Version
        """
        self.bpath = bpath
        self.name = bpath[-1] if bpath else None
        self.rep = rep
        self.parent = parent
        super(Branch, self).__init__()

    @property
    def full_version(self):
        if self.bpath:
            return ".".join(self.bpath)
        return None

    def rebase(self):
        if self.parent is None:
            raise OperationError("The selected branch can not be rebased")
        target_branch = self.parent.branch
        for version in self:
            if not version.can_rebase(target_branch):
                raise OperationError('Version %s can not be rebased, because '
                                     'have own branches' % self.full_version)
        history = []
        result = ''
        for version in self[:]:
            history.append(version.full_version)
            result += version.rebase(target_branch)
        self.parent.branches.pop(self.name)

        meta = self.rep.meta
        if "history" not in meta:
            meta["history"] = []
        meta["history"].append(history)
        self.rep.meta = meta
        return result

    @staticmethod
    def load(bpath, all_files, rep, parent):
        branch = Branch(bpath, rep, parent)
        branch_files = Branch._search_branch_vers(bpath, all_files)
        for item in branch_files:
            file, filename, name, vpath = item
            branch.append(
                Version.load(vpath, all_files, filename, name, rep, branch))
            all_files.remove(item)
        return branch

    @staticmethod
    def _search_branch_vers(bpath, all_files):
        result = []
        for file, filename, name, vpath in all_files:
            if bpath is None:
                if len(vpath) == 1:
                    result.append((file, filename, name, vpath))
            elif bpath == vpath[0:len(bpath)] and len(bpath) + 1 == len(vpath):
                result.append((file, filename, name, vpath))
        return result

    def append(self, p_object):
        super(Branch, self).append(p_object)
        self.sort()

    def show(self, padding="", highlight=None):
        if self.bpath is not None:
            res = ""
        else:
            res = "%sRepository:\n" % (padding,)
        for version in self:
            res += version.show(padding=padding + "  ", highlight=highlight)
        return res

    @property
    def head(self):
        if len(self):
            return self[-1]
        return None

    def find_branch(self, path):
        """
        Search branch recursively
        :param path: path to branch. Ex: 001.TEST.2.TEST2
        :type path: str
        :return: branch or None
        :rtype: Branch
        """
        if path is None:
            return self
        bpath = path.split('.')
        search_version_val = bpath.pop(0)
        try:
            search_version = int(search_version_val)
        except ValueError:
            raise OperationError('Invalid version %s' % search_version_val)
        search_branch = bpath.pop(0)
        for ver in self:
            if ver.version == search_version:
                for branch_name, branch in ver.branches.items():
                    if branch_name == search_branch:
                        return branch.find_branch(".".join(bpath) or None)
        return None

    def find_version(self, path):
        """
        Search version recursively
        :param path: path to version
        :type path: str
        :return: target version or None if not found
        :rtype: Version
        """
        Version.validate_version(path)
        vpath = path.split('.')
        version = int(vpath.pop())
        branch = self
        if len(vpath):
            branch = self.find_branch(".".join(vpath))
        if branch:
            for ver in branch:
                if ver.version == version:
                    return ver
        return None

    def __str__(self):
        ver = self.full_version
        if ver:
            return 'Branch(' + self.full_version + ')'
        else:
            return 'Root'

    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__, self.bpath,
                                   self.rep, self.parent)


class Action(object):
    def __init__(self, is_up, version):
        """

        :param is_up:
        :type is_up: bool
        :param version:
        :type version: Version
        """
        self.is_up = is_up
        self.version = version
        self.rep = version.rep
        if self.is_up:
            self.is_transactional = self.version.is_up_transactional
            self.isolation_level = self.version.isolation_level_up
        else:
            self.is_transactional = self.version.is_down_transactional
            self.isolation_level = self.version.isolation_level_down

    def execute(self, db):
        if self.is_up:
            # logging.info("Upgrading to %s" % self.version.full_version)
            self.version.up(db)
            prev = self.version.prev
            if prev:
                old_full_version = prev.full_version
            else:
                old_full_version = None
            db.ops_add('up', old_full_version, self.version.full_version)
        else:
            # logging.info("Downgrading %s" % self.version.full_version)
            self.version.down(db)
            prev = self.version.prev
            if prev:
                new_full_version = prev.full_version
            else:
                new_full_version = None
            db.ops_add('down', self.version.full_version, new_full_version)

    def __str__(self):
        if self.is_up:
            type = 'Up'
        else:
            type = 'Down'
        xact = 'X' if self.is_transactional else ''
        return "%s%s2Version(%s)" % (xact, type, str(self.version))

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__,
                               self.is_up, self.version)


class Plan(list):
    def __init__(self, seq, rep, current, target):
        super(Plan, self).__init__(seq)
        self.seq = seq
        self.rep = rep
        self.current = current
        self.target = target

    def execute(self, db, dry_run, up_only=False, down_only=False):
        if up_only or down_only:
            for action in self:
                if up_only and not action.is_up:
                    raise OperationError(
                        'Can not be downgraded from version %s' % repr(action))
                if down_only and action.is_up:
                    raise OperationError(
                        'Can not be upgraded to version %s' % repr(action))
        old_dry_run = db.dry_run
        db.dry_run = dry_run
        tr = None
        for action in self:
            if tr is None and action.is_transactional:
                tr = Transaction(db, action.isolation_level)
                tr.begin()
            elif tr is not None and not action.is_transactional:
                tr.commit()
                tr = None
            elif tr is not None \
                    and tr.isolation_level != action.isolation_level:
                tr.commit()
                tr = Transaction(db, action.isolation_level)
                tr.begin()
            try:
                action.execute(db)
            except Exception:
                if tr is not None:
                    tr.rollback()
                raise
        if tr is not None:
            tr.commit()
        db.dry_run = old_dry_run

    @staticmethod
    def get_switch_plan(current, target, rep):
        if current is None:
            cur_vers = Plan([], rep, None, None)
        else:
            cur_vers = Plan._get_versions(current.rep.root,
                                          current.vpath[:])
        if target is None:
            tgt_vers = Plan([], rep, None, None)
        else:
            tgt_vers = Plan._get_versions(rep.root, target.vpath[:])
        while len(cur_vers) \
                and len(tgt_vers) \
                and cur_vers[0].full_version == tgt_vers[0].full_version:
            cur_vers.pop(0)
            tgt_vers.pop(0)
        return Plan(
            [Action(False, down) for down in reversed(cur_vers)] +
            [Action(True, up) for up in tgt_vers],
            rep,
            current,
            target
        )

    @staticmethod
    def get_plan(target, rep):
        """
        Return list of Actions from baseline to selected version
        :param target: Target version
        :type target: Version
        :rtype: Plan
        """
        result = Plan._get_versions(rep.root, target.vpath[:])
        return Plan([Action(True, ver) for ver in result], rep, None, target)

    @staticmethod
    def _get_versions(branch, vpath):
        result = []
        ver = int(vpath.pop(0))
        for version in branch:
            result.append(version)
            if ver == version.version:
                if len(vpath):
                    branch_name = vpath.pop(0)
                    branch = version.branches[branch_name]
                    return result + Plan._get_versions(branch, vpath)
                return result
        return result

    def __repr__(self):
        return '%s(%r, %r, %r, %r)' % (self.__class__.__name__,
                                       self.seq, self.rep, self.current,
                                       self.target)

    def __str__(self):
        if len(self) == 0:
            return 'nothing to do'
        plan_str = []
        for v in self:
            ver = v.version.full_version if self.target else '0'
            if v.is_up:
                type = 'Up'
                xact = 'x' if v.version.is_up_transactional else ''
            else:
                type = 'Down'
                xact = 'x' if v.version.is_down_transactional else ''
            plan_str.append("%s(%s%s)" % (ver, xact, type))

        if not self[-1].is_up:
            plan_str.append(self.target.full_version if self.target else '0')
        if self[0].is_up:
            plan_str = [self.current.full_version if self.current else '0'] + \
                       plan_str
        return ' -> '.join(plan_str)
