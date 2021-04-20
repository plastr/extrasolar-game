# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os, collections
from front.lib.db import named_query

import logging
logger = logging.getLogger(__name__)

# The number of seconds before the connection socket times out per query.
CONNECTION_TIMEOUT = 5

# Default configuration for db connections.
UTC_TIMEZONE = "+00:00"
CHARSET = "utf8"
# Whether the connection will be set into SQL 'strict' mode. For MySQL
# this means TRADITIONAL and possibly innodb_strict_mode if supported.
SQL_STRICT_MODE = False
# After how many seconds should the named queries be refreshed from disk.
# Should be short internal in development, long in production.
STAT_INTERVAL_SECONDS = None

def init_module(sql_strict_mode, stat_interval_seconds):
    global SQL_STRICT_MODE, STAT_INTERVAL_SECONDS
    SQL_STRICT_MODE = sql_strict_mode
    STAT_INTERVAL_SECONDS = int(stat_interval_seconds)

class DatabaseError(Exception):
    """ Generic base Exception for database related errors. """

class UnexpectedResultError(DatabaseError):
    """ Raised when a query uses the incorrect db function. Should use db.run for queries with no results,
    db.row or db.rows when results are expected. """
    def __init__(self, query_name):
        details = "Query used unexpected database loading mechanism. query=[%s]" % query_name
        super(DatabaseError, self).__init__(details)

class TooFewRowsError(DatabaseError):
    """ Raised when a query is expected to return exactly one row and returns none. """
    def __init__(self, query_name):
        details = "Exactly one row expected from query, got 0 rows. query=[%s]" % query_name
        super(DatabaseError, self).__init__(details)

class TooManyRowsError(DatabaseError):
    """ Raised when a query is expected to return exactly one row and returns more. """
    def __init__(self, query_name, count):
        details = "Exactly one row expected from query, got %d. query=[%s]" % (count, query_name)
        super(DatabaseError, self).__init__(details)

class DatabaseMiddleware(object):
    """
    A WSGI middlware compatible object which wraps the WSGI application in a context manager
    which commits and closes any open database connections after the response has been generated,
    or if there are any exceptions, rollsback and closes the connections.
    """
    def __init__(self, app, config=None):
        self.app = app
        config = config or {}

    def __call__(self, environ, start_response):
        with commit_or_rollback(environ):
            return self.app(environ, start_response)

class conn(object):
    """
    Context manager for a connection, for use in a with statement.
    The main purpose of this context manager is to support sharding, by switching the
    "current connection" to point at the correct shard.
    NOTE: No rollback or commit will happen inside of this context manager.

    Use as::
        with db.conn(ctx) as ctx:
            db.run(ctx, "query_name...")

    The ctx parameter should be an object from which the context manager can derive the
    database configuration, e.g. the request object, a dict loaded from a .ini file,
    or a _CtxWrapper object.
    The optional timeout parameter is an integer expressing the number of seconds
    to set the underlying connection object to timeout after.
    NOTE: Timeout can only be used at the 'outer most' db.conn call, it has no
    effect if used after a connection has been opened for a given shard with a given
    ctx object. A warning log will be emitted if it is used in that manner.

    It supports nested commits by allowing an existing connection to be
    specified.  E.g.::
        with db.conn(ctx, timeout=10) as ctx:
            with db.conn(ctx) as ctx:
                db.run(ctx, "query_name...")
    """
    def __init__(self, ctx, timeout=None, user_id=None):
        # TODO JLP: Determine how to get the user_id or other shard key.
        shard_key = "opaque value"

        self.wrapped_ctx = _CtxWrapper.wrap(ctx)
        # Store the state of the context stack. Either of these may be None.
        self.old_key = self.wrapped_ctx.shard_key
        self.old_current_conn = self.wrapped_ctx.current_conn
        self.wrapped_ctx.shard_key = shard_key
        self.timeout = timeout

    def __enter__(self):
        self.wrapped_ctx.current_conn = connect(self.wrapped_ctx, timeout=self.timeout)
        return self.wrapped_ctx

    def __exit__(self, exception_type, value, tb):
        # Inform the wrapper that a nesting level was exited/popped.
        self.wrapped_ctx.pop_nesting(self.old_key, self.old_current_conn)

class commit_or_rollback(object):
    """
    Context manager for a committing or rolling back a database connection, for use in a with statement.
    Use as::
        with db.commit_or_rollback(ctx) as ctx:
            with db.conn(ctx) as ctx:
                db.run(ctx, "query_name...")

    The ctx parameter should be an object from which the context manager can derive the
    database configuration, e.g. the request object, a dict loaded from a .ini file,
    or a _CtxWrapper object.
    The context manager will call commit() and close() on all open connections before exiting if no
    exception has occurred, otherwise it will call rollback() and close().
    """
    def __init__(self, ctx):
        self.wrapped_ctx = _CtxWrapper.wrap(ctx)

    def __enter__(self):
        return self.wrapped_ctx

    def __exit__(self, exception_type, value, tb):
        # If there was no exception, commit the transaction.
        if exception_type is None:
            self.wrapped_ctx.commit_connections()
            self.wrapped_ctx.close_connections()
        # Otherwise, if type is not None there was an exception, rollback the transaction.
        elif exception_type is not None:
            try:
                self.wrapped_ctx.rollback_connections()
                self.wrapped_ctx.close_connections()
            except:
                # Run the rollback/close inside of a try/catch. If the rollback or close
                # fail (perhaps the DB connection has died) then log that inner exception but
                # raise the original exception so that the stack trace is clear.
                logger.exception("Exception occurred during rollback. Raising original exception.")
                raise exception_type, value, tb

def run(ctx, query_name, **args):
    """ Runs a named query with the specified arguments. If any result is returned an
    exception is raised. Intended to be used for INSERT, DELETE and similar queries.
    Will raise an assertion error if used for a query where results could be returned."""
    result = _run_query_by_name(ctx, query_name, **args)
    if not isinstance(result, tuple) or len(result) != 0:
        raise UnexpectedResultError(query_name)
    return result

def rows(ctx, query_name, **args):
    """The same as run but any results are returned as a list of dicts. Intended to be used
    for SELECT and similar queries. Will raise an assertion error if used for a query where no
    results could be returned."""
    result = _run_query_by_name(ctx, query_name, **args)
    if not isinstance(result, list):
        raise UnexpectedResultError(query_name)
    return result

def row(ctx, query_name, **args):
    """The same as run but specialized for queries that are expected to have exactly one result;
    it returns a single dict and raises an exception if fewer or more results were returned
    by the query."""
    result = rows(ctx, query_name, **args)
    row_count = len(result)
    if row_count == 0:
        raise TooFewRowsError(query_name)
    if row_count > 1:
        raise TooManyRowsError(query_name, row_count)
    return result[0]

_g_named_queries = None
def _run_query_by_name(ctx, query_name, **args):
    """ Runs a named query with the specified arguments, returns a list of dicts, one for each row."""
    global _g_named_queries
    if _g_named_queries is None:
        query_dir = os.path.join(os.path.dirname(__file__), "queries")
        _g_named_queries = named_query.NamedQueryManager(os.path.abspath(os.path.realpath(query_dir)), stat_interval_seconds=STAT_INTERVAL_SECONDS)

    wrapped_ctx = _CtxWrapper.wrap(ctx)
    assert wrapped_ctx.current_conn != None
    res = _g_named_queries.get(query_name).run(wrapped_ctx.current_conn, args)
    return res

def _run_query_string(ctx, query_string, **args):
    """
    Execute an ad-hoc named query on the given context.
    NOTE: This is a debug ONLY method, do NOT use this in production code.
    """
    query = _construct_adhoc_query(ctx, query_string, **args)
    wrapped_ctx = _CtxWrapper.wrap(ctx)
    assert wrapped_ctx.current_conn != None
    res = query.run(wrapped_ctx.current_conn, args)
    return res

def _compose_query_string(ctx, query_string, **args):
    """
    Return the SQL for an ad-hoc named query on the given context.
    NOTE: This is a debug ONLY method, do NOT use this in production code.
    """
    query = _construct_adhoc_query(ctx, query_string, **args)
    wrapped_ctx = _CtxWrapper.wrap(ctx)
    assert wrapped_ctx.current_conn != None
    return query.sql(wrapped_ctx.current_conn, args, _debugging=True)

def _construct_adhoc_query(ctx, query_string, **args):
    # Dummy up a JSON looking string and wrap it with a file-like object
    # so that it conforms to the NamedQuery API.
    query_string = '{"base": "' + query_string + '"}'
    import cStringIO
    query_io = cStringIO.StringIO(query_string)
    query = named_query.NamedQuery("adhoc_query", query_io)
    return query

def commit(ctx):
    """
    Commit any open transactions on all open connections in the given database context.
    This should be safe to call multiple times as it does not close connections.
    Generally this will only be used in tools type code, wrapped by a commit_or_rollback context
    manager where a given database change needs to be persisted, say in a for loop.
    Use as::
        with db.commit_or_rollback(ctx) as ctx:
            with db.conn(ctx) as ctx:
                rows = db.run(ctx, "query_name...")
                for r in rows:
                    db.run(ctx, "modify row...")
                    db.commit(ctx)
    """
    wrapped_ctx = _CtxWrapper.wrap(ctx)
    wrapped_ctx.commit_connections()

def rollback(ctx):
    """
    Rollback any open transactions on all open connections in the given database context.
    This should be safe to call multiple times as it does not close connections.
    Generally this will only be used in tools type code, wrapped by a commit_or_rollback context
    manager where a given database change needs to be rollback, say in a for loop where a caught
    exception has occurred.
    Use as::
        with db.commit_or_rollback(ctx) as ctx:
            with db.conn(ctx) as ctx:
                rows = db.run(ctx, "query_name...")
                for r in rows:
                    try:
                        db.run(ctx, "modify row...")
                        db.commit(ctx)
                    except Exception, e:
                        logging.exception(e)
                        db.rollback(ctx)
    """
    wrapped_ctx = _CtxWrapper.wrap(ctx)
    wrapped_ctx.rollback_connections()

def close_all_connections(ctx):
    """
    Close all open connections in the given database context.
    This is NOT safe to be called multiple times and should be used with extreme caution.
    Generally this will only be used in tools type code or unit testing where a wrapping
    commit_or_rollback context manager is not already available. Use that context manager
    whenever possible.
    Use as::
        with db.conn(ctx) as ctx:
            rows = db.run(ctx, "query_name...")
            db.commit(ctx)
            db.close_all_connections(ctx)
    """
    wrapped_ctx = _CtxWrapper.wrap(ctx)
    wrapped_ctx.close_connections()

def connect(ctx, timeout=None):
    """
    Returns a connection to the database.  Does some initial-setup
    too, though that's probably a bad design somehow.
    The optional timeout parameter is an integer expressing the number of seconds
    to set the underlying connection object to timeout after.
    NOTE: Timeout can only be used for the first connect() call for a given ctx/shard, it has no
    effect if used after a connection has been opened for a given shard with a given
    ctx object. A warning log will be emitted if it is used in that manner.
    """
    wrapped_ctx = _CtxWrapper.wrap(ctx)

    assert wrapped_ctx.shard_key != None
    # TODO JLP: Resolve the shard key down to a shardname here...
    shardname = wrapped_ctx.shard_key
    openconns = wrapped_ctx.open_connections

    if shardname in openconns:
        # Timeout can only be set when initially opening a connection
        if timeout != None:
            logger.warning("Attempted to set timeout on already opened connection, ignoring.")
        return openconns[shardname]
    else:
        if shardname in wrapped_ctx.seen_shards:
            logger.warning("Connection was already opened for shard. [%s]", shardname)

        dbconf = wrapped_ctx.dbconf
        # TODO JLP: Actually use shardname variable here to select hostname.
        conn = _connect(dbconf, dbname=_dbname(dbconf), connection_timeout=timeout)

        openconns[shardname] = conn
        wrapped_ctx.seen_shards.add(shardname)
        return conn

## Utility functions for direct database access. Intended for unit testing.
def create_database(config, apply_schema=False):
    dbname = _dbname(config)
    conn = _connect(config)
    curs = conn.cursor()
    curs.execute("CREATE DATABASE %s CHARACTER SET '%s'" % (dbname, CHARSET))

    if apply_schema:
        curs.execute("USE %s" % dbname)

        # Execute the schema update using an iterator to make sure all the
        # queries run.
        curs.execute(_schema())

        # mysql-connector-python version:
        # NOTE: This should work but does not
        #   for result in curs.execute(_schema(), multi=True):
        # for result in conn.cmd_query_iter(_schema()):
        #     pass

        # Wait for the schema to be installed.
        # while curs.execute("SHOW TABLES") == 0:
        #     pass

    curs.close()
    conn.commit()
    conn.close()
    # specifically returning nothing b/c things get weird if we reuse this conn

def destroy_database(config):
    """ Only use for unit testing. """
    dbname = _dbname(config)
    conn = _connect(config)
    curs = conn.cursor()
    curs.execute("DROP DATABASE IF EXISTS %s" % dbname)
    while curs.execute("SHOW DATABASES LIKE '%s'" % dbname) == 1:
        pass
    curs.close()
    conn.commit()
    conn.close()

def clear_database(config):
    """ Only use for unit testing. """
    dbname = _dbname(config)
    conn = _connect(config)
    curs = conn.cursor()
    curs.execute("SHOW DATABASES LIKE '%s'" % dbname)
    if not curs.fetchone():
        return

    curs.execute("USE %s" % dbname)
    curs.execute("SHOW TABLES")
    for t in curs.fetchall():
        if "_yoyo_migration" not in t[0]:
            curs.execute("TRUNCATE TABLE %s" % t[0])
    curs.close()
    conn.commit()
    conn.close()

def list_tables(config):
    """ Only use for unit testing. """
    conn = _connect(config, dbname=_dbname(config))
    curs = conn.cursor()
    tables = []
    curs.execute("SHOW TABLES")
    for t in curs.fetchall():
        tables.append(t)
    curs.close()
    conn.commit()
    conn.close()
    return tables

## Helpers for database migrations
# When creating custom migration code, be sure to pass all connection objects
# through this function before using them to setup common configuration
# options usually set by the db module.
# Optionally set use_strict to False to turn of sql strict mode.
# This should only be used for historical migrations.
def setup_migration_cursor(conn, use_strict=True):
    cursor = conn.cursor()
    # Set the timezone to be UTC.
    cursor.execute('SET time_zone = "' + UTC_TIMEZONE + '"')
    if SQL_STRICT_MODE and use_strict:
        _enable_strict_mode(cursor)
    return cursor

class _RowCache(object):
    """ The purpose of this class is to hold the rows returned by named queries to be optionally used by
        other parts of the system that have access to the ctx instead of running the queries again. The
        initial use case for this is to run single queries to load all of the data for a set of lazy loaded
        collections at once rather than executing all of their single lazy loading queries. """
    def __init__(self):
        self._seen_queries = set()
        self._cache = collections.defaultdict(list)

    def get_rows_from_query(self, query_name, *key_parts):
        """
        Returns any database rows (as a list of dicts) that were cached for the given named query.
        Returns None if no rows have been cached for this query.
        """
        # If this query has already had rows cached, then the default value for a key is an empty row list
        # because any key not in the cache did not have any database row data associated with it.
        if query_name in self._seen_queries:
            key = self._make_key(query_name, *key_parts)
            return self._cache.get(key, [])
        # Otherwise return None indicating this query has never been cached.
        else:
            return None

    def set_rows_from_query(self, ctx, key_func, query_name, **args):
        """
        Run the given named query and cache all the rows returned, ready to be retrieved with get_rows_from_query.
        key_func is a callable which is passed each loaded row in return and returns a sequence of str()able
        data which will be used when constructing the key to hold query results in the cache. So for instance
        this could return the database id field which would be appended to the query_name.
        **args are passed to the db.rows function as named query parameters.
        """
        if query_name in self._seen_queries:
            logger.warn("Row caching query data that was already cached [%s]", query_name)
        self._seen_queries.add(query_name)
        with conn(ctx) as ctx:
            for r in rows(ctx, query_name, **args):
                key = self._make_key(query_name, *key_func(r))
                self._cache[key].append(r)

    def _make_key(self, *key_parts):
        return "__".join((str(p) for p in key_parts))

class _CtxWrapper(object):
    """ The purpose of this class to wrap a database 'context' object and track information
        specific to database connections in that wrapped object. Examples of wrapped objects
        are the web Request object or a dict which is deserialized .ini file. This wrapper
        provides a consistent API regardless of how the tracked information is stored in the
        wrapped object."""

    # These properties are made available by this wrapper class, but the values are stored in
    # the wrapped context object. They are stored in the wrapped context with a _ prefix.
    # Note that these specific values need to persist beyond the lifetime of this _CtxWrapper
    # instance, so those values are pushed into the context that gets passed into the constructor.
    PROPERTIES = ['shard_key', 'current_conn', 'open_connections', 'seen_shards', 'row_cache']

    def __init__(self, ctx):
        # Determine where on the ctx object values can be stored into a dict. If the ctx
        # has an environ attribute then it is most likely a Request object and values will
        # be stored in the environ dict.
        if hasattr(ctx, 'environ'):
            self._storage = ctx.environ
        # Otherwise assume that values can be stored on the ctx object itself. An example would
        # be if database config data was loaded straight from the .ini file into a dict, 
        else:
            self._storage = ctx
        # Initialize the open connections list if it is not in the wrapped context.
        if not '_open_connections' in self._storage:
            self._storage['_open_connections'] = {}
        if not '_seen_shards' in self._storage:
            self._storage['_seen_shards'] = set()
        # Initialize a row cache for this context if it does not already exist.
        if not '_row_cache' in self._storage:
            self._storage['_row_cache'] = _RowCache()

    @classmethod
    def wrap(cls, ctx):
        """ Factory method. Wrap the given ctx object if it is not already wrapped. """
        if not isinstance(ctx, _CtxWrapper):
            return _CtxWrapper(ctx)
        else:
            return ctx

    def pop_nesting(self, old_key, old_current_conn):
        """ Called when a the context manager using this wrapper exists/pops out of a nesting level.
            Clears the shard_key and current_conn fields and then restores them from the provided
            values if they are not None, restoring the state at the next nesting level up."""
        del self._storage['_shard_key']
        del self._storage['_current_conn']
        if old_key:
            self.shard_key = old_key
        if old_current_conn:
            self.current_conn = old_current_conn

    def commit_connections(self):
        for connection in self.open_connections.itervalues():
            connection.commit()

    def rollback_connections(self):
        for connection in self.open_connections.itervalues():
            connection.rollback()

    def close_connections(self):
        for shardname, connection in self.open_connections.items():
            connection.close()
            del self._storage['_open_connections'][shardname]

    # Override attribute set and get access and pass through our wrapped attributes
    # to the underlying wrapped objects storage.
    def __getattr__(self, name):
        if name in self.PROPERTIES:
            return self._storage.get("_" + name)
        else:
            return super(_CtxWrapper, self).__getattribute__(name)

    def __setattr__(self, name, value):
        if name in self.PROPERTIES:
            self._storage["_" + name] = value
        else:
            super(_CtxWrapper, self).__setattr__(name, value)

    @property
    def dbconf(self):
        """On the request object the database config is inside of a dict under front.config."""
        if 'front.config' in self._storage:
            return self._storage['front.config']
        else:
            return self._storage

def _connect(config, dbname="", connection_timeout=None):
    # mysql-connector-python version:
    # from mysql import connector
    # if connection_timeout is None:
    #     connection_timeout = CONNECTION_TIMEOUT
    #
    # conn = connector.connect(user=config.get('database.username'),
    #                          passwd=config.get('database.password'),
    #                          host=config.get('database.host'),
    #                          db=dbname,
    #                          connection_timeout=connection_timeout,
    #                          buffered=True, time_zone=UTC_TIMEZONE)

    import MySQLdb
    if connection_timeout is None:
        connection_timeout = CONNECTION_TIMEOUT

    conn = MySQLdb.connect(user=config.get('database.username'),
                           passwd=config.get('database.password'),
                           host=config.get('database.host'),
                           db=dbname,
                           use_unicode=True, charset="utf8",
                           connect_timeout=connection_timeout,
                           init_command='SET time_zone = "' + UTC_TIMEZONE + '"')

    if SQL_STRICT_MODE:
        _enable_strict_mode(conn.cursor())
    return conn

def _enable_strict_mode(cursor):
    # NOTE: This only works on mysql 5.5+. Enable when all developer machines are 5.5+.
    # cursor.execute('SET SESSION innodb_strict_mode=ON')
    cursor.execute("SET SESSION sql_mode='TRADITIONAL'")
    return cursor

def _dbname(config):
    return config.get('database.name').replace('PID', str(os.getpid()))

def _schema():
    return open(os.path.join(os.path.dirname(__file__), "schema.sql")).read()
