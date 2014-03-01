# testing/config.py
# Copyright (C) 2005-2014 the SQLAlchemy authors and contributors <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

requirements = None
db = None
dbs = {}
db_opts = None
_current = None
file_config = None

def _unique_configs():
    return set(dbs.values())