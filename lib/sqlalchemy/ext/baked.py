from ..orm.query import QueryContext, Query
from ..orm import strategies, attributes, properties, \
    strategy_options, util as orm_util, interfaces
from .. import log as sqla_log
from ..sql import util as sql_util
from ..orm import exc as orm_exc
from .. import util

import logging

log = logging.getLogger(__name__)


class BakedQuery(object):
    """an object that can produce a 'baked' Query, that is one where
    its ultimately generated SQL string is cached based on how the query
    has been constructed.

    """
    _bakery = {}
    _spoiled = False

    def __init__(self, initial_fn, args=(), bakery=None):
        if args:
            self._cache_key = tuple(args)
        else:
            self._cache_key = ()
        self.query = initial_fn()
        self._params = {}
        self._update_cache_key(initial_fn)
        self.steps = []
        if bakery is not None:
            self._bakery = bakery

    def _clone(self):
        b1 = BakedQuery.__new__(BakedQuery)
        b1.query = self.query
        b1._cache_key = self._cache_key
        b1.steps = list(self.steps)
        b1._bakery = self._bakery
        b1._params = dict(self._params)
        return b1

    def _update_cache_key(self, fn, args=()):
        self._cache_key += (
            fn.func_code.co_filename,
            fn.func_code.co_firstlineno) + args

    @classmethod
    def baked(cls, fn):
        def decorate(*args):
            return BakedQuery(fn, args)
        return decorate

    def bake(self, fn, *args):
        self._update_cache_key(fn, args)
        self.steps.append(fn)
        return self

    def spoil(self):
        """Cancel any query caching that will occur on this BakedQuery object.

        The BakedQuery can continue to be used normally, however when it
        actually iterates results, no caching will be used.

        This is to support the case where a particular step in constructing
        a baked query disqualifies the query from being cacheable, such
        as a variant that relies upon some uncacheable value.

        """
        self._spoiled = True
        return self

    def _bake_subquery_loaders(self, context):
        context.attributes['baked_queries'] = baked_queries = []
        for k, v in context.attributes.items():
            if isinstance(v, Query):
                if 'subquery' in k:
                    bk = BakedQuery(lambda *args: v)
                    bk._cache_key = self._cache_key + k
                    bk._bake()
                    baked_queries.append((k, bk._cache_key, v))
                del context.attributes[k]

    def _unbake_subquery_loaders(self, context):
        for k, cache_key, query in context.attributes["baked_queries"]:
            bk = BakedQuery(lambda: query.with_session(context.session))
            bk._params = self._params
            bk._cache_key = cache_key
            context.attributes[k] = bk

    def _bake(self):
        log.debug("baking")
        query = self.as_query(params=False)
        context = query._compile_context()
        self._bake_subquery_loaders(context)
        del context.session
        del context.query
        self._bakery[self._cache_key] = context

    def params(self, **kw):
        self._params.update(kw)
        return self

    def as_query(self, params=True):
        query = self.query
        for step in self.steps:
            query = step(query)
        if params and self._params:
            query = query.params(**self._params)
        return query

    def __iter__(self):
        if self._spoiled:
            return iter(self.as_query())

        if self._cache_key not in self._bakery:
            self._bake()

        query = self.query

        query._execution_options = query._execution_options.union(
            {"compiled_cache": self._bakery}
        )
        baked_context = self._bakery[self._cache_key]
        context = QueryContext.__new__(QueryContext)
        context.__dict__.update(baked_context.__dict__)
        context.query = query
        context.session = query.session
        context.attributes = context.attributes.copy()

        self._unbake_subquery_loaders(context)

        context.statement.use_labels = True
        if context.autoflush and not context.populate_existing:
            query.session._autoflush()
        return query.params(self._params)._execute_and_instances(context)

    def first(self):
        baked = self._clone()
        baked.bake(lambda q: q.slice(0, 1))
        ret = list(baked)
        if len(ret) > 0:
            return ret[0]
        else:
            return None

    def all(self):
        return list(self)

    def get(self, ident):
        return self.as_query()._get_impl(ident, self._load_on_ident)

    def _load_on_ident(self, query, key):
        """Load the given identity key from the database."""

        ident = key[1]

        baked = self._clone()

        mapper = query._mapper_zero()

        _get_clause, _get_params = mapper._get_clause

        def setup(query):
            _lcl_get_clause = _get_clause
            q = query._clone()
            q._get_condition()
            q._order_by = None

            # None present in ident - turn those comparisons
            # into "IS NULL"
            if None in ident:
                nones = set([
                    _get_params[col].key for col, value in
                    zip(mapper.primary_key, ident) if value is None
                ])
                _lcl_get_clause = sql_util.adapt_criterion_to_null(
                    _lcl_get_clause, nones)

            _lcl_get_clause = q._adapt_clause(_lcl_get_clause, True, False)
            q._criterion = _lcl_get_clause
            return q

        # cache the query against a key that includes
        # which positions in the primary key are NULL
        # (remember, we can map to an OUTER JOIN)
        baked.bake(setup, tuple(elem is None for elem in ident))

        params = dict([
            (_get_params[primary_key].key, id_val)
            for id_val, primary_key in zip(ident, mapper.primary_key)
        ])

        baked.params(**params)

        result = self.all()
        l = len(result)
        if l > 1:
            raise orm_exc.MultipleResultsFound()
        elif l:
            return result[0]
        else:
            return None


def bake_lazy_loaders():
    properties.RelationshipProperty.strategy_for(
        lazy="select")(BakedLazyLoader)
    properties.RelationshipProperty.strategy_for(
        lazy=True)(BakedLazyLoader)


def unbake_lazy_loaders():
    properties.RelationshipProperty.strategy_for(
        lazy="select")(strategies.LazyLoader)
    properties.RelationshipProperty.strategy_for(
        lazy=True)(strategies.LazyLoader)


@sqla_log.class_logger
@properties.RelationshipProperty.strategy_for(lazy="baked_select")
class BakedLazyLoader(strategies.LazyLoader):

    def _emit_lazyload(self, session, state, ident_key, passive):

        q = BakedQuery(
            lambda: session.query(self.mapper),
            bakery=self.mapper._compiled_cache)
        q.bake(
            lambda q: q._adapt_all_clauses()._with_invoke_all_eagers(False),
            self.parent_property)

        if not self.parent_property.bake_queries:
            q.spoil()

        if self.parent_property.secondary is not None:
            q.bake(
                lambda q:
                q.select_from(self.mapper, self.parent_property.secondary))

        pending = not state.key

        # don't autoflush on pending
        if pending or passive & attributes.NO_AUTOFLUSH:
            q.bake(lambda q: q.autoflush(False))

        if state.load_path:
            q.spoil()
            q.bake(
                lambda q:
                q._with_current_path(state.load_path[self.parent_property]))

        if state.load_options:
            q.spoil()
            q.bake(lambda q: q._conditional_options(*state.load_options))

        if self.use_get:
            return q._load_on_ident(q.query, ident_key)

        if self.parent_property.order_by:
            q.bake(
                lambda q:
                q.order_by(*util.to_list(self.parent_property.order_by)))

        for rev in self.parent_property._reverse_property:
            # reverse props that are MANYTOONE are loading *this*
            # object from get(), so don't need to eager out to those.
            if rev.direction is interfaces.MANYTOONE and \
                rev._use_get and \
                    not isinstance(rev.strategy, strategies.LazyLoader):
                q.bake(
                    lambda q:
                    q.options(
                        strategy_options.Load(rev.parent).lazyload(rev.key)))

        lazy_clause, params = self._generate_lazy_clause(state, passive)

        if pending:
            if orm_util._none_set.intersection(params.values()):
                return None

        q.bake(lambda q: q.filter(lazy_clause))
        q.params(**params)

        result = q.all()
        if self.uselist:
            return result
        else:
            l = len(result)
            if l:
                if l > 1:
                    util.warn(
                        "Multiple rows returned with "
                        "uselist=False for lazily-loaded attribute '%s' "
                        % self.parent_property)

                return result[0]
            else:
                return None
