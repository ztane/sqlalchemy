.. module:: sqlalchemy.orm

=================
Mapping Columns
=================

Customizing Column Properties
==============================

The default behavior of :func:`~.orm.mapper` is to assemble all the columns in
the mapped :class:`.Table` into mapped object attributes, each of which are
named according to the name of the column itself (specifically, the ``key``
attribute of :class:`.Column`).  This behavior can be
modified in several ways.

.. _mapper_column_distinct_names:

Naming Columns Distinctly from Attribute Names
----------------------------------------------

A mapping by default shares the same name for a
:class:`.Column` as that of the mapped attribute - specifically
it matches the :attr:`.Column.key` attribute on :class:`.Column`, which
by default is the same as the :attr:`.Column.name`.

The name assigned to the Python attribute which maps to
:class:`.Column` can be different from either :attr:`.Column.name` or :attr:`.Column.key`
just by assigning it that way, as we illustrate here in a Declarative mapping::

    class User(Base):
        __tablename__ = 'user'
        id = Column('user_id', Integer, primary_key=True)
        name = Column('user_name', String(50))

Where above ``User.id`` resolves to a column named ``user_id``
and ``User.name`` resolves to a column named ``user_name``.

When mapping to an existing table, the :class:`.Column` object
can be referenced directly::

    class User(Base):
        __table__ = user_table
        id = user_table.c.user_id
        name = user_table.c.user_name

Or in a classical mapping, placed in the ``properties`` dictionary
with the desired key::

    mapper(User, user_table, properties={
       'id': user_table.c.user_id,
       'name': user_table.c.user_name,
    })

In the next section we'll examine the usage of ``.key`` more closely.

.. _mapper_automated_reflection_schemes:

Automating Column Naming Schemes from Reflected Tables
------------------------------------------------------

In the previous section :ref:`mapper_column_distinct_names`, we showed how
a :class:`.Column` explicitly mapped to a class can have a different attribute
name than the column.  But what if we aren't listing out :class:`.Column`
objects explicitly, and instead are automating the production of :class:`.Table`
objects using reflection (e.g. as described in :ref:`metadata_reflection_toplevel`)?
In this case we can make use of the :meth:`.DDLEvents.column_reflect` event
to intercept the production of :class:`.Column` objects and provide them
with the :attr:`.Column.key` of our choice::

    @event.listens_for(Table, "column_reflect")
    def column_reflect(inspector, table, column_info):
        # set column.key = "attr_<lower_case_name>"
        column_info['key'] = "attr_%s" % column_info['name'].lower()

With the above event, the reflection of :class:`.Column` objects will be intercepted
with our event that adds a new ".key" element, such as in a mapping as below::

    class MyClass(Base):
        __table__ = Table("some_table", Base.metadata,
                    autoload=True, autoload_with=some_engine)

If we want to qualify our event to only react for the specific :class:`.MetaData`
object above, we can check for it in our event::

    @event.listens_for(Table, "column_reflect")
    def column_reflect(inspector, table, column_info):
        if table.metadata is Base.metadata:
            # set column.key = "attr_<lower_case_name>"
            column_info['key'] = "attr_%s" % column_info['name'].lower()

.. _column_prefix:

Naming All Columns with a Prefix
--------------------------------

A quick approach to prefix column names, typically when mapping
to an existing :class:`.Table` object, is to use ``column_prefix``::

    class User(Base):
        __table__ = user_table
        __mapper_args__ = {'column_prefix':'_'}

The above will place attribute names such as ``_user_id``, ``_user_name``,
``_password`` etc. on the mapped ``User`` class.

This approach is uncommon in modern usage.   For dealing with reflected
tables, a more flexible approach is to use that described in
:ref:`mapper_automated_reflection_schemes`.


Using column_property for column level options
-----------------------------------------------

Options can be specified when mapping a :class:`.Column` using the
:func:`.column_property` function.  This function
explicitly creates the :class:`.ColumnProperty` used by the
:func:`.mapper` to keep track of the :class:`.Column`; normally, the
:func:`.mapper` creates this automatically.   Using :func:`.column_property`,
we can pass additional arguments about how we'd like the :class:`.Column`
to be mapped.   Below, we pass an option ``active_history``,
which specifies that a change to this column's value should
result in the former value being loaded first::

    from sqlalchemy.orm import column_property

    class User(Base):
        __tablename__ = 'user'

        id = Column(Integer, primary_key=True)
        name = column_property(Column(String(50)), active_history=True)

:func:`.column_property` is also used to map a single attribute to
multiple columns.  This use case arises when mapping to a :func:`~.expression.join`
which has attributes which are equated to each other::

    class User(Base):
        __table__ = user.join(address)

        # assign "user.id", "address.user_id" to the
        # "id" attribute
        id = column_property(user_table.c.id, address_table.c.user_id)

For more examples featuring this usage, see :ref:`maptojoin`.

Another place where :func:`.column_property` is needed is to specify SQL expressions as
mapped attributes, such as below where we create an attribute ``fullname``
that is the string concatenation of the ``firstname`` and ``lastname``
columns::

    class User(Base):
        __tablename__ = 'user'
        id = Column(Integer, primary_key=True)
        firstname = Column(String(50))
        lastname = Column(String(50))
        fullname = column_property(firstname + " " + lastname)

See examples of this usage at :ref:`mapper_sql_expressions`.

.. autofunction:: column_property

.. _include_exclude_cols:

Mapping a Subset of Table Columns
---------------------------------

Sometimes, a :class:`.Table` object was made available using the
reflection process described at :ref:`metadata_reflection` to load
the table's structure from the database.
For such a table that has lots of columns that don't need to be referenced
in the application, the ``include_properties`` or ``exclude_properties``
arguments can specify that only a subset of columns should be mapped.
For example::

    class User(Base):
        __table__ = user_table
        __mapper_args__ = {
            'include_properties' :['user_id', 'user_name']
        }

...will map the ``User`` class to the ``user_table`` table, only including
the ``user_id`` and ``user_name`` columns - the rest are not referenced.
Similarly::

    class Address(Base):
        __table__ = address_table
        __mapper_args__ = {
            'exclude_properties' : ['street', 'city', 'state', 'zip']
        }

...will map the ``Address`` class to the ``address_table`` table, including
all columns present except ``street``, ``city``, ``state``, and ``zip``.

When this mapping is used, the columns that are not included will not be
referenced in any SELECT statements emitted by :class:`.Query`, nor will there
be any mapped attribute on the mapped class which represents the column;
assigning an attribute of that name will have no effect beyond that of
a normal Python attribute assignment.

In some cases, multiple columns may have the same name, such as when
mapping to a join of two or more tables that share some column name.
``include_properties`` and ``exclude_properties`` can also accommodate
:class:`.Column` objects to more accurately describe which columns
should be included or excluded::

    class UserAddress(Base):
        __table__ = user_table.join(addresses_table)
        __mapper_args__ = {
            'exclude_properties' :[address_table.c.id],
            'primary_key' : [user_table.c.id]
        }

.. note::

   insert and update defaults configured on individual
   :class:`.Column` objects, i.e. those described at :ref:`metadata_defaults`
   including those configured by the ``default``, ``update``,
   ``server_default`` and ``server_onupdate`` arguments, will continue to
   function normally even if those :class:`.Column` objects are not mapped.
   This is because in the case of ``default`` and ``update``, the
   :class:`.Column` object is still present on the underlying
   :class:`.Table`, thus allowing the default functions to take place when
   the ORM emits an INSERT or UPDATE, and in the case of ``server_default``
   and ``server_onupdate``, the relational database itself maintains these
   functions.



.. _mapper_sql_expressions:

SQL Expressions as Mapped Attributes
=====================================

Attributes on a mapped class can be linked to SQL expressions, which can
be used in queries.

Using a Hybrid
--------------

The easiest and most flexible way to link relatively simple SQL expressions to a class is to use a so-called
"hybrid attribute",
described in the section :ref:`hybrids_toplevel`.  The hybrid provides
for an expression that works at both the Python level as well as at the
SQL expression level.  For example, below we map a class ``User``,
containing attributes ``firstname`` and ``lastname``, and include a hybrid that
will provide for us the ``fullname``, which is the string concatenation of the two::

    from sqlalchemy.ext.hybrid import hybrid_property

    class User(Base):
        __tablename__ = 'user'
        id = Column(Integer, primary_key=True)
        firstname = Column(String(50))
        lastname = Column(String(50))

        @hybrid_property
        def fullname(self):
            return self.firstname + " " + self.lastname

Above, the ``fullname`` attribute is interpreted at both the instance and
class level, so that it is available from an instance::

    some_user = session.query(User).first()
    print some_user.fullname

as well as usable wtihin queries::

    some_user = session.query(User).filter(User.fullname == "John Smith").first()

The string concatenation example is a simple one, where the Python expression
can be dual purposed at the instance and class level.  Often, the SQL expression
must be distinguished from the Python expression, which can be achieved using
:meth:`.hybrid_property.expression`.  Below we illustrate the case where a conditional
needs to be present inside the hybrid, using the ``if`` statement in Python and the
:func:`.sql.expression.case` construct for SQL expressions::

    from sqlalchemy.ext.hybrid import hybrid_property
    from sqlalchemy.sql import case

    class User(Base):
        __tablename__ = 'user'
        id = Column(Integer, primary_key=True)
        firstname = Column(String(50))
        lastname = Column(String(50))

        @hybrid_property
        def fullname(self):
            if self.firstname is not None:
                return self.firstname + " " + self.lastname
            else:
                return self.lastname

        @fullname.expression
        def fullname(cls):
            return case([
                (cls.firstname != None, cls.firstname + " " + cls.lastname),
            ], else_ = cls.lastname)

.. _mapper_column_property_sql_expressions:

Using column_property
---------------------

The :func:`.orm.column_property` function can be used to map a SQL
expression in a manner similar to a regularly mapped :class:`.Column`.
With this technique, the attribute is loaded
along with all other column-mapped attributes at load time.  This is in some
cases an advantage over the usage of hybrids, as the value can be loaded
up front at the same time as the parent row of the object, particularly if
the expression is one which links to other tables (typically as a correlated
subquery) to access data that wouldn't normally be
available on an already loaded object.

Disadvantages to using :func:`.orm.column_property` for SQL expressions include that
the expression must be compatible with the SELECT statement emitted for the class
as a whole, and there are also some configurational quirks which can occur
when using :func:`.orm.column_property` from declarative mixins.

Our "fullname" example can be expressed using :func:`.orm.column_property` as
follows::

    from sqlalchemy.orm import column_property

    class User(Base):
        __tablename__ = 'user'
        id = Column(Integer, primary_key=True)
        firstname = Column(String(50))
        lastname = Column(String(50))
        fullname = column_property(firstname + " " + lastname)

Correlated subqueries may be used as well.  Below we use the :func:`.select`
construct to create a SELECT that links together the count of ``Address``
objects available for a particular ``User``::

    from sqlalchemy.orm import column_property
    from sqlalchemy import select, func
    from sqlalchemy import Column, Integer, String, ForeignKey

    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

    class Address(Base):
        __tablename__ = 'address'
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('user.id'))

    class User(Base):
        __tablename__ = 'user'
        id = Column(Integer, primary_key=True)
        address_count = column_property(
            select([func.count(Address.id)]).\
                where(Address.user_id==id).\
                correlate_except(Address)
        )

In the above example, we define a :func:`.select` construct like the following::

    select([func.count(Address.id)]).\
        where(Address.user_id==id).\
        correlate_except(Address)

The meaning of the above statement is, select the count of ``Address.id`` rows
where the ``Address.user_id`` column is equated to ``id``, which in the context
of the ``User`` class is the :class:`.Column` named ``id`` (note that ``id`` is
also the name of a Python built in function, which is not what we want to use
here - if we were outside of the ``User`` class definition, we'd use ``User.id``).

The :meth:`.select.correlate_except` directive indicates that each element in the
FROM clause of this :func:`.select` may be omitted from the FROM list (that is, correlated
to the enclosing SELECT statement against ``User``) except for the one corresponding
to ``Address``.  This isn't strictly necessary, but prevents ``Address`` from
being inadvertently omitted from the FROM list in the case of a long string
of joins between ``User`` and ``Address`` tables where SELECT statements against
``Address`` are nested.

If import issues prevent the :func:`.column_property` from being defined
inline with the class, it can be assigned to the class after both
are configured.   In Declarative this has the effect of calling :meth:`.Mapper.add_property`
to add an additional property after the fact::

    User.address_count = column_property(
            select([func.count(Address.id)]).\
                where(Address.user_id==User.id)
        )

For many-to-many relationships, use :func:`.and_` to join the fields of the
association table to both tables in a relation, illustrated
here with a classical mapping::

    from sqlalchemy import and_

    mapper(Author, authors, properties={
        'book_count': column_property(
                            select([func.count(books.c.id)],
                                and_(
                                    book_authors.c.author_id==authors.c.id,
                                    book_authors.c.book_id==books.c.id
                                )))
        })

Using a plain descriptor
-------------------------

In cases where a SQL query more elaborate than what :func:`.orm.column_property`
or :class:`.hybrid_property` can provide must be emitted, a regular Python
function accessed as an attribute can be used, assuming the expression
only needs to be available on an already-loaded instance.   The function
is decorated with Python's own ``@property`` decorator to mark it as a read-only
attribute.   Within the function, :func:`.object_session`
is used to locate the :class:`.Session` corresponding to the current object,
which is then used to emit a query::

    from sqlalchemy.orm import object_session
    from sqlalchemy import select, func

    class User(Base):
        __tablename__ = 'user'
        id = Column(Integer, primary_key=True)
        firstname = Column(String(50))
        lastname = Column(String(50))

        @property
        def address_count(self):
            return object_session(self).\
                scalar(
                    select([func.count(Address.id)]).\
                        where(Address.user_id==self.id)
                )

The plain descriptor approach is useful as a last resort, but is less performant
in the usual case than both the hybrid and column property approaches, in that
it needs to emit a SQL query upon each access.

Changing Attribute Behavior
============================

.. _simple_validators:

Simple Validators
-----------------

A quick way to add a "validation" routine to an attribute is to use the
:func:`~sqlalchemy.orm.validates` decorator. An attribute validator can raise
an exception, halting the process of mutating the attribute's value, or can
change the given value into something different. Validators, like all
attribute extensions, are only called by normal userland code; they are not
issued when the ORM is populating the object::

    from sqlalchemy.orm import validates

    class EmailAddress(Base):
        __tablename__ = 'address'

        id = Column(Integer, primary_key=True)
        email = Column(String)

        @validates('email')
        def validate_email(self, key, address):
            assert '@' in address
            return address

.. versionchanged:: 1.0.0 - validators are no longer triggered within
   the flush process when the newly fetched values for primary key
   columns as well as some python- or server-side defaults are fetched.
   Prior to 1.0, validators may be triggered in those cases as well.


Validators also receive collection append events, when items are added to a
collection::

    from sqlalchemy.orm import validates

    class User(Base):
        # ...

        addresses = relationship("Address")

        @validates('addresses')
        def validate_address(self, key, address):
            assert '@' in address.email
            return address


The validation function by default does not get emitted for collection
remove events, as the typical expectation is that a value being discarded
doesn't require validation.  However, :func:`.validates` supports reception
of these events by specifying ``include_removes=True`` to the decorator.  When
this flag is set, the validation function must receive an additional boolean
argument which if ``True`` indicates that the operation is a removal::

    from sqlalchemy.orm import validates

    class User(Base):
        # ...

        addresses = relationship("Address")

        @validates('addresses', include_removes=True)
        def validate_address(self, key, address, is_remove):
            if is_remove:
                raise ValueError(
                        "not allowed to remove items from the collection")
            else:
                assert '@' in address.email
                return address

The case where mutually dependent validators are linked via a backref
can also be tailored, using the ``include_backrefs=False`` option; this option,
when set to ``False``, prevents a validation function from emitting if the
event occurs as a result of a backref::

    from sqlalchemy.orm import validates

    class User(Base):
        # ...

        addresses = relationship("Address", backref='user')

        @validates('addresses', include_backrefs=False)
        def validate_address(self, key, address):
            assert '@' in address.email
            return address

Above, if we were to assign to ``Address.user`` as in ``some_address.user = some_user``,
the ``validate_address()`` function would *not* be emitted, even though an append
occurs to ``some_user.addresses`` - the event is caused by a backref.

Note that the :func:`~.validates` decorator is a convenience function built on
top of attribute events.   An application that requires more control over
configuration of attribute change behavior can make use of this system,
described at :class:`~.AttributeEvents`.

.. autofunction:: validates

.. _mapper_hybrids:

Using Descriptors and Hybrids
-----------------------------

A more comprehensive way to produce modified behavior for an attribute is to
use :term:`descriptors`.  These are commonly used in Python using the ``property()``
function. The standard SQLAlchemy technique for descriptors is to create a
plain descriptor, and to have it read/write from a mapped attribute with a
different name. Below we illustrate this using Python 2.6-style properties::

    class EmailAddress(Base):
        __tablename__ = 'email_address'

        id = Column(Integer, primary_key=True)

        # name the attribute with an underscore,
        # different from the column name
        _email = Column("email", String)

        # then create an ".email" attribute
        # to get/set "._email"
        @property
        def email(self):
            return self._email

        @email.setter
        def email(self, email):
            self._email = email

The approach above will work, but there's more we can add. While our
``EmailAddress`` object will shuttle the value through the ``email``
descriptor and into the ``_email`` mapped attribute, the class level
``EmailAddress.email`` attribute does not have the usual expression semantics
usable with :class:`.Query`. To provide these, we instead use the
:mod:`~sqlalchemy.ext.hybrid` extension as follows::

    from sqlalchemy.ext.hybrid import hybrid_property

    class EmailAddress(Base):
        __tablename__ = 'email_address'

        id = Column(Integer, primary_key=True)

        _email = Column("email", String)

        @hybrid_property
        def email(self):
            return self._email

        @email.setter
        def email(self, email):
            self._email = email

The ``.email`` attribute, in addition to providing getter/setter behavior when we have an
instance of ``EmailAddress``, also provides a SQL expression when used at the class level,
that is, from the ``EmailAddress`` class directly:

.. sourcecode:: python+sql

    from sqlalchemy.orm import Session
    session = Session()

    {sql}address = session.query(EmailAddress).\
                     filter(EmailAddress.email == 'address@example.com').\
                     one()
    SELECT address.email AS address_email, address.id AS address_id
    FROM address
    WHERE address.email = ?
    ('address@example.com',)
    {stop}

    address.email = 'otheraddress@example.com'
    {sql}session.commit()
    UPDATE address SET email=? WHERE address.id = ?
    ('otheraddress@example.com', 1)
    COMMIT
    {stop}

The :class:`~.hybrid_property` also allows us to change the behavior of the
attribute, including defining separate behaviors when the attribute is
accessed at the instance level versus at the class/expression level, using the
:meth:`.hybrid_property.expression` modifier. Such as, if we wanted to add a
host name automatically, we might define two sets of string manipulation
logic::

    class EmailAddress(Base):
        __tablename__ = 'email_address'

        id = Column(Integer, primary_key=True)

        _email = Column("email", String)

        @hybrid_property
        def email(self):
            """Return the value of _email up until the last twelve
            characters."""

            return self._email[:-12]

        @email.setter
        def email(self, email):
            """Set the value of _email, tacking on the twelve character
            value @example.com."""

            self._email = email + "@example.com"

        @email.expression
        def email(cls):
            """Produce a SQL expression that represents the value
            of the _email column, minus the last twelve characters."""

            return func.substr(cls._email, 0, func.length(cls._email) - 12)

Above, accessing the ``email`` property of an instance of ``EmailAddress``
will return the value of the ``_email`` attribute, removing or adding the
hostname ``@example.com`` from the value. When we query against the ``email``
attribute, a SQL function is rendered which produces the same effect:

.. sourcecode:: python+sql

    {sql}address = session.query(EmailAddress).filter(EmailAddress.email == 'address').one()
    SELECT address.email AS address_email, address.id AS address_id
    FROM address
    WHERE substr(address.email, ?, length(address.email) - ?) = ?
    (0, 12, 'address')
    {stop}

Read more about Hybrids at :ref:`hybrids_toplevel`.

.. _synonyms:

Synonyms
--------

Synonyms are a mapper-level construct that allow any attribute on a class
to "mirror" another attribute that is mapped.

In the most basic sense, the synonym is an easy way to make a certain
attribute available by an additional name::

    class MyClass(Base):
        __tablename__ = 'my_table'

        id = Column(Integer, primary_key=True)
        job_status = Column(String(50))

        status = synonym("job_status")

The above class ``MyClass`` has two attributes, ``.job_status`` and
``.status`` that will behave as one attribute, both at the expression
level::

    >>> print MyClass.job_status == 'some_status'
    my_table.job_status = :job_status_1

    >>> print MyClass.status == 'some_status'
    my_table.job_status = :job_status_1

and at the instance level::

    >>> m1 = MyClass(status='x')
    >>> m1.status, m1.job_status
    ('x', 'x')

    >>> m1.job_status = 'y'
    >>> m1.status, m1.job_status
    ('y', 'y')

The :func:`.synonym` can be used for any kind of mapped attribute that
subclasses :class:`.MapperProperty`, including mapped columns and relationships,
as well as synonyms themselves.

Beyond a simple mirror, :func:`.synonym` can also be made to reference
a user-defined :term:`descriptor`.  We can supply our
``status`` synonym with a ``@property``::

    class MyClass(Base):
        __tablename__ = 'my_table'

        id = Column(Integer, primary_key=True)
        status = Column(String(50))

        @property
        def job_status(self):
            return "Status: " + self.status

        job_status = synonym("status", descriptor=job_status)

When using Declarative, the above pattern can be expressed more succinctly
using the :func:`.synonym_for` decorator::

    from sqlalchemy.ext.declarative import synonym_for

    class MyClass(Base):
        __tablename__ = 'my_table'

        id = Column(Integer, primary_key=True)
        status = Column(String(50))

        @synonym_for("status")
        @property
        def job_status(self):
            return "Status: " + self.status

While the :func:`.synonym` is useful for simple mirroring, the use case
of augmenting attribute behavior with descriptors is better handled in modern
usage using the :ref:`hybrid attribute <mapper_hybrids>` feature, which
is more oriented towards Python descriptors.   Technically, a :func:`.synonym`
can do everything that a :class:`.hybrid_property` can do, as it also supports
injection of custom SQL capabilities, but the hybrid is more straightforward
to use in more complex situations.

.. autofunction:: synonym

.. _custom_comparators:

Operator Customization
----------------------

The "operators" used by the SQLAlchemy ORM and Core expression language
are fully customizable.  For example, the comparison expression
``User.name == 'ed'`` makes usage of an operator built into Python
itself called ``operator.eq`` - the actual SQL construct which SQLAlchemy
associates with such an operator can be modified.  New
operations can be associated with column expressions as well.   The operators
which take place for column expressions are most directly redefined at the
type level -  see the
section :ref:`types_operators` for a description.

ORM level functions like :func:`.column_property`, :func:`.relationship`,
and :func:`.composite` also provide for operator redefinition at the ORM
level, by passing a :class:`.PropComparator` subclass to the ``comparator_factory``
argument of each function.  Customization of operators at this level is a
rare use case.  See the documentation at :class:`.PropComparator`
for an overview.

.. _mapper_composite:

Composite Column Types
=======================

Sets of columns can be associated with a single user-defined datatype. The ORM
provides a single attribute which represents the group of columns using the
class you provide.

.. versionchanged:: 0.7
    Composites have been simplified such that
    they no longer "conceal" the underlying column based attributes.  Additionally,
    in-place mutation is no longer automatic; see the section below on
    enabling mutability to support tracking of in-place changes.

.. versionchanged:: 0.9
    Composites will return their object-form, rather than as individual columns,
    when used in a column-oriented :class:`.Query` construct.  See :ref:`migration_2824`.

A simple example represents pairs of columns as a ``Point`` object.
``Point`` represents such a pair as ``.x`` and ``.y``::

    class Point(object):
        def __init__(self, x, y):
            self.x = x
            self.y = y

        def __composite_values__(self):
            return self.x, self.y

        def __repr__(self):
            return "Point(x=%r, y=%r)" % (self.x, self.y)

        def __eq__(self, other):
            return isinstance(other, Point) and \
                other.x == self.x and \
                other.y == self.y

        def __ne__(self, other):
            return not self.__eq__(other)

The requirements for the custom datatype class are that it have a constructor
which accepts positional arguments corresponding to its column format, and
also provides a method ``__composite_values__()`` which returns the state of
the object as a list or tuple, in order of its column-based attributes. It
also should supply adequate ``__eq__()`` and ``__ne__()`` methods which test
the equality of two instances.

We will create a mapping to a table ``vertice``, which represents two points
as ``x1/y1`` and ``x2/y2``. These are created normally as :class:`.Column`
objects. Then, the :func:`.composite` function is used to assign new
attributes that will represent sets of columns via the ``Point`` class::

    from sqlalchemy import Column, Integer
    from sqlalchemy.orm import composite
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

    class Vertex(Base):
        __tablename__ = 'vertice'

        id = Column(Integer, primary_key=True)
        x1 = Column(Integer)
        y1 = Column(Integer)
        x2 = Column(Integer)
        y2 = Column(Integer)

        start = composite(Point, x1, y1)
        end = composite(Point, x2, y2)

A classical mapping above would define each :func:`.composite`
against the existing table::

    mapper(Vertex, vertice_table, properties={
        'start':composite(Point, vertice_table.c.x1, vertice_table.c.y1),
        'end':composite(Point, vertice_table.c.x2, vertice_table.c.y2),
    })

We can now persist and use ``Vertex`` instances, as well as query for them,
using the ``.start`` and ``.end`` attributes against ad-hoc ``Point`` instances:

.. sourcecode:: python+sql

    >>> v = Vertex(start=Point(3, 4), end=Point(5, 6))
    >>> session.add(v)
    >>> q = session.query(Vertex).filter(Vertex.start == Point(3, 4))
    {sql}>>> print q.first().start
    BEGIN (implicit)
    INSERT INTO vertice (x1, y1, x2, y2) VALUES (?, ?, ?, ?)
    (3, 4, 5, 6)
    SELECT vertice.id AS vertice_id,
            vertice.x1 AS vertice_x1,
            vertice.y1 AS vertice_y1,
            vertice.x2 AS vertice_x2,
            vertice.y2 AS vertice_y2
    FROM vertice
    WHERE vertice.x1 = ? AND vertice.y1 = ?
     LIMIT ? OFFSET ?
    (3, 4, 1, 0)
    {stop}Point(x=3, y=4)

.. autofunction:: composite


Tracking In-Place Mutations on Composites
-----------------------------------------

In-place changes to an existing composite value are
not tracked automatically.  Instead, the composite class needs to provide
events to its parent object explicitly.   This task is largely automated
via the usage of the :class:`.MutableComposite` mixin, which uses events
to associate each user-defined composite object with all parent associations.
Please see the example in :ref:`mutable_composites`.

.. versionchanged:: 0.7
    In-place changes to an existing composite value are no longer
    tracked automatically; the functionality is superseded by the
    :class:`.MutableComposite` class.

.. _composite_operations:

Redefining Comparison Operations for Composites
-----------------------------------------------

The "equals" comparison operation by default produces an AND of all
corresponding columns equated to one another. This can be changed using
the ``comparator_factory`` argument to :func:`.composite`, where we
specify a custom :class:`.CompositeProperty.Comparator` class
to define existing or new operations.
Below we illustrate the "greater than" operator, implementing
the same expression that the base "greater than" does::

    from sqlalchemy.orm.properties import CompositeProperty
    from sqlalchemy import sql

    class PointComparator(CompositeProperty.Comparator):
        def __gt__(self, other):
            """redefine the 'greater than' operation"""

            return sql.and_(*[a>b for a, b in
                              zip(self.__clause_element__().clauses,
                                  other.__composite_values__())])

    class Vertex(Base):
        ___tablename__ = 'vertice'

        id = Column(Integer, primary_key=True)
        x1 = Column(Integer)
        y1 = Column(Integer)
        x2 = Column(Integer)
        y2 = Column(Integer)

        start = composite(Point, x1, y1,
                            comparator_factory=PointComparator)
        end = composite(Point, x2, y2,
                            comparator_factory=PointComparator)

