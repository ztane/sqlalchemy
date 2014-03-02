#!/usr/bin/env python
"""
pytest plugin script.

This script is an extension to py.test which
installs SQLAlchemy's testing plugin into the local environment.

"""
import sys
import imp


from os import path
for pth in ['./lib']:
    sys.path.insert(0, path.join(path.dirname(path.abspath(__file__)), pth))

# installing without importing SQLAlchemy, so that coverage includes
# SQLAlchemy itself.
path = "lib/sqlalchemy/testing/plugin/pytestplugin.py"
pytestplugin = imp.load_source("pytestplugin", path)

for name in dir(pytestplugin):
    if not name.startswith("_"):
        exec("%s = pytestplugin.%s" % (name, name))