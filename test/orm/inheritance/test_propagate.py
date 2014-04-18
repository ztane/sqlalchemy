from sqlalchemy.testing import raises
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.testing.schema import Column, Table
from sqlalchemy.orm import (
    backref,
    mapper,
    Session,
    eagerload,
    relationship,
    configure_mappers
)
from sqlalchemy.testing import fixtures

class TestPropagateFlag(fixtures.MappedTest):

    @classmethod
    def define_tables(cls, metadata):
        Table('people', metadata,
            Column('person_id', Integer, primary_key=True,
                test_needs_autoincrement=True),
            Column('name', String(50)),
            Column('type', String(30)))

        Table('engineers', metadata,
            Column('person_id', Integer, ForeignKey('people.person_id'),
                primary_key=True),
            Column('status', String(30)),
            Column('engineer_name', String(50)),
            Column('primary_language', String(50)))

        Table('managers', metadata,
            Column('person_id', Integer, ForeignKey('people.person_id'),
                primary_key=True),
            Column('status', String(30)),
            Column('manager_name', String(50)))

        Table('people_versions', metadata,
            Column('id', Integer, ForeignKey('people.person_id'),
                primary_key=True),
            Column('version_id', Integer, primary_key=True))

        Table('engineer_versions', metadata,
            Column('id', Integer, ForeignKey('engineers.person_id'),
                primary_key=True),
            Column('version_id', Integer, primary_key=True))

    @classmethod
    def setup_mappers(cls):
        Person, Manager, Engineer, PersonVersion, EngineerVersion = \
            cls.classes.Person, cls.classes.Manager, cls.classes.Engineer, \
            cls.classes.PersonVersion, cls.classes.EngineerVersion
        people, engineers, managers, people_versions, engineer_versions = \
            cls.tables.people, cls.tables.engineers, cls.tables.managers, \
            cls.tables.people_versions, cls.tables.engineer_versions

        mapper(Person, people)
        mapper(Engineer, engineers, inherits=Person)
        mapper(Manager, managers, inherits=Person)

        mapper(PersonVersion, people_versions, properties={
                'entity': relationship(Person,
                            backref=backref("versions", propagate=False))
        })
        mapper(EngineerVersion, engineer_versions, properties={
                'entity': relationship(Engineer,
                            backref=backref("versions", propagate=False))
        })
        configure_mappers()

    @classmethod
    def setup_classes(cls):
        class Person(cls.Comparable):
            pass

        class Manager(Person):
            pass

        class Engineer(Person):
            pass

        class PersonVersion(cls.Comparable):
            pass

        class EngineerVersion(cls.Comparable):
            pass

    def test_non_propagated_relationships_are_not_inherited(self):
        Manager = self.classes.Manager
        with raises(
                AttributeError,
                "Concrete/non-propagated .*managers does not implement "
                "attribute 'versions' at the instance or class level."
        ):
            Manager.versions

    def test_non_propagated_relationship_in_join_clause(self):
        Manager = self.classes.Manager
        session = Session()
        with raises(
                AttributeError,
                "Concrete/non-propagated .*managers does not implement "
                "attribute 'versions' at the instance or class level."
        ):
            session.query(Manager).join(Manager.versions)

    def test_non_propagated_relationship_in_eagerload(self):
        Manager = self.classes.Manager
        session = Session()
        with raises(
                AttributeError,
                "Concrete/non-propagated .*managers does not implement "
                "attribute 'versions' at the instance or class level."
        ):
            session.query(Manager).join(eagerload(Manager.versions))


    # TODO: tests that demonstrate that the non-propagated attribute
    # works!  querying, loading, persistence, etc.

