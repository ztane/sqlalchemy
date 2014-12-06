from ..orm.query import QueryContext, Query
from ..orm import strategies, attributes, properties, \
    strategy_options, util as orm_util, interfaces, loading
from .. import log
from ..sql import util as sql_util, visitors
from .. import util


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

    def all(self):
        return list(self)


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


@log.class_logger
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
            return loading._load_on_ident_from_baked(q, ident_key)

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

        lazy_clause, params = self._simple_lazy_clause(state, passive=passive)

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

