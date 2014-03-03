import pytest
import argparse
import inspect
from . import plugin_base

py_unittest = None

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

    # because it feels icky importing from "_pytest"..
    global py_unittest
    py_unittest = config.pluginmanager.getplugin('unittest')

import collections
def pytest_collection_modifyitems(session, config, items):
    # look for all those classes that specify __multiple__ and
    # expand them out into per-database test cases.

    # this is much easier to do within pytest_pycollect_makeitem, however
    # pytest is unfortunately iterating through cls.__dict__ as makeitem is
    # called which causes a "dictionary changed size" error on py3k.
    # I'd submit a pullreq for them to turn it into a list first, but
    # it's to suit the rather odd use case here which is that we are adding
    # new classes to a module on the flt.

    rebuilt_items = collections.defaultdict(list)

    test_classes = set(item.parent for item in items)
    for test_class in test_classes:
        for sub_cls in plugin_base.generate_sub_tests(test_class.cls, test_class.parent.module):
            if sub_cls is not test_class.cls:
                rebuilt_items[test_class.cls].extend(py_unittest.UnitTestCase(
                                    sub_cls.__name__, parent=test_class.parent).collect())

    newitems = []
    for item in items:
        if item.parent.cls in rebuilt_items:
            #import pdb
            #pdb.set_trace()
            newitems.extend(rebuilt_items[item.parent.cls])
            rebuilt_items[item.parent.cls][:] = []
        else:
            newitems.append(item)

    items[:] = newitems

def pytest_pycollect_makeitem(collector, name, obj):
    if inspect.isclass(obj) and plugin_base.want_class(obj):
        return py_unittest.UnitTestCase(name, parent=collector)
        return [
            py_unittest.UnitTestCase(sub_obj.__name__, parent=collector)
            for sub_obj in plugin_base.generate_sub_tests(obj, collector.module)
        ]
    else:
        return []

_current_class = None

def pytest_runtest_setup(item):
    # I'd like to get module/class/test level calls here
    # but I don't quite see the pattern.

    # not really sure what determines if we're called
    # here with pytest.Class, pytest.Module, does not seem to be
    # consistent

    global _current_class

    # ... so we're doing a little dance here to figure it out...
    if item.parent is not _current_class:

        class_setup(item.parent)
        _current_class = item.parent

        # this is needed for the class-level, to ensure that the
        # teardown runs after the class is completed with its own
        # class-level teardown...
        item.parent.addfinalizer(lambda: class_teardown(item.parent))

    test_setup(item)

def pytest_runtest_teardown(item):
    # ...but this works better as the hook here rather than
    # using a finalizer, as the finalizer seems to get in the way
    # of the test reporting failures correctly (you get a bunch of
    # py.test assertion stuff instead)
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
        print(gs)
        pytest.skip(str(gs))

def class_teardown(item):
    plugin_base.stop_test_class(item.cls)
