from ..orm.query import QueryContext, Query


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
