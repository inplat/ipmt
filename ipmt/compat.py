# -*- coding: utf-8 -*-
import sys

py2k = sys.version_info < (3, 0)
py33 = sys.version_info >= (3, 3)


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
