from pymongo import Connection

from django.db.backends import BaseDatabaseWrapper, BaseDatabaseValidation
from django.db.backends.signals import connection_created
from django.contrib.mongodb.creation import DatabaseCreation
from django.contrib.mongodb.introspection import DatabaseIntrospection
from django.utils.importlib import import_module


class DatabaseFeatures(object):
    interprets_empty_strings_as_nulls = False
    sql_nulls = False
    related_fields_match_type = False


class DatabaseOperations(object):
    compiler_module = "django.contrib.mongodb.compiler"
    sql_ddl = False
    
    def __init__(self, connection):
        self._cache = {}
        self.connection = connection
    
    def max_name_length(self):
        return 254
    
    def value_to_db_datetime(self, value):
        return value

    # TODO: this is copy pasta, fix the abstractions in Ops
    def compiler(self, compiler_name):
        """
        Returns the SQLCompiler class corresponding to the given name,
        in the namespace corresponding to the `compiler_module` attribute
        on this backend.
        """
        if compiler_name not in self._cache:
            self._cache[compiler_name] = getattr(
                import_module(self.compiler_module), compiler_name
            )
        return self._cache[compiler_name]
    
    def flush(self, style, only_django=False):
        if only_django:
            tables = self.connection.introspection.django_table_names(only_existing=True)
        else:
            tables = self.connection.introspection.table_names()
        for table in tables:
            self.connection.db.drop_collection(table)
    
    def check_aggregate_support(self, aggregate):
        # TODO: this really should use the generic aggregates, not the SQL ones
        from django.db.models.sql.aggregates import Count
        return isinstance(aggregate, Count)

class DatabaseWrapper(BaseDatabaseWrapper):
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.features = DatabaseFeatures()
        self.ops = DatabaseOperations(self)
        self.creation = DatabaseCreation(self)
        self.validation = BaseDatabaseValidation(self)
        self.introspection = DatabaseIntrospection(self)
        self._connection = None
    
    @property
    def connection(self):
        if self._connection is None:
            self._connection = Connection(self.settings_dict["HOST"],
                self.settings_dict["PORT"] or None)
            connection_created.send(sender=self.__class__)
        return self._connection
    
    @property
    def db(self):
        return self.connection[self.settings_dict["NAME"]]

    def close(self):
        if self._connection is not None:
            self._connection.disconnect()
            self._connection = None
    
    
    ###########################
    # TODO: Transaction stuff #
    ###########################
    
    def _enter_transaction_management(self, managed):
        pass

    def _leave_transaction_management(self, managed):
        pass
    
    def _commit(self):
        pass
    
    def _rollback(self):
        pass
    
    def _savepoint(self, sid):
        pass
    
    def _savepoint_commit(self, sid):
        pass
