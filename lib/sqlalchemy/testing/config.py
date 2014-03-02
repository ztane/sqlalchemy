# testing/config.py
# Copyright (C) 2005-2014 the SQLAlchemy authors and contributors <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

import collections

requirements = None
db = None
db_url = None
dbs = {}
db_opts = None
_current = None
file_config = None

class Config(object):
    def __init__(self, db, db_opts, options, file_config):
        self.db = db
        self.db_opts = db_opts
        self.options = options
        self.file_config = file_config

    _stack = collections.deque()

    @classmethod
    def register(cls, db, db_opts, options, file_config, namespace):
        """add a config as one of the global configs.

        If there are no configs set up yet, this config also
        gets set as the "_current".
        """
        cfg = Config(db, db_opts, options, file_config)

        global _current
        if not _current:
            cls.set_as_current(cfg, namespace)
        dbs[cfg.db.name] = cfg
        dbs[(cfg.db.name, cfg.db.dialect)] = cfg
        dbs[cfg.db] = cfg

    @classmethod
    def set_as_current(cls, config, namespace):
        global db, _current, db_url
        _current = config
        db_url = config.db.url
        namespace.db = db = config.db

    @classmethod
    def push_engine(cls, db, namespace):
        assert _current, "Can't push without a default Config set up"
        cls.push(
            Config(db, _current.db_opts, _current.options, _current.file_config),
            namespace
        )

    @classmethod
    def push(cls, config, namespace):
        cls._stack.append(_current)
        cls.set_as_current(config, namespace)

    @classmethod
    def reset(cls, namespace):
        if cls._stack:
            cls.set_as_current(cls._stack[0], namespace)
            cls._stack.clear()

def _unique_configs():
    return set(dbs.values())