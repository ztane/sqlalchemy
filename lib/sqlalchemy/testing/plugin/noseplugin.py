# plugin/noseplugin.py
# Copyright (C) 2005-2014 the SQLAlchemy authors and contributors <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""Enhance nose with extra options and behaviors for running SQLAlchemy tests.

When running ./sqla_nose.py, this module is imported relative to the
"plugins" package as a top level package by the sqla_nose.py runner,
so that the plugin can be loaded with the rest of nose including the coverage
plugin before any of SQLAlchemy itself is imported, so that coverage works.

When third party libraries use this plugin, it can be imported
normally as "from sqlalchemy.testing.plugin import noseplugin".

"""

from __future__ import absolute_import

import os
import sys
py3k = sys.version_info >= (3, 0)

if py3k:
    import configparser
else:
    import ConfigParser as configparser

from nose.plugins import Plugin
from nose import SkipTest
import sys

# late imports
fixtures = None
engines = None
exclusions = None
warnings = None
profiling = None
assertions = None
requirements = None
config = None
testing = None
util = None
file_config = None


logging = None
db_opts = {}
options = None
_existing_config_obj = None


class Config(object):
    def __init__(self, db, db_opts, options, file_config):
        self.db = db
        self.db_opts = db_opts
        self.options = options
        self.file_config = file_config

def _log(option, opt_str, value, parser):
    global logging
    if not logging:
        import logging
        logging.basicConfig()

    if opt_str.endswith('-info'):
        logging.getLogger(value).setLevel(logging.INFO)
    elif opt_str.endswith('-debug'):
        logging.getLogger(value).setLevel(logging.DEBUG)


def _list_dbs(*args):
    print("Available --db options (use --dburi to override)")
    for macro in sorted(file_config.options('db')):
        print("%20s\t%s" % (macro, file_config.get('db', macro)))
    sys.exit(0)


def _server_side_cursors(options, opt_str, value, parser):
    db_opts['server_side_cursors'] = True


pre_configure = []
post_configure = []


def pre(fn):
    pre_configure.append(fn)
    return fn


def post(fn):
    post_configure.append(fn)
    return fn


@pre
def _setup_options(opt, file_config):
    global options
    options = opt


@pre
def _monkeypatch_cdecimal(options, file_config):
    if options.cdecimal:
        import cdecimal
        sys.modules['decimal'] = cdecimal


@post
def _engine_uri(options, file_config):
    from sqlalchemy.testing import engines, config
    from sqlalchemy import testing

    if options.dburi:
        db_urls = list(options.dburi)
    else:
        db_urls = []

    if options.db:
        for db in options.db:
            if db not in file_config.options('db'):
                raise RuntimeError(
                    "Unknown URI specifier '%s'.  Specify --dbs for known uris."
                            % db)
            else:
                db_urls.append(file_config.get('db', db))

    if not db_urls:
        db_urls.append(file_config.get('db', 'default'))

    for db_url in db_urls:
        eng = engines.testing_engine(db_url, db_opts)
        eng.connect().close()
        config_obj = Config(eng, db_opts, options, file_config)
        if not config.db:
            config.db = testing.db = eng
            config._current = config_obj
        config.dbs[eng.name] = config_obj
        config.dbs[(eng.name, eng.dialect)] = config_obj
        config.dbs[eng] = config_obj

    config.db_opts = db_opts


@post
def _engine_pool(options, file_config):
    if options.mockpool:
        from sqlalchemy import pool
        db_opts['poolclass'] = pool.AssertionPool

@post
def _prep_testing_database(options, file_config):
    from sqlalchemy.testing import config
    from sqlalchemy import schema, inspect

    if options.dropfirst:
        for e in set(config.dbs.values()):
            inspector = inspect(e)

            try:
                view_names = inspector.get_view_names()
            except NotImplementedError:
                pass
            else:
                for vname in view_names:
                    e.execute(schema._DropView(schema.Table(vname, schema.MetaData())))

            try:
                view_names = inspector.get_view_names(schema="test_schema")
            except NotImplementedError:
                pass
            else:
                for vname in view_names:
                    e.execute(schema._DropView(
                                schema.Table(vname,
                                            schema.MetaData(), schema="test_schema")))

            for tname in reversed(inspector.get_table_names(order_by="foreign_key")):
                e.execute(schema.DropTable(schema.Table(tname, schema.MetaData())))

            for tname in reversed(inspector.get_table_names(
                                    order_by="foreign_key", schema="test_schema")):
                e.execute(schema.DropTable(
                    schema.Table(tname, schema.MetaData(), schema="test_schema")))


@post
def _set_table_options(options, file_config):
    from sqlalchemy.testing import schema

    table_options = schema.table_options
    for spec in options.tableopts:
        key, value = spec.split('=')
        table_options[key] = value

    if options.mysql_engine:
        table_options['mysql_engine'] = options.mysql_engine


@post
def _reverse_topological(options, file_config):
    if options.reversetop:
        from sqlalchemy.orm.util import randomize_unitofwork
        randomize_unitofwork()


def _requirements_opt(options, opt_str, value, parser):
    _setup_requirements(value)

@post
def _requirements(options, file_config):

    requirement_cls = file_config.get('sqla_testing', "requirement_cls")
    _setup_requirements(requirement_cls)

def _setup_requirements(argument):
    from sqlalchemy.testing import config
    from sqlalchemy import testing

    if config.requirements is not None:
        return

    modname, clsname = argument.split(":")

    # importlib.import_module() only introduced in 2.7, a little
    # late
    mod = __import__(modname)
    for component in modname.split(".")[1:]:
        mod = getattr(mod, component)
    req_cls = getattr(mod, clsname)

    config.requirements = testing.requires = req_cls()

@post
def _post_setup_options(opt, file_config):
    from sqlalchemy.testing import config
    config.options = options
    config.file_config = file_config


@post
def _setup_profiling(options, file_config):
    from sqlalchemy.testing import profiling
    profiling._profile_stats = profiling.ProfileStatsFile(
                file_config.get('sqla_testing', 'profile_file'))


class NoseSQLAlchemy(Plugin):
    """
    Handles the setup and extra properties required for testing SQLAlchemy
    """
    enabled = True

    name = 'sqla_testing'
    score = 100

    def options(self, parser, env=os.environ):
        Plugin.options(self, parser, env)
        opt = parser.add_option
        opt("--log-info", action="callback", type="string", callback=_log,
            help="turn on info logging for <LOG> (multiple OK)")
        opt("--log-debug", action="callback", type="string", callback=_log,
            help="turn on debug logging for <LOG> (multiple OK)")
        opt("--db", action="append", type="string", dest="db",
                    help="Use prefab database uri. Multiple OK, "
                            "first one is run by default.")
        opt('--dbs', action='callback', callback=_list_dbs,
            help="List available prefab dbs")
        opt("--dburi", action="append", type="string", dest="dburi",
            help="Database uri.  Multiple OK, first one is run by default.")
        opt("--dropfirst", action="store_true", dest="dropfirst",
            help="Drop all tables in the target database first")
        opt("--mockpool", action="store_true", dest="mockpool",
            help="Use mock pool (asserts only one connection used)")
        opt("--low-connections", action="store_true", dest="low_connections",
            help="Use a low number of distinct connections - i.e. for Oracle TNS"
        )
        opt("--reversetop", action="store_true", dest="reversetop", default=False,
            help="Use a random-ordering set implementation in the ORM (helps "
                  "reveal dependency issues)")
        opt("--requirements", action="callback", type="string",
            callback=_requirements_opt,
            help="requirements class for testing, overrides setup.cfg")
        opt("--with-cdecimal", action="store_true", dest="cdecimal", default=False,
            help="Monkeypatch the cdecimal library into Python 'decimal' for all tests")
        opt("--serverside", action="callback", callback=_server_side_cursors,
            help="Turn on server side cursors for PG")
        opt("--mysql-engine", action="store", dest="mysql_engine", default=None,
            help="Use the specified MySQL storage engine for all tables, default is "
                 "a db-default/InnoDB combo.")
        opt("--table-option", action="append", dest="tableopts", default=[],
            help="Add a dialect-specific table option, key=value")
        opt("--write-profiles", action="store_true", dest="write_profiles", default=False,
                help="Write/update profiling data.")
        global file_config
        file_config = configparser.ConfigParser()
        file_config.read(['setup.cfg', 'test.cfg'])

    def configure(self, options, conf):
        Plugin.configure(self, options, conf)
        self.options = options
        for fn in pre_configure:
            fn(self.options, file_config)

    def begin(self):
        # Lazy setup of other options (post coverage)
        for fn in post_configure:
            fn(self.options, file_config)

        # late imports, has to happen after config as well
        # as nose plugins like coverage
        global util, fixtures, engines, exclusions, \
                        assertions, warnings, profiling,\
                        config, testing
        from sqlalchemy import testing
        from sqlalchemy.testing import fixtures, engines, exclusions, \
                        assertions, warnings, profiling, config
        from sqlalchemy import util

    def describeTest(self, test):
        return ""

    def wantFunction(self, fn):
        if fn.__module__ is None:
            return False
        if fn.__module__.startswith('sqlalchemy.testing'):
            return False

    def wantClass(self, cls):
        """Return true if you want the main test selector to collect
        tests from this class, false if you don't, and None if you don't
        care.

        :Parameters:
           cls : class
             The class being examined by the selector

        """
        if not issubclass(cls, fixtures.TestBase):
            return False
        elif cls.__name__.startswith('_'):
            return False
        else:
            return True

    def _do_skips(self, cls):
        from sqlalchemy.testing import config

        all_configs = set(config._unique_configs())
        reasons = []

        if hasattr(cls, '__requires__'):
            requirements = config.requirements
            for config_obj in list(all_configs):
                for requirement in cls.__requires__:
                    check = getattr(requirements, requirement)

                    if check.predicate(config_obj):
                        all_configs.remove(config_obj)
                        if check.reason:
                            reasons.append(check.reason)
                        break

        if cls.__unsupported_on__:
            spec = exclusions.db_spec(*cls.__unsupported_on__)
            for config_obj in list(all_configs):
                if spec(config_obj):
                    all_configs.remove(config_obj)

        if getattr(cls, '__only_on__', None):
            spec = exclusions.db_spec(*util.to_list(cls.__only_on__))
            for config_obj in list(all_configs):
                if not spec(config_obj):
                    all_configs.remove(config_obj)


        if getattr(cls, '__skip_if__', False):
            for c in getattr(cls, '__skip_if__'):
                if c():
                    raise SkipTest("'%s' skipped by %s" % (
                        cls.__name__, c.__name__)
                    )

        for db_spec, op, spec in getattr(cls, '__excluded_on__', ()):
            for config_obj in list(all_configs):
                if exclusions.skip_if(exclusions.SpecPredicate(db_spec, op, spec)).predicate(config_obj):
                    all_configs.remove(config_obj)


        if not all_configs:
            raise SkipTest(
                "'%s' unsupported on DB implementation %s%s" % (
                    cls.__name__,
                    ", ".join("'%s' = %s" % (config_obj.db.name, config_obj.db.dialect.server_version_info)
                        for config_obj in config._unique_configs()
                    ),
                    ", ".join(reasons)
                )
            )
        elif hasattr(cls, '__prefer__'):
            non_preferred = set()
            spec = exclusions.db_spec(*util.to_list(cls.__prefer__))
            for config_obj in all_configs:
                if not spec(config_obj):
                    non_preferred.add(config_obj)
            if all_configs.difference(non_preferred):
                all_configs.difference_update(non_preferred)

        if config._current not in all_configs:
            self._setup_config(all_configs.pop(), cls)

    def beforeTest(self, test):
        warnings.resetwarnings()
        profiling._current_test = test.id()

    def afterTest(self, test):
        engines.testing_reaper._after_test_ctx()
        warnings.resetwarnings()

    def _setup_config(self, config_obj, ctx):
        ctx.__use_config__ = config_obj

    def _setup_engine(self, ctx):
        if getattr(ctx, '__engine_options__', None):
            eng = engines.testing_engine(options=ctx.__engine_options__)
            config_obj = Config(eng, db_opts, options, file_config)
        elif getattr(ctx, '__use_config__', None):
            config_obj = ctx.__use_config__
        else:
            config_obj = None

        if config_obj:
            global _existing_config_obj
            _existing_config_obj = config._current
            config._current = config_obj
            config.db = testing.db = config_obj.db

    def _restore_engine(self, ctx):
        global _existing_config_obj
        if _existing_config_obj is not None:
            config.db = testing.db = _existing_config_obj.db
            config._current = _existing_config_obj
            _existing_config_obj = None

    def startContext(self, ctx):
        if not isinstance(ctx, type) \
            or not issubclass(ctx, fixtures.TestBase):
            return
        self._do_skips(ctx)
        self._setup_engine(ctx)

    def stopContext(self, ctx):
        if not isinstance(ctx, type) \
            or not issubclass(ctx, fixtures.TestBase):
            return
        engines.testing_reaper._stop_test_ctx()
        if not options.low_connections:
            assertions.global_cleanup_assertions()
        self._restore_engine(ctx)
