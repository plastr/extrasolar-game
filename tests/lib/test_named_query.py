# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import mock
import os
import shutil
import tempfile
import unittest

import json

from front.lib.db import named_query

CASE_1 = { 'ttl':1234,
           'base':"""
           select last_name_id, name
           from user_last_name
           where open = 'Y'
           """
           }

CASE_2 = {'ttl':1234,
          'base':"""
          select last_name_id, name
          from user_last_name
          where open = 'Y'
          and (availability = 'public' or owner_id = :owner_id)
          """
          }

CASE_3 = {'ttl': 1234,
          'base':"""
          select last_name_id, name
          from user_last_name
          where open = 'Y'""",
          'dynamic_where':{
              'select_public': "and (availability = 'public' or owner_id = :owner_id)"
              }
          }

CASE_4 = {'ttl': 1234,
          'base':"""
          select last_name_id, name
          from user_last_name
          where open = 'Y'""",
          'dynamic_where':{
              'select_public':[
                  "and (availability = 'public' or owner_id = :owner_id)",
                  "and (availability = 'any' or owner_id = :owner_id)",
                  "and (availability = 'somethingelse' or owner_id = :owner_id)"
                  ]
              }
          }

CASE_5 = {'ttl': 1234,
          'base':"""
          select last_name_id, name
          from user_last_name
          where open = 'Y'""",
          'dynamic_where':{
              'select_public':{
                  'avail_public':"and (availability = 'public' or owner_id = :owner_id)",
                  'avail_any':"and (availability = 'any' or owner_id = :owner_id)",
                  'avail_somethingelse':"and (availability = 'somethingelse' or owner_id = :owner_id)",
                  'default':"and (availability = 'somecond' or owner_id = :owner_id"
                  }
              }
          }

CASE_6 = {'ttl': 1234,
          'return_as_map': True,
          'base':"""
          select username as first, last_name as last
          from user
          where agent_id = 'agent_id'""",
          'legacy_dbname':'indra',
          'alternative':{'indra': {
            'ttl': 4321,
            'return_as_map': True,
            'base':"""
            select u.username as first, l.name as last
            from user u, user_last_name l
            where u.agent_id = 'agent_id'
            and u.ast_name_id = l.last_name_id"""}}
          }

CASE_7 = {'ttl':1234,
          'base':"""
          select agent_id
          from user
          where username like :firstname%
          """
          }

CASE_8 = {'ttl':1234,
          'base':"""
          select agent_id
          from user
          where username like %:firstname%
          """
          }

CASE_9 = {'ttl':3600,
          'base':"""
        SELECT m.agent_id as agent_id,
                m.donated_square_meters as contribution, 
        IF(:agent_in_group = '0', 'unknown', DATE_FORMAT(u.last_login_date, :short_day_format)) as last_login,
        IF(:agent_in_group = '0', 0, HEX(m.agent_powers_mask)) as powers, 
                IFNULL(gr.title, g.member_title) as title,
                IF( urmo.agent_id IS NOT NULL, TRUE, FALSE) as is_owner
                FROM (user_groups_map m, user u, groups g)
                LEFT JOIN user_roles_map urm ON urm.role_id = m.title_role
                AND urm.agent_id = m.agent_id
                LEFT JOIN group_roles gr ON m.title_role = gr.role_id
                LEFT JOIN user_roles_map urmo ON g.owner_role = urmo.role_id AND urmo.agent_id = u.agent_id
                WHERE m.group_id = :group_id
                AND u.agent_id = m.agent_id
                AND u.enabled = 'Y'
                AND g.group_id = m.group_id""",
          'dynamic_where':{
              'agent_in_group':"""
AND m.agent_powers_mask & CONV(:gp_member_visible_in_dir,16,10)"""},
          'query_suffix':"GROUP BY u.agent_id"
          }

CASE_10 = {
    'ttl':1234,
    'base':"""
SELECT u.agent_id as agent_id,
  u.im_via_email as im_via_email,
  u.email as email,
  u.enabled as enabled,
  CONCAT(u.username, ' ', l.name) as name,
  u.limited_to_estate as limited_to_estate,
  u.god_level as god_level,
  u.inventory_host_name as inventory_host_name
FROM user u, user_last_name l 
WHERE u.last_name_id = l.last_name_id
AND u.agent_id in (@:id_list)"""
          }

CASE_11 = {
    'ttl':1234,
    'base':"""
SELECT c.classified_id, c.name, c.price_for_listing, c.enabled
FROM classified c 
WHERE c.enabled = 'Y'""",
    'query_suffix':"""
ORDER BY c.price_for_listing DESC, c.creation_date
LIMIT 101 OFFSET :query_start_row"""
          }

CASE_12 = {
    'ttl':1234,
    'base':"""
SELECT c.classified_id, c.name, c.price_for_listing, c.enabled
FROM classified c 
WHERE c.enabled = 'Y'""",
    'query_suffix':"""
ORDER BY c.price_for_listing DESC, c.creation_date
LIMIT 101 OFFSET #:query_start_row"""
          }

CASE_13 = {
    'ttl':1234,
    'base':"""
    REPLACE INTO user_note
    (agent_id, target_id, note)
    VALUES @:user_notes
    """
    }

class NamedQueryTestBase(unittest.TestCase):
    def setUp(self):
        named_query.DEBUG = True
        self.temp_sql_dir = tempfile.mkdtemp()
        self.dbh = mock.Mock()
        def _fake_escape(params):
            "simple db-like escape. does not handle everything correctly."
            if not params:
                return params
            db_params = {}
            for key, value in params.iteritems():
                if isinstance(value, basestring):
                    db_value = "'" + value.replace("'", '"') + "'"
                    db_value = db_value.decode('utf-8')
                elif value is None:
                    db_value = 'NULL'
                else:
                    db_value = str(value)
                db_params[key] = db_value
            return db_params
        self.dbh.literal = _fake_escape

    def tearDown(self):
        named_query.DEBUG = False
        shutil.rmtree(self.temp_sql_dir)

    def named_query_for(self, name, contents):
        tf = self.write_temp_sql(name, contents)
        return named_query.NamedQuery(name, tf)
        
    def write_temp_sql(self, name, contents):
        if (name is not None):
            name = name + '.nq'
        dirname = os.path.join(self.temp_sql_dir, os.path.dirname(name))
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        filename = os.path.join(self.temp_sql_dir, name)
        fp = open(filename, 'w')
        json.dump(contents, fp)
        fp.close()
        return filename

class StaticNamedQueryTester(NamedQueryTestBase):
    def test_initialization_of_named_query(self):
        nq = self.named_query_for('case_1', CASE_1)
        self.assertEqual(nq.ttl(), 1234)
        self.assertEqual(nq.return_as_map(), False)
        #self.assertEqual(nq.sql(self.dbh, {}), CASE_1['base'])

    def test_ttl_is_optional(self):
        nq = self.named_query_for('ttl_is_optional', {'base':'test'})
        self.assertEqual(nq.ttl(), 0)

    def test_dynamic_where_are_optional(self):
        nq = self.named_query_for('dynamic_where_is_optional', {'base':'test'})
        self.assertEqual(nq._options, {})

    def test_return_as_map_is_optional(self):
        nq = self.named_query_for('return_as_map_is_optional', {'base':'test'})
        self.assertEqual(nq.return_as_map(), False)

    def test_base_is_required(self):
        def should_fail():
            nq = self.named_query_for('base_is_required', {})
            self.assert_(False)
        self.assertRaises(KeyError, should_fail)

    def test_base_substitution(self):
        nq = self.named_query_for('case_2', CASE_2)
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG'})
        self.assert_("owner_id = 'ZOMG'" in sql)

        # negative test
        def should_fail():
            sql = nq.sql(self.dbh, {})
            self.assert_(False)
        self.assertRaises(KeyError, should_fail)

    def test_base_substitution_with_extra(self):
        nq = self.named_query_for('case_2', CASE_2)
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'agent_id':'WTFBBQ'})
        self.assert_("owner_id = 'ZOMG'" in sql)

    def test_dynamic_where_boolean_addition(self):
        nq = self.named_query_for('case_3', CASE_3)
        # make sure extra clause is not added
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG'})
        self.assert_('availability' not in sql)

        # For string substitution, false is interpreted as do not add.
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':False})
        self.assert_('availability' not in sql)

        # make sure extra clause is added
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':True})
        self.assert_('availability' in sql)

        # make sure there's a space in there
        self.assert_("'Y'and" not in sql)

    def test_dynamic_where_array_addition(self):
        nq = self.named_query_for('case_4', CASE_4)
        # make sure extra clause is not added
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG'})
        self.assert_('and' not in sql)

        # make sure appropriate clause is added
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':0})
        self.assert_("'public'" in sql)
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':False})
        self.assert_("'public'" in sql)

        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':1})
        self.assert_("'any'" in sql)
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':True})
        self.assert_("'any'" in sql)

        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':2})
        self.assert_("'somethingelse'" in sql)

        # throw an exception when index is out of bounds
        def should_fail():
            nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':3})
            self.assert_(False)
        self.assertRaises(IndexError, should_fail)

    def test_dynamic_where_map_addition(self):
        nq = self.named_query_for('case_5', CASE_5)
        # make sure extra clause is not added
        sql = nq.sql(self.dbh, {'owner_id':'ZOMG'})
        self.assert_('and' not in sql)

        # make sure appropriate clause is added
        sql = nq.sql(
            self.dbh,
            {'owner_id':'ZOMG', 'select_public':'avail_public'})
        self.assert_("'public'" in sql)

        sql = nq.sql(
            self.dbh, 
            {'owner_id':'ZOMG', 'select_public':'avail_any'})
        self.assert_("'any'" in sql)

        sql = nq.sql(
            self.dbh, 
            {'owner_id':'ZOMG', 'select_public':'avail_somethingelse'})
        self.assert_("'somethingelse'" in sql)

        sql = nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':'default'})
        self.assert_("'somecond'" in sql)

        # throw an exception when key isn't in dynamic_where map
        def should_fail():
            nq.sql(self.dbh, {'owner_id':'ZOMG', 'select_public':'bad_key'})
            self.assert_(False)
        self.assertRaises(KeyError, should_fail)

    def test_alternative(self):
        nq = self.named_query_for('case_6', CASE_6)
        self.assertEqual(nq.ttl(), 1234)
        self.assertEqual(nq.return_as_map(), True)
        self.assertEqual(nq.sql(self.dbh, {}), CASE_6['base'])
        alt = nq.for_schema('indra')
        self.assertEqual(alt.ttl(), 4321)
        self.assertEqual(alt.return_as_map(), True)
        self.assertEqual(
            alt.sql(self.dbh, {}), 
            CASE_6['alternative']['indra']['base'])

    def test_append_like(self):
        nq = self.named_query_for('case_7', CASE_7)
        sql = nq.sql(self.dbh, {'firstname':'phoe'})
        self.assertNotEqual(sql.find("like 'phoe%'"), -1)

        # this sucks, but we strip % and _ because of design flaws in
        # sql. see explination in named_query.py if you are
        # interested.
        sql = nq.sql(self.dbh, {'firstname':'%phoen'})
        self.assertNotEqual(sql.find("like 'phoen%'"), -1)
        sql = nq.sql(self.dbh, {'firstname':'p_hoen'})
        self.assertNotEqual(sql.find("like 'phoen%'"), -1)

    def test_append_like_unicode(self):
        # ensure that it doesn't blow up if the value is a Unicode object
        nq = self.named_query_for('case_7', CASE_7)
        sql = nq.sql(self.dbh, {'firstname':u'phoe'})
        self.assertNotEqual(sql.find("like 'phoe%'"), -1)

    def test_around_like(self):
        nq = self.named_query_for('case_8', CASE_8)
        sql = nq.sql(self.dbh, {'firstname':'hoeni'})
        self.assertNotEqual(sql.find("like '%hoeni%"), -1)

        # this sucks, but we strip % and _ because of design flaws in
        # sql. see explination in named_query.py if you are
        # interested.
        sql = nq.sql(self.dbh, {'firstname':'%phoen'})
        self.assertNotEqual(sql.find("like '%phoen%'"), -1)
        sql = nq.sql(self.dbh, {'firstname':'p_hoen'})
        self.assertNotEqual(sql.find("like '%phoen%"), -1)

    def test_around_like_latin1_as_unicode(self):
        nq = self.named_query_for('case_8', CASE_8)
        sql = nq.sql(self.dbh, {'firstname':u'hoeni'})
        self.assertNotEqual(sql.find("like '%hoeni%"), -1)
        sql = nq.sql(self.dbh, {'firstname':u'%phoen'})
        self.assertNotEqual(sql.find("like '%phoen%'"), -1)
        sql = nq.sql(self.dbh, {'firstname':u'p_hoen'})
        self.assertNotEqual(sql.find("like '%phoen%"), -1)

    def test_query_suffix_and_dynamic_where(self):
        nq = self.named_query_for('case_9', CASE_9)
        params = {
            'agent_in_group': False,
            'short_day_format': '%M-%D',
            'group_id': 'foobar',
            'gp_member_visible_in_dir':1}
            
        # make sure extra clause is not added, but query_suffix was added.
        sql = nq.sql(self.dbh, params)
        self.assert_('AND m.agent_powers_mask & CONV(' not in sql)
        self.assert_('GROUP BY u.agent_id' in sql)

        # now add the dynamic where, make sure it shows up, make sure
        # the suffix is still there and actually a suffix.
        params['agent_in_group'] = True
        sql = nq.sql(self.dbh, params)
        dwhere = sql.find('AND m.agent_powers_mask & CONV(')
        self.assert_(dwhere is not -1)
        qs = sql.find('GROUP BY u.agent_id')
        self.assert_(qs is not -1)
        self.assert_(qs > dwhere)

    def test_array_syntax(self):
        nq = self.named_query_for('case_10', CASE_10)
        self.assertRaises(KeyError, nq.sql, self.dbh, {})
        sql = nq.sql(self.dbh, {'id_list':'abcd'})
        self.assert_("('abcd')" in sql)
        sql = nq.sql(self.dbh, {'id_list':['abcd','efgh']})
        self.assert_("('abcd','efgh')" in sql)
        sql = nq.sql(self.dbh, {'id_list':('abcd','efgh')})
        self.assert_("('abcd','efgh')" in sql)
        # make sure it didn't save off some kind of state
        self.assertRaises(KeyError, nq.sql, self.dbh, {})
        sql = nq.sql(self.dbh, {'id_list':(None)})
        self.assert_("u.agent_id in (NULL)" in sql)
        sql = nq.sql(self.dbh, {'id_list':None})
        self.assert_("u.agent_id in (NULL)" in sql)
        sql = nq.sql(self.dbh, {'id_list':[None]})
        self.assert_("u.agent_id in (NULL)" in sql)

    def test_empty_array(self):
        def should_fail():
            sql = nq.sql(self.dbh, {'id_list':[]})
        nq = self.named_query_for('case_10', CASE_10)
        self.assertRaises(named_query.ImproperInvocation, should_fail)

    def test_bonus_array(self):
        # since empty_list is not in CASE_10, the named query runner
        # should ignore it even though it is empty.
        nq = self.named_query_for('case_10', CASE_10)
        sql = nq.sql(self.dbh, {'id_list':'abcd','empty_list':[]})
        self.assert_("('abcd')" in sql)

    def test_integer_escaping(self):
        nq = self.named_query_for('case_11', CASE_11)
        sql = nq.sql(self.dbh, {'query_start_row':0})
        self.assert_("OFFSET '0'" not in sql)
        self.assert_("OFFSET 0" in sql)

    def test_integer_binding(self):
        nq = self.named_query_for('case_12', CASE_12)
        sql = nq.sql(self.dbh, {'query_start_row':'0'})
        self.assert_("OFFSET '0'" not in sql)
        self.assert_("OFFSET 0" in sql)
        sql = nq.sql(self.dbh, {'query_start_row':1})
        self.assert_("OFFSET '1'" not in sql)
        self.assert_("OFFSET 1" in sql)

    def _test_values_clause(self, context):
        def _compare_main_sql(test_case, nq):
            flatten = lambda(s): s.replace('\n', ' ').replace('\t', '').split('VALUES')[0]
            sql_test_case = flatten(test_case)
            sql_nq = flatten(nq)
            self.assertEqual(sql_test_case, sql_nq)

        nq = self.named_query_for('case_13', CASE_13)
        sql = nq.sql(self.dbh, context)
        (main_sql, values_clause) = sql.split('VALUES')
        _compare_main_sql(CASE_13['base'], main_sql)
        import re
        expr = re.compile('(\(.+?\))')
        matches = expr.finditer(values_clause)
        self.assertNotEqual(matches, None)
        for match in matches: 
            values_clause = match.group(0)[1:-1].replace("'", '').split(',')
            if tuple(values_clause) not in context['user_notes'] and \
            values_clause not in context['user_notes']:
                self.assert_(False)

    def test_values_clause_using_list(self):
        nq_context = {'user_notes': [
                        ['ee6558b3-d060-490a-9ef3-65bc09eef2bb', 
                        '1799b39b-d6a3-4fec-baf6-0f7c8cc715a0', 
                        'rtgrftesfesfewf'], 
                        ['ee6558b3-d060-490a-9ef3-65bc09eef2bb', 
                        '313c6e30-0e5b-4140-9369-20aceef71907', 
                        'test'], 
                        ['ee6558b3-d060-490a-9ef3-65bc09eef2bb', 
                        '4c12658a-1379-4697-9a93-89156d7bc1ac', 
                        'etseteat'],
                        ]
                        }
        self._test_values_clause(nq_context)

    def test_values_clause_using_tuple(self):
        nq_context = {'user_notes': [
                        ('ee6558b3-d060-490a-9ef3-65bc09eef2bb', 
                                '1799b39b-d6a3-4fec-baf6-0f7c8cc715a0', 
                                'rtgrftesfesfewf'), 
                        ('ee6558b3-d060-490a-9ef3-65bc09eef2bb', 
                                '313c6e30-0e5b-4140-9369-20aceef71907', 
                                'test'), 
                        ('ee6558b3-d060-490a-9ef3-65bc09eef2bb', 
                                '4c12658a-1379-4697-9a93-89156d7bc1ac', 
                                'etseteat'),
                        ]}
        self._test_values_clause(nq_context)

    def test_values_clause_using_dict(self):
        def should_fail():
            nq_context = {'user_notes': [{'note': 'rtgrftesfesfewf', 'target_id': '1799b39b-d6a3-4fec-baf6-0f7c8cc715a0', 'agent_id': 'ee6558b3-d060-490a-9ef3-65bc09eef2bb'},]}
            sql = nq.sql(self.dbh, nq_context)
            self.assert_(False)

        # test passing in a map as a dict value in the @ syntax
        nq = self.named_query_for('case_13', CASE_13)
        self.assertRaises(named_query.ImproperInvocation, should_fail)

    def test_refresh(self):
        orig_query = "orig_query"
        new_query = "new_query"
        filename = self.write_temp_sql('timer', {'base':orig_query})
        # backdate it by a few seconds because the mtime granularity is too low
        os.utime(filename, (os.path.getatime(filename), os.path.getmtime(filename) - 5))
        
        nq = named_query.NamedQuery('timer', filename)
        self.assertEqual(nq._base_query, orig_query)

        # overwrite the file with new shit
        self.write_temp_sql('timer', {'base':new_query})
        # 1 million seconds will probably not have elapsed, so it shouldn't reload
        nq._stat_interval_seconds = 1000000
        nq.refresh()
        self.assertEqual(nq._base_query, orig_query)

        # now let's see if it reloads
        nq._stat_interval_seconds = 0
        nq.refresh()
        self.assertEqual(nq._base_query, new_query)

        # delete the file and see that the named query reflects that
        os.remove(filename)
        self.assertRaises(OSError, nq.refresh)
        self.assert_(nq.deleted)
        self.assertEqual(nq.name(), 'timer')
        self.assertEqual(nq._location, filename)
        self.assertRaises(AttributeError, lambda: nq._base)

    def test_refresh_long(self):
        # Create a manager with a stat time of a year in seconds, effectively ignoring the filesystem
        # once a query has been loaded.
        manager = named_query.NamedQueryManager(self.temp_sql_dir, stat_interval_seconds=31557600)

        orig_query = "orig_query"
        new_query = "new_query"
        filename = self.write_temp_sql('timer', {'base':orig_query})
        # backdate it by a few seconds because the mtime granularity is too low
        os.utime(filename, (os.path.getatime(filename), os.path.getmtime(filename) - 5))

        # Pull the query from the manager and verify it has the correct stat_interval_seconds.
        nq = manager.get('timer')
        self.assertEqual(nq._base_query, orig_query)
        self.assertEqual(nq._stat_interval_seconds, 31557600)

        # overwrite the file with new shit
        self.write_temp_sql('timer', {'base':new_query})
        # A year in seconds will probably not have elapsed, so it shouldn't reload, where reloading
        # would ordinarily result in an OSError since the file has been overwritten.
        nq.refresh()
        self.assertEqual(nq._base_query, orig_query)

        # delete the file and see that the named query is still cached
        os.remove(filename)
        self.assertEqual(nq._base_query, orig_query)
        nq.refresh()
        self.assertEqual(nq._base_query, orig_query)

    def test_literal_percent(self):
        query = "SELECT DATE_FORMAT( NOW(), '%h:%i' ) as time"
        nq = self.named_query_for('literal_percents', {'base':query})
        sql = nq.sql(self.dbh, {})
        self.assertEqual(sql, query)

if __name__ == '__main__':
    unittest.main()
