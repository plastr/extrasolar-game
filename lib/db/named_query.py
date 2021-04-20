# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# file named_query.py
# author Ryan Williams, Phoenix
# date 2007-07-31
#
# $LicenseInfo:firstyear=2007&license=mit$
#
# Copyright (c) 2007-2009, Linden Research, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# $/LicenseInfo$

"""
API for running named queries.

https://wiki.lindenlab.com/wiki/Named_Queries
"""

import json
import errno
import os
import re
import time
import uuid

import logging
logger = logging.getLogger(__name__)

DEBUG = True
# If not empty, only those named queries listed will have debugging messages.
# E.g. DEBUG_QUERIES = ('insert_message')
# If empty, debugging messages will be shown for all named queries.
DEBUG_QUERIES = ()

NAMED_QUERY_SUFFIX = ".nq"

def init_module(sql_debug_queries):
    global DEBUG
    DEBUG = sql_debug_queries

_g_named_manager = None
def _init_g_named_manager(sql_dir):
    """
    Initializes a global :class:`lldb.named_query.NamedQueryManager`
    object to point at a specified named queries hierarchy.

    This function is intended entirely for testing purposes, because
    it's tricky to control the config from inside a test.
    """
    global _g_named_manager
    _g_named_manager = NamedQueryManager(
        os.path.abspath(os.path.realpath(sql_dir)))

def get(name, schema = None):
    """
    Get the named query object to be used to perform queries on the
    given schema. Uses the module global
    :class:`lldb.named_query.NamedQueryManager` object to fetch
    the named query.

    :param name: The name of the query to run.
    :param schema: Specify an alternate query for a known non-default schema.
    :returns: Returns a class:`NamedQuery` instance.
    """
    if _g_named_manager is None:
        _init_g_named_manager('.')
    return _g_named_manager.get(name).for_schema(schema)

def sql(connection, name, params, schema = None):
    """
    Generate the SQL for the named query with params on the given
    connection. Uses the module global
    :class:`lldb.named_query.NamedQueryManager` object to fetch
    the named query.

    :param connection: The connection to use.
    :param name: The name of the query to run.
    :param params: The parameters passed into the query.
    :return: Returns the sql for use against the given connection.
    """
    return get(name, schema).sql(connection, params)

def run(connection, name, params, expect_rows = None):
    """
    Given a connection, run a named query with the params.

    :param connection: The connection to use.
    :param name: The name of the query to run.
    :param params: The parameters passed into the query.
    :param expect_rows: The number of rows expected. Set to 1 if
        return_as_map is True. Raises :exc:`lldb.named_query.ExpectationFailed`
        if the number of returned rows does not exactly match.
        Kind of a hack.
    :returns: Returns the result set as a list of dicts.

    Note that this function will fetch ALL rows.
    """
    return get(name).run(connection, params, expect_rows)

class ExpectationFailed(Exception):
    """
    Exception that is raised when an expectation for the results of an
    sql query is not met.
    """
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

class ImproperInvocation(Exception):
    """
    Exception raised when a named query is incorrectly invoked, eg
    empty array for an @ segment.
    """
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

class NamedQuery(object):
    """
    An instance of a :class:`lldb.named_query.NamedQuery` object
    encapsulates the sql, alternatives, file timeouts, sql constructrion
    rules for the Linden named query syntax.

    https://wiki.lindenlab.com/wiki/Named_Queries
    """
    def __init__(self, name, filename):
        """
        Construct a :class:`lldb.named_query.NamedQuery` object.
        
        :param name: an arbitrary name as a handle for the query
        :param filename: a path to a file or a file-like object
            containing an llsd named query document.
        """
        self._stat_interval_seconds = 5  # 5 seconds
        self._name = name
        self._location = filename
        self._alternative = dict()
        self._last_mod_time = 0
        self._last_check_time = 0
        self.deleted = False
        self.load_contents()

    def name(self):
        "The name of the query."
        return self._name

    def get_modtime(self):
        """Returns the mtime (last modified time) of the named query
        filename. For file-like objects, expect a modtime of 0"""
        if self._location and isinstance(self._location, (str, unicode)):
            return os.path.getmtime(self._location)
        return 0

    def load_contents(self):
        """Loads and parses the named query file into self. Does
        nothing if self.location is nonexistant."""
        if self._location:
            if isinstance(self._location, (str, unicode)):
                contents = json.loads(open(self._location).read())
            else:
                # we probably have a file-like object. Godspeed!
                contents = json.loads(self._location.read())
            self._reference_contents(contents)
            # Check for alternative implementations
            try:
                for name, alt in self._contents['alternative'].items():
                    nq = NamedQuery(name, None)
                    nq._reference_contents(alt)
                    self._alternative[name] = nq
            except KeyError:
                pass
            self._last_mod_time = self.get_modtime()
            self._last_check_time = time.time()

    def _reference_contents(self, contents):
        "Helper method which builds internal structure from parsed contents"
        self._contents = contents
        self._ttl = int(self._contents.get('ttl', 0))
        self._return_as_map = bool(self._contents.get('return_as_map', False))
        self._legacy_dbname = self._contents.get('legacy_dbname', None)

        # reset these before doing the sql conversion because we will
        # read them there. reset these while loading so we pick up
        # changes.
        self._around = set()
        self._append = set()
        self._integer = set()
        self._options = self._contents.get('dynamic_where', {})
        for key in self._options:
            if isinstance(self._options[key], basestring):
                self._options[key] = self._convert_sql(self._options[key])
            elif isinstance(self._options[key], list):
                lines = []
                for line in self._options[key]:
                    lines.append(self._convert_sql(line))
                self._options[key] = lines
            else:
                moreopt = {}
                for kk in self._options[key]:
                    moreopt[kk] = self._convert_sql(self._options[key][kk]) 
                self._options[key] = moreopt
        self._base_query = self._convert_sql(self._contents['base'])
        self._query_suffix = self._convert_sql(
            self._contents.get('query_suffix', ''))

    def _convert_sql(self, sql):
        """
        convert the parsed sql into a useful internal structure.

        This function has to turn the named query format into a pyformat
        style. It also has to look for %:name% and :name% and
        ready them for use in LIKE statements
        """
        if sql:
            #print >>sys.stderr, "sql:",sql
            
            # This first sub is to properly escape any % signs that
            # are meant to be literally passed through to mysql in the
            # query.  It leaves any %'s that are used for
            # like-expressions.
            expr = re.compile("(?<=[^a-zA-Z0-9_-])%(?=[^:])")
            sql = expr.sub('%%', sql)

            # This should tackle the rest of the %'s in the query, by
            # converting them to LIKE clauses.
            expr = re.compile("(%?):([a-zA-Z][a-zA-Z0-9_-]*)%")
            sql = expr.sub(self._prepare_like, sql)
            expr = re.compile("#:([a-zA-Z][a-zA-Z0-9_-]*)")
            sql = expr.sub(self._prepare_integer, sql)
            expr = re.compile(":([a-zA-Z][a-zA-Z0-9_-]*)")
            sql = expr.sub("%(\\1)s", sql)
        return sql

    def _prepare_like(self, match):
        """
        This function changes LIKE statement replace behavior

        It works by turning %:name% to %(_name_around)s and :name% to
        %(_name_append)s. Since a leading '_' is not a valid keyname
        input (enforced via unit tests), it will never clash with
        existing keys. Then, when building the statement, the query
        runner will generate corrected strings.
        """
        if match.group(1) == '%':
            # there is a leading % so this is treated as prefix/suffix
            self._around.add(match.group(2))
            return "%(" + self._build_around_key(match.group(2)) + ")s"
        else:
            # there is no leading %, so this is suffix only
            self._append.add(match.group(2))
            return "%(" + self._build_append_key(match.group(2)) + ")s"

    def _build_around_key(self, key):
        return "_" + key + "_around"

    def _build_append_key(self, key):
        return "_" + key + "_append"

    def _prepare_integer(self, match):
        """
        This function adjusts the sql for #:name replacements

        It works by turning #:name to %(_name_as_integer)s. Since a
        leading '_' is not a valid keyname input (enforced via unit
        tests), it will never clash with existing keys. Then, when
        building the statement, the query runner will generate
        corrected strings.
        """
        self._integer.add(match.group(1))
        return "%(" + self._build_integer_key(match.group(1)) + ")s"

    def _build_integer_key(self, key):
        return "_" + key + "_as_integer"

    def _strip_wildcards_to_list(self, value):
        """
        Take string, and strip out the LIKE special characters.

        Technically, this is database dependant, but postgresql and
        mysql use the same wildcards, and I am not aware of a general
        way to handle this. I think you need a sql statement of the
        form:

        LIKE_STRING( [ANY,ONE,str]... )

        which would treat ANY as their any string, and ONE as their
        single glyph, and str as something that needs database
        specific encoding to not allow any % or _ to affect the query.

        As it stands, I believe it's impossible to write a named query
        style interface which uses like to search the entire space of
        text available. Imagine the query:

        % of brain used by average linden

        In order to search for %, it must be escaped, so once you have
        escaped the string to not do wildcard searches, and be escaped
        for the database, and then prepended the wildcard you come
        back with one of:

        1) %\% of brain used by average linden
        2) %%% of brain used by average linden

        Then, when passed to the database to be escaped to be database
        safe, you get back:
        
        1) %\\% of brain used by average linden
        : which means search for any character sequence, followed by a
          backslash, followed by any sequence, followed by ' of
          brain...'
        2) %%% of brain used by average linden
        : which (I believe) means search for a % followed by any
          character sequence followed by 'of brain...'

        Neither of which is what we want!

        So, we need a vendor (or extention) for LIKE_STRING. Anyone
        want to write it?
        """
        if isinstance(value, unicode):
            utf8_value = value
        else:
            utf8_value = unicode(value, "utf-8")
        esc_list = []
        remove_chars = set(u"%_")
        for glyph in utf8_value:
            if glyph in remove_chars:
                continue
            esc_list.append(glyph.encode("utf-8"))
        return esc_list

    def delete(self):
        """Makes this query unusable by deleting all the members and
        setting the deleted member. This is desired when the on-disk
        query has been deleted but the in-memory copy remains."""
        # blow away all members except _name, _location, and deleted
        name, location = self._name, self._location
        for key in self.__dict__.keys():
            del self.__dict__[key]
        self.deleted = True
        self._name, self._location = name, location

    def ttl(self):
        """Estimated time to live of this query. Used for web
        services to set the Expires header."""
        return self._ttl

    def legacy_dbname(self):
        return self._legacy_dbname

    def return_as_map(self):
        """Returns true if this query is configured to return its
        results as a single map (as opposed to a list of maps, the
        normal behavior)."""
        
        return self._return_as_map

    def for_schema(self, db_name):
        "Look trough the alternates and return the correct query"
        if db_name is None:
            return self
        try:
            return self._alternative[db_name]
        except KeyError:
            pass
        return self

    def run(self, connection, params, expect_rows = None, use_dictcursor = False):
        """
        Given a connection, run a named query with the params.

        :param connection: The connection to use.
        :param name: The name of the query to run.
        :param params: The parameters passed into the query.
        :param expect_rows: The number of rows expected. Set to 1 if
            return_as_map is True. Raises ExpectationFailed if the
            number of returned rows does not exactly match. Kind of a
            hack.
        :param use_dictcursor: Set to false to use a normal cursor and
        :returns: Returns the result set as a list of dicts, or, if the
            named query has return_as_map set to true, returns a single
            dict.

        Note that this function will fetch ALL rows. We do this because it
        opens and closes the cursor to generate the values, and this 
        isn't a generator so the cursor has no life beyond the method call.
        """
        cursor = connection.cursor()

        if DEBUG:
            # Store the original UUID objects for debugging output.
            uuids = [(k,v) for k,v in params.iteritems() if isinstance(v, uuid.UUID)]

        # Prepare the query for execution.
        full_query, params = self._construct_sql(params)

        if DEBUG:
            # If there were UUIDs in the query parameters, convert them back to UUID instances.
            params_with_uuids = params.copy(); params_with_uuids.update(uuids)
            if len(DEBUG_QUERIES) == 0 or self.name() in DEBUG_QUERIES:
                logger.debug(u'Query [%s] SQL: %s', self.name(), full_query % params_with_uuids)

        # Execute the query.
        cursor.execute(full_query, params)

        # convert to dicts manually if we're not using a dictcursor
        if use_dictcursor:
            result_set = cursor.fetchall()
        else:
            if not cursor.description:
                # an insert or something
                cursor.close()
                return ()

            names = [x[0] for x in cursor.description]

            result_set = []
            for row in cursor.fetchall():
                converted_row = {}
                for idx, col_name in enumerate(names):
                    converted_row[col_name] = row[idx]
                result_set.append(converted_row)

        # *NOTE: the expect_rows argument is a very cheesy way to get some
        # validation on the result set.  If you want to add more expectation
        # logic, do something more object-oriented and flexible. Or use an ORM.
        rows = cursor.rowcount
        if(self._return_as_map):
            expect_rows = 1
        if expect_rows is not None and rows != expect_rows:
            cursor.close()
            raise ExpectationFailed("Statement expected %s rows, got %s.  Sql: '%s' %s" % (
                expect_rows, rows, full_query, params))

        cursor.close()
        if DEBUG:
            if len(DEBUG_QUERIES) == 0 or self.name() in DEBUG_QUERIES:
                logger.debug("Query [%s] Result: %s", self.name(), result_set)
        if self._return_as_map:
            return result_set[0]
        return result_set

    def _construct_sql(self, params):
        """ Returns a query string and a dictionary of parameters,
        suitable for directly passing to the execute() method."""
        self.refresh()

        # build the query from the options available and the params
        base_query = []
        base_query.append(self._base_query)
        #print >>sys.stderr, "base_query:",base_query
        for opt, extra_where in self._options.items():
            if type(extra_where) in (dict, list, tuple):
                if opt in params:
                    base_query.append(extra_where[params[opt]])
            else:
                if opt in params and params[opt]:
                    base_query.append(extra_where)
        if self._query_suffix:
            base_query.append(self._query_suffix)
        #print >>sys.stderr, "base_query:",base_query
        full_query = '\n'.join(base_query)

        # Go through the query and rewrite all of the ones with the
        # @:name syntax.
        rewrite = _RewriteQueryForArray(params)
        expr = re.compile("@%\(([a-zA-Z][a-zA-Z0-9_-]*)\)s")
        full_query = expr.sub(rewrite.operate, full_query)
        params.update(rewrite.new_params)

        # build out the params for like. We only have to do this
        # parameters which were detected to have ued the where syntax
        # during load.
        #
        # * treat the incoming string as utf-8
        # * strip wildcards
        # * append or prepend % as appropriate
        new_params = {}
        for key in params:
            # Fix for DEV-44731. Text below courtesy of Zero
            if isinstance(params[key], unicode):
                # Since many LL tables have UTF-8 data stored in columns in 
                # marked Latin1 - and the connections are thus also Latin1, 
                # we must be sure to never pass a unicode object to the 
                # MySQLdb module, because it will transcode into Latin1, which
                # isn't what we want. Hence, we expressly encode as UTF-8 here. 
                # NOTE: This continues to work even for tables where the columns
                # are set UTF-8 because in those cases the connections will be
                # UTF-8. In such cases, this code is just doing the encoding 
                # 'early'. 
                # BE WARNED: Other column encodings or connection encodings will
                # not work with this code.
                params[key] = params[key].encode('utf8')
            if isinstance(params[key], uuid.UUID):
                params[key] = params[key].bytes
            if key in self._around:
                new_value = ['%']
                new_value.extend(self._strip_wildcards_to_list(params[key]))
                new_value.append('%')
                new_params[self._build_around_key(key)] = ''.join(new_value)
            if key in self._append:
                new_value = self._strip_wildcards_to_list(params[key])
                new_value.append('%')
                new_params[self._build_append_key(key)] = ''.join(new_value)
            if key in self._integer:
                new_params[self._build_integer_key(key)] = int(params[key])
        params.update(new_params)

        return full_query, params

    def sql(self, connection, params, _debugging=False):
        """
        Generates an SQL statement from the named query document
        and a dictionary of parameters.

        **NOTE**: Only use for debugging, because it uses the
         non-standard MySQLdb ``literal`` method.
        """
        if not DEBUG and not _debugging:
            import warnings
            warnings.warn("Don't use named_query.sql() when not debugging.  Used on %s" % self._location)
        # do substitution using the mysql (non-standard) 'literal'
        # function to do the escaping.
        full_query, params = self._construct_sql(params)
        return full_query % connection.literal(params)
        

    def refresh(self):
        """
        Refresh self from the file on the filesystem.

        This is optimized to be callable as frequently as you wish,
        without adding too much load. It does so by only stat-ing the
        file every N seconds, where N defaults to 5 and is
        configurable through the member _stat_interval_seconds. If the stat
        reveals that the file has changed, refresh will re-parse the
        contents of the file and use them to update the named query
        instance. If the stat reveals that the file has been deleted,
        refresh will call self.delete to make the in-memory
        representation unusable.
        """
        now = time.time()
        if(now - self._last_check_time > self._stat_interval_seconds):
            self._last_check_time = now
            try:
                modtime = self.get_modtime()
                if(modtime > self._last_mod_time):
                    self.load_contents()
            except OSError, e:
                if e.errno == errno.ENOENT: # file not found
                    self.delete() # clean up self
                raise  # pass the exception along to the caller so they know that this query disappeared

class NamedQueryManager(object):
    """
    Manages the lifespan of :class:`lldb.named_query.NamedQuery` objects,
    drawing from a directory hierarchy of named query documents.

    In practice this amounts to a memory cache of
    :class:``lldb.named_query.NamedQuery`` objects.
    """
    def __init__(self, named_queries_dir, stat_interval_seconds=5):
        """Initializes a manager to look for named queries in a
        directory."""
        self._dir = os.path.abspath(os.path.realpath(named_queries_dir))
        self._cached_queries = {}
        self._stat_interval_seconds = stat_interval_seconds

    def sql(self, connection, name, params):
        nq = self.get(name)
        return nq.sql(connection, params)
        
    def get(self, name):
        """
        Returns a :class:`lldb.named_query.NamedQuery` instance based
        on the name, either from memory cache, or by parsing from disk.

        The name is simply a relative path to the directory associated
        with the manager object. Before returning the instance, the
        :class:`lldb.named_query.NamedQuery` object is cached in memory,
        so that subsequent accesses don't have to read from disk or do
        any parsing. This means that :class:`lldb.named_query.NamedQuery`
        objects returned by this method are shared across all users of
        the manager object. :meth:`lldb.named_query.NamedQuery.refresh()`
        is used to bring the :class:`lldb.named_query.NamedQuery` objects
        in sync with the actual files on disk.
        """
        nq = self._cached_queries.get(name)
        if nq is None:
            nq = NamedQuery(name, os.path.join(self._dir, name + NAMED_QUERY_SUFFIX))
            nq._stat_interval_seconds = self._stat_interval_seconds
            self._cached_queries[name] = nq
        else:
            try:
                nq.refresh()
            except OSError, e:
                if e.errno == errno.ENOENT: # file not found
                    del self._cached_queries[name]
                raise # pass exception along to caller so they know that the query disappeared

        return nq

class _RewriteQueryForArray(object):
    "Helper class for rewriting queries with the @:name syntax"
    def __init__(self, params):
        self.params = params
        self.new_params = dict()

    def operate(self, match):
        "Given a match, return the string that should be in use"
        key = match.group(1)
        value = self.params[key]
        if type(value) in (list,tuple):
            if len(value) == 0:
                # We raise this here because it will just generate ()
                # which is invalid SQL.
                raise ImproperInvocation(
                    'Empty list: %s' % (key,))
            rv = []
            for idx in range(len(value)):
                # if the value@idx is array-like, we are
                # probably dealing with a VALUES
                new_key = "_%s_%s"%(key, str(idx))
                val_item = value[idx]
                if type(val_item) in (list, tuple, dict):
                    if type(val_item) is dict:
                        # this is because in Python, the order of 
                        # key, value retrieval from the dict is not
                        # guaranteed to match what the input intended
                        # and for VALUES, order is important.
                        # TODO: Implemented ordered dict in LLSD parser?
                        raise ImproperInvocation(
                            'Only lists/tuples allowed, found dict in: %s'
                            % (key,))
                    values_keys = []
                    for value_idx, item in enumerate(val_item):
                        # we want a key of the format :
                        # key_#replacement_#value_row_#value_col
                        # ugh... so if we are replacing 10 rows in user_note, 
                        # the first values clause would read (for @:user_notes) :-
                        # ( :_user_notes_0_1_1,  :_user_notes_0_1_2, :_user_notes_0_1_3 )
                        # the input LLSD for VALUES will look like:
                        # <llsd>...
                        # <map>
                        #  <key>user_notes</key>
                        #      <array>
                        #      <array> <!-- row 1 for VALUES -->
                        #          <string>...</string>
                        #          <string>...</string>
                        #          <string>...</string>
                        #      </array>
                        # ...
                        #      </array>
                        # </map>
                        # ... </llsd>
                        values_key = "%s_%s"%(new_key, value_idx)
                        self.new_params[values_key] = item
                        values_keys.append("%%(%s)s"%values_key)
                    # now collapse all these new place holders enclosed in ()
                    # from [':_key_0_1_1', ':_key_0_1_2', ':_key_0_1_3,...] 
                    # rv will have [ '(:_key_0_1_1, :_key_0_1_2, :_key_0_1_3)', ]
                    # which is flattened a few lines below join(rv)
                    rv.append('(%s)' % ','.join(values_keys))
                else:
                    self.new_params[new_key] = val_item
                    rv.append("%%(%s)s"%new_key)
            return ','.join(rv)
        else:
            # not something that can be expanded, so just drop the
            # leading @ in the front of the match. This will mean that
            # the single value we have, be it a string, int, whatever
            # (other than dict) will correctly show up, eg:
            #
            # where foo in (@:foobar) -- foobar is a string, so we get
            # where foo in (:foobar)
            return match.group(0)[1:]
