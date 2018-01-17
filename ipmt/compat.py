# -*- coding: utf-8 -*-
import codecs
import locale
import sys

try:
    from urllib.parse import (urlsplit, urlunsplit, urlencode, parse_qsl,
                              quote, unquote)
except ImportError:
    from urlparse import urlsplit, urlunsplit, parse_qsl
    from urllib import urlencode, quote, unquote

PY2 = sys.version_info[0] == 2

py2k = sys.version_info < (3, 0)
py3k = sys.version_info >= (3, 0)
py33 = sys.version_info >= (3, 3)

if PY2:
    ustr = unicode
else:
    ustr = str

if PY2:
    exec('def reraise(tp, value, tb):\n raise tp, value, tb')
else:
    def reraise(tp, value, tb):
        raise value.with_traceback(tb)

if PY2:
    from urlparse import urlparse
else:
    from urllib.parse import urlparse


if PY2:
    from urllib import unquote
else:
    from urllib.parse import unquote

if PY2:
    exec('def exec_(code, globals_):\n '
         'exec code in globals_')
else:
    def exec_(code, globals_):
        exec(code, globals_)

if PY2 and hasattr(sys.stdout, 'isatty'):
    # In python2 sys.stdout is a byte stream.
    # Convert it to a unicode stream using the environment's preferred encoding
    if sys.stdout.isatty():
        encoding = sys.stdout.encoding
    else:
        encoding = locale.getpreferredencoding()
    stdout = codecs.getwriter(encoding)(sys.stdout)

else:
    stdout = sys.stdout

if PY2 and hasattr(sys.stderr, 'isatty'):
    # In python2 sys.stderr is a byte stream.
    # Convert it to a unicode stream using the environment's preferred encoding
    if sys.stderr.isatty():
        encoding = sys.stderr.encoding
    else:
        encoding = locale.getpreferredencoding()
    stderr = codecs.getwriter(encoding)(sys.stderr)

else:
    stderr = sys.stderr

if py2k:
    from mako.util import parse_encoding

if py33:
    from importlib import machinery

    def load_module_py(module_id, path):
        return machinery.SourceFileLoader(module_id, path).load_module(
            module_id)

    def load_module_pyc(module_id, path):
        return machinery.SourcelessFileLoader(module_id, path).load_module(
            module_id)
else:
    import imp

    def load_module_py(module_id, path):
        with open(path, 'rb') as fp:
            mod = imp.load_source(module_id, path, fp)
            if py2k:
                source_encoding = parse_encoding(fp)
                if source_encoding:
                    mod._alembic_source_encoding = source_encoding
            return mod

    def load_module_pyc(module_id, path):
        with open(path, 'rb') as fp:
            mod = imp.load_compiled(module_id, path, fp)
            # no source encoding here
            return mod
