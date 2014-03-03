import pytest
import argparse

import os
fixtures = None


# no package imports yet!  this prevents us from tripping coverage
# too soon.
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

def pytest_configure(config):
    plugin_base.pre_begin(config.option)
    plugin_base.post_begin()
    global fixtures
    from sqlalchemy.testing import fixtures


def pytest_collection_modifyitems(session, config, items):
    items[:] = [
        item for item in items if
        isinstance(item.cls, type) and issubclass(item.cls, fixtures.TestBase)
        and not item.cls.__name__.startswith("_")
    ]

def pytest_pycollect_makeitem(collector, name, obj):
    # TODO: this would be nicer?  no clue what to
    # return here
    return None

_current_class = None

from pytest import Item
def pytest_runtest_setup(item):
    # I'd like to get module/class/test level calls here
    # but I don't quite see the pattern.

    # not really sure what determines if we're called
    # here with pytest.Class, pytest.Module, does not seem to be
    # consistent

    if not isinstance(item, Item):
        return
    global _current_class

    # ... so we're doing a little dance here to figure it out...
    if item.parent is not _current_class:

        class_setup(item.parent)
        _current_class = item.parent
        item.parent.addfinalizer(lambda: class_teardown(item.parent))

    test_setup(item)

def pytest_runtest_teardown(item, nextitem):
    if not isinstance(item, Item):
        return

    test_teardown(item)


def test_setup(item):
    id_ = "%s.%s:%s" % (item.parent.module.__name__, item.parent.name, item.name)
    plugin_base.before_test(item, id_)

def test_teardown(item):
    plugin_base.after_test(item)

def class_setup(item):
    try:
        plugin_base.start_test_class(item.cls)
    except plugin_base.GenericSkip as gs:
        pytest.skip(gs.message)

def class_teardown(item):
    plugin_base.stop_test_class(item.cls)
