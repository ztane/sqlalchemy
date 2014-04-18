from sqlalchemy.testing import raises
from sqlalchemy import testing
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.testing.schema import Column
from sqlalchemy.orm import (
    backref,
    clear_mappers,
    configure_mappers,
    create_session,
    eagerload,
    relationship,
    Session
)
from sqlalchemy.testing import fixtures


Base = None


class TestPropagateFlag(fixtures.MappedTest):
    @classmethod
    def setup(self):
        global Base
        Base = declarative_base(testing.db)

        class Employee(Base):
            __tablename__ = 'employee'
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            type = Column(String(50))

            __mapper_args__ = {
                'polymorphic_identity': 'employee', 'polymorphic_on': type
            }

            def __repr__(self):
                return "Ordinary person %s" % self.name

        class Engineer(Employee):
            __tablename__ = 'engineer'
            id = Column(Integer, ForeignKey('employee.id'), primary_key=True)
            status = Column(String(30))
            engineer_name = Column(String(30))
            primary_language = Column(String(30))

            __mapper_args__ = {
                'polymorphic_identity': 'engineer',
            }

            def __repr__(self):
                return "Engineer %s, status %s" % (self.name, self.status)

        class Manager(Employee):
            __tablename__ = 'manager'
            id = Column(Integer, ForeignKey('employee.id'), primary_key=True)
            status = Column(String(30))
            manager_name = Column(String(30))

            __mapper_args__ = {
                'polymorphic_identity': 'manager',
            }

            def __repr__(self):
                return "Manager %s, status %s, manager_name %s" % (
                    self.name, self.status, self.manager_name
                )

        class Version(Base):
            __abstract__ = True

            version_id = Column(Integer, primary_key=True)

        class EmployeeVersion(Version):
            __tablename__ = 'employee_version'

            id = Column(Integer, ForeignKey('employee.id'), primary_key=True)
            employee = relationship(
                Employee, backref=backref('versions', propagate=False)
            )

        class EngineerVersion(Version):
            __tablename__ = 'engineer_version'

            id = Column(Integer, ForeignKey('engineer.id'), primary_key=True)
            employee = relationship(
                Engineer, backref=backref('versions', propagate=False)
            )

        self.Employee = Employee
        self.Engineer = Engineer
        self.Manager = Manager
        configure_mappers()

    def teardown(self):
        clear_mappers()
        Session.close_all()

    def test_non_propagated_relationships_are_not_inherited(self):
        with raises(AttributeError):
            self.Manager.versions

    def test_non_propagated_relationship_in_join_clause(self):
        session = create_session()
        with raises(AttributeError):
            session.query(self.Manager).join(self.Manager.versions)

    def test_non_propagated_relationship_in_eagerload(self):
        session = create_session()
        with raises(AttributeError):
            session.query(self.Manager).join(eagerload(self.Manager.versions))
