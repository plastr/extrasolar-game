# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import unittest
from datetime import datetime, timedelta
from front.models import chips

# Needed for 'time' parsing
from front.lib import utils

# Needed for rollback and database clearing.
from front.lib import db

## Implementation specific test helpers. These need to be implemented for the specific DB context
## and user implementations for the project using the chips system.
# Get a db compatible ctx object. Implementation specific.
def get_ctx():
    from front import read_config_and_init
    return read_config_and_init('test')
# Get a chips compatible user object. Implementation specific.
def get_user(ctx):
    from front.resource.auth import password
    with db.conn(ctx):
        new_id = password.insert_password_user(ctx, 'testuser@example.com', 'pw', 'FirstName', 'LastName')
        from front.models import user
        return user.user_from_context(ctx, new_id)
# Clear the database. Implementation specific.
def clear_database():
    db.clear_database(get_ctx())
## End implementation specific test helpers.

class TestModel(chips.Model):
    fields = frozenset(['f1'])
    id_field = 'test_id'

class TestCollection(chips.Collection):
    model_class = TestModel

class TestRoot(chips.Model):
    id_field = chips.RootId('root')
    fields = frozenset(['f'])
    collections = frozenset(['tc0'])
    def __init__(self, **params):
        super(TestRoot, self).__init__(tc0=TestCollection('tc0'), f="orig_value", **params)

class TestChipsModel(unittest.TestCase):
    def tearDown(self):
        clear_database()

    def test_set(self):
        t = TestModel(test_id='id1', f1='old_value')
        t.f1 = "new_value"
        self.assertEqual(t.f1, "new_value")
        def _set_foo():
            t.foo = "not_listed_field"
        self.assertRaises(chips.ChipsError, _set_foo)

        def _init_missing_field():
            TestModel(test_id='id1')
        self.assertRaises(chips.ChipsError, _init_missing_field)

    def test_to_struct(self):
        t = TestModel(test_id='id1', f1='old_value')
        self.assertEqual(t.to_struct(), {'test_id':'id1', 'f1':'old_value'})
        self.assertEqual(t.to_struct(fields=['test_id']), {'test_id':'id1'})

    def test_eq_and_hash(self):
        # Two models with the same id_field should be equal and hash to the same value.
        t1 = TestModel(test_id='id1', f1='old_value')
        t2 = TestModel(test_id='id1', f1='old_value')
        self.assertEqual(t1, t2)
        models = set([t1])
        self.assertEqual(len(models), 1)
        models.add(t2)
        self.assertEqual(len(models), 1)
        self.assertTrue(t1 in models)
        self.assertTrue(t2 in models)

    def test_pending_chips(self):
        t = TestModel(test_id='id1', f1='old_value')
        c = t._pending_chips()
        self.assertEqual(c, [])
        self.assertEqual(len(c), 0)

        r = TestRoot()
        c = r.tc0
        c.add(t)
        t.f1 = 'new_value'
        c = t._pending_chips()
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0],
            {'action': chips.MOD,
             'path': ['root', 'tc0', 'id1'],
             'value': {'test_id':'id1', 'f1':'new_value'},
             'time': c[0]['time']})

    def test_create(self):
        r = TestRoot()
        c = r.tc0
        t = c.create_child(test_id='id1', f1='orig_value')
        self.assertEqual(t.f1, 'orig_value')

        c = t._pending_chips()
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0],
            {'action': chips.ADD,
             'path': ['root', 'tc0', 'id1'],
             'value': {'test_id':'id1', 'f1':'orig_value'},
             'time': c[0]['time']})

    def test_delete(self):
        t = TestModel(test_id='id1', f1='old_value')
        self.assertEqual(len(t._pending_chips()), 0)
        r = TestRoot()
        c = r.tc0
        c.add(t)

        t.delete()
        chip = t._pending_chips()
        self.assertEqual(len(chip), 1)
        self.assertEqual(chip[0],
            {'action': chips.DELETE,
             'path': ['root', 'tc0', 'id1'],
             'value': {},
             'time': chip[0]['time']})

    def test_send_chips(self):
        with db.commit_or_rollback(get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = get_user(ctx)

                r = TestRoot()
                c = r.tc0
                t = c.create_child(test_id="id1", f1="derp")
                t.send_chips(ctx, user)
                since = datetime.utcnow() - timedelta(seconds=1)
                since = since.replace(microsecond=0)
                c = chips.get_chips(ctx, user, since, datetime.utcnow(), True)
                self.assertEqual(len(c), 1)
                self.assertEqual(c[0],
                    {'action': chips.ADD,
                     'path': ['root', 'tc0', 'id1'],
                     'transient': 1,
                     'value': {'test_id':'id1', 'f1':'derp'},
                     'time': c[0]['time']})

                t.f1 = "new_value"
                t.send_chips(ctx, user)
                c = chips.get_chips(ctx, user, since, datetime.utcnow(), True)
                self.assertEqual(len(c), 2)
                self.assertEqual(c[1],
                    {'action': chips.MOD,
                     'path': ['root', 'tc0', 'id1'],
                     'transient': 1,
                     'value': {'test_id':'id1', 'f1':'new_value'},
                     'time': c[1]['time']})

    def test_cid(self):
        r = TestRoot()
        c = r.tc0
        t = c.create_child(cid='cid0', f1='derp')
        self.assertEqual(t.get_id(), 'cid0')
        t.test_id = "test_id1"
        self.assertEqual(t.get_id(), 'test_id1')
        self.assert_(t.has_cid())
        c = t._pending_chips()
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0],
            {'action': chips.ADD,
             'path': ['root', 'tc0', 'cid0'],
             'value': {'test_id':'test_id1', 'f1':'derp'},
             'time': c[0]['time']})

        with db.commit_or_rollback(get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = get_user(ctx)
                t.send_chips(ctx, user)
                self.assertFalse(t.has_cid())

    def test_parent(self):
        reindex_called = [False]
        class TestParent(object):
            def _chip_path(self):
                return ['parent_id0']
            def _child_reindex(self, old_id, model):
                reindex_called[0] = (old_id, model.get_id())

        t = TestModel(test_id='id1', f1='derp')
        t._set_parent(TestParent())
        self.assertEqual(t._chip_path(), ['parent_id0', 'id1'])

        t.test_id = 'id2'
        self.assertEqual(t._chip_path(), ['parent_id0', 'id2'])
        self.assertEqual(reindex_called[0], ('id1', 'id2'))

    def test_unmanaged_fields(self):
        class TestUnmanagedModel(chips.Model):
            id_field = 'test_id'
            fields = frozenset(['f1', 'f2'])
            unmanaged_fields = frozenset(['f2'])

        # Test that both the constructor and the attribute assignement code paths do not assign
        # the model as the parent of any unmanaged fields.
        managed = TestModel.create(test_id="id1", f1="derp")
        unmanaged = TestModel.create(test_id="id2", f1="derp")
        parent = TestUnmanagedModel.create(test_id="parent_id1", f1=managed, f2=unmanaged)
        self.assertEqual(managed.parent, parent)
        self.assertEqual(unmanaged.parent, None)

        managed = TestModel.create(test_id="id1", f1="derp")
        unmanaged = TestModel.create(test_id="id2", f1="derp")
        parent = TestUnmanagedModel.create(test_id="parent_id1", f1=managed, f2=unmanaged)
        self.assertEqual(managed.parent, parent)
        self.assertEqual(unmanaged.parent, None)
        # Reparenting should raise an assertion error as it is not supported.
        def _set_managed():
            parent.f1 = managed
        self.assertRaises(AssertionError, _set_managed)
        # However, unmanaged fields do not have their parent field changed.
        parent.f2 = unmanaged

    # This test also tests the collection lazy loader.
    def test_server_only_fields(self):
        class TestServerOnlyModel(chips.Model):
            id_field = 'test_id'
            fields = frozenset(['f1', 'f2'])
            collections = frozenset(['tc0'])
            server_only_fields = frozenset(['f2', 'tc0'])
            def __init__(self, **params):
                super(TestServerOnlyModel, self).__init__(tc0=TestCollection.load_later('tc0', self._load_models), **params)
            def _load_models(self):
                return [dict(test_id="id1", f1="derp")]

        m = TestServerOnlyModel.create(test_id="id1", f1='client', f2='server')
        self.assertEqual(m.to_struct(), {'test_id':'id1', 'f1':'client'})
        # Verify that the collection was not lazy loaded as the collection should have been skipped
        # as it is a server_only_field
        self.assertFalse(m.tc0._loaded)
        self.assertEqual(len(m.tc0), 1)
        self.assertTrue(m.tc0._loaded)
        self.assertEqual(m.tc0['id1'].f1, 'derp')

    def test_lazy_field(self):
        class TestLazyFieldModel(chips.Model):
            id_field = chips.RootId('lazy_field_root')
            fields = frozenset(['f1', 'lazy_field'])
            lazy_field = chips.LazyField("lazy_field", lambda m: m._load_field())

            def _load_field(self):
                return "Lazy Loaded"

        m = TestLazyFieldModel(f1='value')
        self.assertEqual(m.lazy_field, 'Lazy Loaded')
        m.set_silent(lazy_field="Quiet Value")
        chip = m._pending_chips()
        self.assertEqual(len(chip), 0)
        m.lazy_field = "Loud Value"
        chip = m._pending_chips()
        self.assertEqual(len(chip), 1)
        self.assertEqual(chip[0],
            {'action': chips.MOD,
             'path': ['lazy_field_root'],
             'value': {'lazy_field':'Loud Value'},
             'time': chip[0]['time']})

    def test_lazy_field_unmanaged(self):
        class TestLazyFieldModel(chips.Model):
            id_field = chips.RootId('lazy_field_root')
            fields = frozenset(['f1', 'lazy_field', 'lazy_field_unmanaged'])
            lazy_field = chips.LazyField("lazy_field", lambda m: m._load_field())
            lazy_field_unmanaged = chips.LazyField("lazy_field_unmanaged", lambda m: m._load_field())
            unmanaged_fields = frozenset(['lazy_field_unmanaged'])
            def _load_field(self):
                return "Lazy Loaded"

        # Test that is is possible to set a model with a parent as a lazy field value
        # if its listed in unmanaged_fields
        r = TestRoot()
        c = r.tc0
        t = c.create_child(test_id='id1', f1='orig_value')
        m = TestLazyFieldModel(f1='value')
        # Assigning a model to an unmanaged lazy field should work.
        m.lazy_field_unmanaged = t
        m.set_silent(lazy_field_unmanaged=t)
        self.assertEqual(m.lazy_field_unmanaged, t)
        # If a lazy field is passed a model that has a parent and the lazy field is not listed in unmanaged_fields
        # then there is an assertion failure as there is no support for reparenting.
        self.assertRaises(AssertionError, m.set_silent, lazy_field=t)

    def test_root_obj(self):
        class TestSimpleRoot(chips.Model):
            id_field = chips.RootId('root')
            fields = frozenset(['f'])
            collections = frozenset(['tc1'])
        root = TestSimpleRoot(f='f', tc1=TestCollection('tc1'))
        self.assertEqual(root.to_struct(), {'f':'f', 'tc1':{}})
        self.assertEqual(root._chip_path(), ['root'])

        child = TestModel(test_id="f1", f1='derp')
        root.tc1.add(child)
        self.assertEqual(child._chip_path(), ['root', 'tc1', 'f1'])

    def test_single_child_model(self):
        class TestSimpleRoot(chips.Model):
            id_field = chips.RootId('root')
            fields = frozenset(['f', 'child'])
        class TestSimpleChild(chips.Model):
            id_field = 'child_id'
            fields = frozenset(['f'])

        child = TestSimpleChild(child_id='child', f='child_f')
        root = TestSimpleRoot(f='f', child=child)
        self.assertEqual(root.to_struct(), {'f':'f', 'child': {'child_id': 'child', 'f': 'child_f'}})
        self.assertEqual(root._chip_path(), ['root'])
        self.assertEqual(child._chip_path(), ['root', 'child'])

        child.f = 'new_value'
        chip = child._pending_chips()
        self.assertEqual(len(chip), 1)
        self.assertEqual(chip[0],
            {'action': chips.MOD,
             'path': ['root', 'child'],
             'value': {'child_id': 'child', 'f':'new_value'},
             'time': chip[0]['time']})

class TestChipsCollection(unittest.TestCase):
    def tearDown(self):
        clear_database()

    def test_constructor(self):
        c = TestCollection('tc0')
        self.assertEqual(len(c), 0)
        c = TestCollection('tc1', {'test_id':'t1', 'f1':'v1'}, {'test_id':'t2', 'f1':'v2'})
        self.assertEqual(len(c), 2)
        for k, v in c.iteritems():
            self.assert_(isinstance(v, TestModel))

    def test_create_child(self):
        r = TestRoot()
        c = r.tc0
        m = c.create_child(test_id='t1', f1='v1')
        self.assert_(isinstance(m, TestModel))
        self.assertEqual(len(c), 1)

    def test_delete_child(self):
        with db.commit_or_rollback(get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = get_user(ctx)

                # Delete from the collection should remove from collection.
                r = TestRoot()
                c = r.tc0
                m = c.create_child(test_id='t1', f1='v1')
                # Flush the add chip.
                m.send_chips(ctx, user)
                self.assertTrue(m in c)
                c.delete_child(m)
                self.assertFalse(m in c)
                # Should have a delete chip.
                chip = m._pending_chips()
                self.assertEqual(len(chip), 1)
                self.assertEqual(chip[0],
                    {'action': chips.DELETE,
                     'path': ['root', 'tc0', 't1'],
                     'value': {},
                     'time': chip[0]['time']})

                # Delete from the model instance should remove from collection.
                m = c.create_child(test_id='t2', f1='v1')
                # Flush the add chip.
                m.send_chips(ctx, user)
                self.assertTrue(m in c)
                m.delete()
                self.assertFalse(m in c)
                # Should have a delete chip.
                chip = m._pending_chips()
                self.assertEqual(len(chip), 1)
                self.assertEqual(chip[0],
                    {'action': chips.DELETE,
                     'path': ['root', 'tc0', 't2'],
                     'value': {},
                     'time': chip[0]['time']})

    def test_in(self):
        r = TestRoot()
        c = r.tc0
        m = c.create_child(test_id='t1', f1='v1')
        self.assert_(m in c)
        self.assert_(m.test_id in c)

    def test_reindex(self):
        r = TestRoot()
        c = r.tc0
        c.create_child(cid='cid0', f1='v1')
        self.assertEqual(len(c), 1)
        c['cid0'].test_id = 't1'
        self.assertEqual(len(c), 1)
        self.assert_('cid0' not in c)
        self.assert_('t1' in c)

    def test_paths(self):
        r = TestRoot()
        c = r.tc0
        c1 = TestCollection('tc1')
        c1._set_parent(c)
        self.assertEqual(c1._chip_path(), ['root', 'tc0', 'tc1'])

    def test_to_struct(self):
        c = TestCollection('tc1')
        c.create_child(test_id='t1', f1='v1')
        self.assertEqual(c.to_struct(),
            {'t1':{'test_id':'t1', 'f1':'v1'}})
        self.assertEqual(c.to_struct(fields=['f1']),
            {'t1':{'test_id':'t1', 'f1':'v1'}})
        self.assertRaises(chips.ChipsError, c.to_struct, fields=['bogus'])

class TestChipsInFuture(unittest.TestCase):
    def tearDown(self):
        clear_database()

    def test_add_in_future(self):
        with db.commit_or_rollback(get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = get_user(ctx)
                root = TestRoot()
                collection = root.tc0

                deliver_at = datetime.utcnow() + timedelta(minutes=10)
                deliver_at_micros = utils.usec_js_from_dt(deliver_at)

                params = {'test_id':'id1', 'f1':'orig_value'}
                model = chips.add_in_future(ctx, user, collection, deliver_at, **params)
                # Should not be in the collection.
                self.assertFalse(model in collection)
                # No chips should have been created now.
                c = chips.get_chips(ctx, user,
                    datetime.utcnow() - timedelta(minutes=1), datetime.utcnow(), True)
                self.assertEqual(len(c), 0)

                # Now get all chips 10 minutes in the future.
                c = chips.get_chips(ctx, user, deliver_at - timedelta(minutes=1), deliver_at, True)
                self.assertEqual(len(c), 1)
                self.assertEqual(c[0],
                    {'action': chips.ADD,
                     'path': ['root', 'tc0', 'id1'],
                     'transient': 1,
                     'value': {'test_id':'id1', 'f1':'orig_value'},
                     'time': deliver_at_micros})

    def test_modify_in_future(self):
        with db.commit_or_rollback(get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = get_user(ctx)
                root = TestRoot()
                collection = root.tc0

                model = collection.create_child(test_id='id1', f1='orig_value')
                model.send_chips(ctx, user)
                # Clear the immediate ADD chip.
                c = chips.get_chips(ctx, user,
                    datetime.utcnow() - timedelta(minutes=1), datetime.utcnow(), True)
                self.assertEqual(len(c), 1)

                deliver_at = datetime.utcnow() + timedelta(minutes=10)
                deliver_at_micros = utils.usec_js_from_dt(deliver_at)

                chips.modify_in_future(ctx, user, model, deliver_at, f1='new_value')
                # Now get all chips 10 minutes in the future.
                c = chips.get_chips(ctx, user, deliver_at - timedelta(minutes=1), deliver_at, True)
                self.assertEqual(len(c), 1)
                self.assertEqual(c[0],
                    {'action': chips.MOD,
                     'path': ['root', 'tc0', 'id1'],
                     'transient': 1,
                     'value': {'test_id':'id1', 'f1':'new_value'},
                     'time': deliver_at_micros})

                # Modifying an unknown field is an error.
                self.assertRaises(chips.ChipsError, chips.modify_in_future, ctx, user, model, deliver_at, bogus='bogus')

    def test_delete_in_future(self):
        with db.commit_or_rollback(get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = get_user(ctx)
                root = TestRoot()
                collection = root.tc0

                model = collection.create_child(test_id='id1', f1='orig_value')
                model.send_chips(ctx, user)
                # Clear the immediate ADD chip.
                c = chips.get_chips(ctx, user,
                    datetime.utcnow() - timedelta(minutes=1), datetime.utcnow(), True)
                self.assertEqual(len(c), 1)

                deliver_at = datetime.utcnow() + timedelta(minutes=10)
                deliver_at_micros = utils.usec_js_from_dt(deliver_at)

                chips.delete_in_future(ctx, user, model, deliver_at)
                # Now get all chips 10 minutes in the future.
                c = chips.get_chips(ctx, user, deliver_at - timedelta(minutes=1), deliver_at, True)
                self.assertEqual(len(c), 1)
                self.assertEqual(c[0],
                    {'action': chips.DELETE,
                     'path': ['root', 'tc0', 'id1'],
                     'transient': 1,
                     'value': {},
                     'time': deliver_at_micros})
