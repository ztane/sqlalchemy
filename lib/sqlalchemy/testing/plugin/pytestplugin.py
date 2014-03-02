import pytest
import argparse

import os

# no package imports yet!  dont want to trip coverage.
import imp
path = os.path.join(os.path.dirname(__file__), "plugin_base.py")
plugin_base = imp.load_source("plugin_base", path)


def pytest_addoption(parser):
    group = parser.getgroup("sqlalchemy")

    def make_option(name, **kw):
        callback_ = kw.pop("callback", None)
        if callback_:
            class CallableAction(argparse.Action):
                def __call__(self, parser, namespace, values, option_string=None):
                    callback_(option_string, values, parser)
            kw["action"] = CallableAction

        group.addoption(name, **kw)

    plugin_base.setup_options(make_option)
    plugin_base.read_config()

