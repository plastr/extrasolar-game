# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
Chips are means of communicating state changes between the client and the 
server. They represent deltas to a well-defined tree of data.

 A Chip row in the database is the following:
 * user_id -- id of the user who should see this chip
 * transient -- IGNORE FOR NOW
 * time -- server time when the chip should become available to the user
 * content -- which is a JSON string
 ** action: "m" = modify, "a" = add, "d" = delete
 ** path: a list that specifies a traversal through the tree of the user's data e.g. ["user", "missions", "TUT1a-0946a6b1eff950b3f8b83a68808d7917"] 
 ** value: the value of the thingy at that tree node, e.g. {'mission_id':12345, 'done':true, ....} 

 Example chip content:
 {"action": "a", 
  "path": ["user", "missions", "00001"],  <-- Client ID if this ID differs from value ID.
  "value": {'mission_id':12345, 'done':true, ....},
  "time": datetime.datetime(2011, 2, 1)}


 Server model creation workflow:
 * create structure:   {'foo_id': 1234, 'field':'blah'}
 * add chip {'action':'a', 'path':['user','thing',1234], 'value':{'foo_id': 1234, 'field':'blah'}}
 
 Client model creation workflow:
 * create structure with client id:   {'client_id': 0001, 'field':'blah'}
 * POST to server
 * server generates ID (4567), modifying structure
 * server adds chip: {'action':'a', 'path':['user','thing',0001], 'value':{'foo_id': 4567, 'field':'blah'}}
 * client reads chip, navigates to node in tree via path
 * client sets id on model, reindexes into tree at id 4567
 
 
 Note that this module uses the convention of prefixing non-API methods and 
 properties with '_'.  Users of the classes not have to use any '_' 
 methods or properties, if I've done my job right.
 """

from front.lib import db, xjson, gametime, utils

MOD = 'm'
ADD = 'a'
DELETE = 'd'

class ChipsError(Exception):
    """ Generic base Exception for chips related errors. """

def update_response(ctx, user, response, last_seen_chip_time):
    """
    This sticks any pending chips for the user onto a response object.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param response: Outgoing response object, must be a dict or else.
    :param last_seen_chip_time: datetime object that specifies the time of the last chip the client has seen
     (should be in the request)
    """
    unseen_chips = get_chips(ctx, user, last_seen_chip_time, gametime.now(), True)
    if unseen_chips:
        response['chips'] = unseen_chips
    return response


def send(ctx, user, action, path, value, time, transient=True):
    """
    Sticks a chip in the database for you.
    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param action: One of chips.MOD, chips.ADD, chips.DELETE
    :param path: A list of strings.  Could be joined on the client end as user.p1.p2.p3 and get to an object 
      at the end.
    :param value: The value of that object, as a pure python struct.  Can be None if you're deleting the object.
    :param transient: [IGNORE FOR NOW[ A chip is transient if it modifies the user data hierarchy in a way that 
      will be captured by a page reload.  Non-transient chips are sent to the client always, and are intended for
      notifications the user should receive no matter what.
    """
    content = xjson.dumps(dict(action=action, path=path, value=value))
    time_micros = utils.usec_db_from_dt(time)
    with db.conn(ctx) as ctx:
        db.run(ctx, "chips/insert_chip", user_id=user.user_id,
                    transient=transient, content=content, time=time_micros)


def get_chips(ctx, user, since, before, transient):
    """
    Grabs a list of chips from the database since the given time.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param since: datetime object that specifies the time of the last chip the client has seen.
    :param before: datetime object that specifies the latest chip to send, usually 'now'.
    :param transient: [IGNORE FOR NOW]
    """
    since_micros = utils.usec_db_from_dt(since)
    before_micros = utils.usec_db_from_dt(before)
    with db.conn(ctx) as ctx:
        if transient:
            rows = db.rows(ctx, "chips/select_chips", user_id=user.user_id,
                            since=since_micros, before=before_micros)
        else:
            rows = db.rows(ctx, "chips/select_chips", user_id=user.user_id,
                            since=since_micros, before=before_micros, no_transient=True)
    chips = []
    for row in rows:
        chip = xjson.loads(row['content'])
        chip['transient'] = row['transient']
        chip['time'] = utils.usec_js_from_db(row['time'])
        chips.append(chip)
    return chips

## Future chip sending functions
def add_in_future(ctx, user, collection, deliver_at, **model_params):
    # Create a new model instance using the supplied parameters.
    model = collection.model_class.create(**model_params)
    # Silently set the model's collection so the chip path is correct. This does
    # not add the model to the collection.
    model._set_parent(collection)
    assert model.has_id() # Must have server issued id.
    send(ctx, user, action=ADD, path=model._chip_path(), value=model.to_struct(), time=deliver_at)
    return model

def modify_in_future(ctx, user, model, deliver_at, **new_params):
    assert model.has_id() # Must have server issued id.
    for name in new_params:
        model.assert_known_field(name)
        # Verify the MOD is not touching server only fields.
        assert name not in model.server_only_fields
    # Add the model's id field to the chip value if available to conform to the MOD
    # value format.
    if model.has_id() and not model.is_root():
        new_params[model.id_field] = getattr(model, model.id_field, None)

    send(ctx, user, action=MOD, path=model._chip_path(), value=new_params, time=deliver_at)

def delete_in_future(ctx, user, model, deliver_at):
    assert model.has_id() # Must have server issued id.
    send(ctx, user, action=DELETE, path=model._chip_path(), value={}, time=deliver_at)


class LazyField(object):
    """
    A Descriptor which wraps a chips.Model attribute which represents a field and will be loaded
    in a lazy fashion.
    :param attr_name: str the name of the attribute/field which is being wrapped. The internal
        storage for this attribute value will have an "_" prepended to attr_name.
    :param loader: func the lazy loading function. The parent model instance will be provided as the only
        parameter to this function. Expected to return the attribute value.
    """
    def __init__(self, attr_name, loader):
        # The name of the originally wrapped attribute.
        self._wrapped_name = attr_name
        # The attribute name where the lazy loaded value will be stored.
        self._cached_name = "_" + attr_name
        self._loader = loader

    def __get__(self, model_instance, model_class):
        if model_instance is None:
            return self
        if hasattr(model_instance, self._cached_name):
            return getattr(model_instance, self._cached_name)
        else:
            try:
                value = self._loader(model_instance)
                setattr(model_instance, self._cached_name, value)
                return value
            # The getattr/getattribute etc. chain of functions as called by the runtime all raise an
            # AttributeError if they cannot resolve the given attribute. This signals to the runtime to
            # try the next getter mechanism. However, if the loader function has a typo or other error
            # which would result in an AttributeError, then we cannot quietly let that pass as that is a
            # programmer error in the loader implementation. Therefore we intercept any AttributeErrors
            # from the loader call and translate them into a real exception.
            except AttributeError, e:
                raise Exception(str(e))

    def __set__(self, model_instance, value):
        # Inform the Model instance that the wrapped attribute has changed if this is not a
        # new or deleted model.
        model_instance.mark_field_changed(self._wrapped_name)
        setattr(model_instance, self._cached_name, value)

    def _set_silent(self, model_instance, value):
        """ Set the field value without informing the model that the value changed, to
            for instance avoid a chip MOD."""
        setattr(model_instance, self._cached_name, value)

class ComputedField(object):
    """ A baseclass which provides a mechanism to modify field values or add new field accessors
        which wrap existing fields. """
    def __init__(self, wrapped_field):
        self.wrapped_field = wrapped_field

    def create_computed_field(self, model_class, computed_field):
        # Override this method to perform creation of computed field.
        # This example code shows how to attach the computed field name as a property
        # which just returns the wrapped field value.
        wrapped_field = self.wrapped_field
        def getter(self):
            return getattr(self, wrapped_field)
        setattr(model_class, computed_field, property(getter))

class FieldedClass(type):
    """Meta-class for initializing Model classes fields."""
    def __init__(cls, name, bases, dct):
        super(FieldedClass, cls).__init__(name, bases, dct)

        # Initialize the lazy_fields dictionary here so each unique class gets any empty dictionary.
        cls.lazy_fields = {}
        # After initializing the lazy_fields walk up the base class hierarchy and add any lazy fields
        # that were defined in any base classes as they are also attribues of this class.
        for base_class in bases:
            if hasattr(base_class, 'lazy_fields'):
                cls.lazy_fields.update(base_class.lazy_fields)

        fields_and_collections = cls.fields.union(cls.collections)
        if not cls.server_only_fields.issubset(fields_and_collections):
            raise ChipsError("server_only_fields not defined in fields or collections %s [%s]" %
                             (cls.__name__, cls.server_only_fields.difference(fields_and_collections)))

        # It is possible that a baseclass has already been processed and inserted unmanaged lazy field cached
        # field names into this list, so skip those as they would not be listed in 'fields'.
        unmanaged_fields = set((f for f in cls.unmanaged_fields if not f.startswith('_')))
        if not unmanaged_fields.issubset(cls.fields):
            raise ChipsError("unmanaged_fields not defined in fields %s [%s]" %
                             (cls.__name__, unmanaged_fields.difference(cls.fields)))

        # Find all the LazyFields for future use. Use items() copy instead of iter as unmanaged_fields
        # might be changing (have to replace as it is a frozenset).
        for prop, field in cls.__dict__.items():
            if isinstance(field, LazyField):
                if field._cached_name in cls.__dict__:
                    raise ChipsError("LazyField cached value name already defined in class %s [%s]" %
                                     (field._cached_name, cls.__name__))
                cls.lazy_fields[prop] = field
                # If the lazy field is listed in unmanaged_fields then also mark its cached value name as unmanaged.
                if prop in cls.unmanaged_fields:
                    cls.unmanaged_fields = cls.unmanaged_fields.union(set([field._cached_name]))

        # Process the ComputedFields
        for computed_field, computer in cls.computed_fields.iteritems():
            computer.create_computed_field(cls, computed_field)

class Model(object):
    """Base class for data that needs to have deltas tracked with chips.  
    Subclass it and override the *id_field* and *fields* class members.
    
        class BankAccount(Model):
            id_field = 'ba_id'
            fields = frozenset(('ba_id', 'balance'))
    
    
    To construct an instance of the model from the database, use the constructor
    with keyword arguments:
    
        ba = BankAccount(ba_id=1234, balance=10)
    
    or if constructing from a database row:
       
        ba = BankAccount(**row)
        
    If inserting a new object into the database, use the class method create(),
    which has the same signature as the constructor:
    
        new_ba = BankAccount.create(ba_id=1234, balance=10)
    
    This does not actually insert it into the database (write your own methods
    to do that!), but it does mark the model as being added for the purpose 
    of sending out chips.
    """
    __metaclass__ = FieldedClass

    # The name of the id field property, which acts as a primary key in a collection and chips.
    id_field = None

    # List of field names as strings for all the valid fields in this model, not including the
    # id_field or collection names. All fields listed are required to be provided with a value
    # (which can be None) during construction. An exception will be raised if any attribute is
    # added to this class which is not in this list, the id_field, or in the collections list,
    # unless that attribute starts with a leading _ character.
    fields = frozenset()

    # Mapping of new field names, which wraps/maps to an existing field listed in fields.
    # The mapped value is expected to be a ComputedField subclass which will be run when
    # this class is loaded by the interpreter.
    computed_fields = {}

    # List of collection names as strings for all the collections in this model.
    collections = frozenset()

    # Optionally list any fields that should only be available to a server instance of this
    # Model and never serialized to the client.
    server_only_fields = frozenset()

    # Optionally list any fields here which should not have their parent assigned to this
    # model instance when they are assigned as attributes. This may be because they are already
    # a member of a Collection and have their parent set.
    unmanaged_fields = frozenset()

    # Tracks all LazyFields used by this Model. Initialized by the metaclass.
    lazy_fields = None

    def __init__(self, **properties):
        """Constructor, accepts keyword arguments that become propreties.
        Note that no effort is made to ensure that the properties are also
        part of the fields.  This is so that the server can maintain variables
        that are not synced with the client.
        """
        self._changed_fields = set()
        self._new = False
        self._deleted = False
        self._parent = None

        # Set all the fields silently to avoid marking them as changed.
        self.set_silent(**properties)

        # Verify every field has a value or is a LazyField. Do not check values as these
        # may trigger lazy loaders.
        for name in self.fields:
            if not (name in self.lazy_fields or hasattr(self, name)):
                raise ChipsError("Required field in model not defined %s [%s]", self.__class__.__name__, name)
        # Verify this instance has an 'id' set.
        if self.get_id() == None:
            raise ChipsError("Model has no id field set %s [%s]", self.__class__.__name__, self.id_field_name)

    @classmethod
    def create(klass, **kw):
        """Static factory method that behaves identically to the constructor
        but returns an object which will generate an ADD chip."""
        m = klass(**kw)
        m._new = True
        return m

    def delete(self):
        """Mark this model instance as deleted. A subsequent call to send_chips will issue a delete chip
            for this instance. If this instance has a Collection parent, it will be deleted from the
            collection as well."""
        if self.parent:
            assert isinstance(self.parent, Collection) # only know how to delete from Collection parents
            self.parent.delete_child(self)
        else:
            self._mark_deleted()

    def _mark_deleted(self):
        self._deleted = True

    @property
    def id_field_name(self):
        """ Returns the name of the id_field, which for a RootModel is the RootId.name. """
        if self.is_root():
            return self.id_field.name
        else:
            return self.id_field

    @property
    def parent(self):
        return self._parent
    
    def _set_parent(self, parent):
        """Give the model object a parent.  This is used for constructing
        paths and so that the parent can be reindexed by the child."""
        assert self._parent == None # implementing reparenting requires more work
        # Set the parent silently to dodge setattr parent handling.
        object.__setattr__(self, '_parent', parent)

    def assert_valid_attribute(self, name):
        """ All attribues of this class must either be a known field or have an _ prefix. """
        if name.startswith('_'):
            return
        self.assert_known_field(name)

    def is_known_field(self, name):
        """ Returns True if the given field name is known (tracked) by this Model instance.
            A known field is either in the 'fields' list, 'collections' list, the id field,
            or is 'cid'. """
        return (name in self.fields) or (name in self.collections) or (name == self.id_field_name) or (name == 'cid')

    def assert_known_field(self, name):
        """ Raises a ChipsError if the given field name is not known (tracked) by this Model."""
        if not (name == self.id_field_name or self.is_known_field(name)):
            raise ChipsError("Unknown field in model %s [%s]", self.__class__.__name__, name)

    def mark_field_changed(self, name):
        """Flags an attribute field as having been modified. This is done automatically
        under normal circumstances by the model itself, but if a subclass intercepts the
        usual __setattr__ chain, this method must be called to inform the model that the
        field has been changed."""
        self.assert_known_field(name)
        assert not self._deleted  # Once a model is deleted, we don't expect attributes to change.
        self._changed_fields.add(name)

    def set_silent(self, **kw):
        """Sets the properties "silently", i.e. without marking the model as
        changed.  Use this if you have to look stuff up from the db after the
        model instance has already been constructed."""
        self._set_attr(silent=True, **kw)

    def __setattr__(self, name, value):
        """This method intercepts any properties set on the object, and should
        never be called directly.  If the property is one of the tracked fields,
        this method marks the model instance as changed and will generate a 
        MOD chip later on.
        """
        assert name != 'cid' # can't see a reason to set a cid after construction
        self._set_attr(silent=False, **{name: value})

    def _set_attr(self, silent, **kw):
        old_id = None
        for name, value in kw.iteritems():
            self.assert_valid_attribute(name)

            # If the model 'id' (id_field, cid etc) is changing and currently has a value,
            # remember the old id_field value for any child reindexing.
            if name == self.id_field and (self.has_id() or self.has_cid()):
                old_id = self.get_id()

            # If not in silent mode, flag this field as changed.
            if not silent:
                if name in self.fields:
                    self.mark_field_changed(name)
            # If setting silently and this is a LazyField, use _set_silent to set the value.
            if silent and name in self.lazy_fields:
                self.lazy_fields[name]._set_silent(self, value)
            else:
                object.__setattr__(self, name, value)
            # If this attribute is not an unmanaged field and is a Model or Collection
            # inform it that this model instance is now its parent.
            if name not in self.unmanaged_fields and isinstance(value, (Model, Collection)):
                value._set_parent(self)

        # Inform any parent if our 'id' changed so this model can be reindexed in any collection.
        if old_id is not None and self._parent is not None:
            self._parent._child_reindex(old_id, self)

    def _pending_chips(self):
        """
        Returns an array of unsent chips.
        """
        assert not (self._deleted and self._new)
        # NOTE: This is ce4 specific code and could be factored out.
        deliver_at = gametime.now()

        chips = []
        # If this is a DELETE, send an empty dict.
        if self._deleted:
            chips.append({
                'action':DELETE,
                'path':self._chip_path(),
                'value':{},
                'time':deliver_at
            })
        # If this is an ADD, add all fields and collections.
        elif self._new:
            chips.append({
                'action':ADD,
                'path':self._chip_path(),
                'value':self.to_struct(),
                'time':deliver_at
            })
        # If this is a MOD, add only the changed fields and id_field.
        elif len(self._changed_fields) > 0:
            chips.append({
                'action':MOD,
                'path':self._chip_path(),
                'value':self.to_struct(fields=self._changed_fields),
                'time':deliver_at})
        return chips

    def send_chips(self, ctx, user):
        """Any pending chips on this model instance are passed along to the user
        (via the module send() method), and the instance is marked as up-to-date.
        
        This also handles the transition from cid to real ids.  The model must
        have a real id for send_chips to work, the chips are generated with the 
        cid in the path (as is the convention), and afterwards the cid is removed.
        """
        assert self.has_id() # server only sends chips after database stuff has 
                             # completed and things have real ids
        for chip in self._pending_chips():
            send(ctx, user, action=chip['action'],
                 path=chip['path'], value=chip['value'], time=chip['time'])

        # clear out any state that marks this as "unsaved"
        self._changed_fields.clear()
        self._new = False
        self._deleted = False
        if self.has_cid():
            del self.cid

    def _chip_path(self):
        """Returns the path used in generated chips.  Uses the parent's path
        if present as a starting point."""
        if self.is_root():
            base_path = []
        else:
            assert self._parent != None # no chip path is valid without a parent
            base_path = self._parent._chip_path()

        if self.has_cid():
            base_path.append(self.cid)
        elif self.has_id():
            base_path.append(self.get_id())

        return base_path

    def is_root(self):
        """Returns true only if this is a root object.  Special!"""
        return isinstance(self.id_field, RootId)

    def has_id(self):
        """Returns true if the instance has a real id (the property named by 
        id_field is set)."""
        return self.is_root() or hasattr(self, self.id_field)

    def has_cid(self):
        """Returns true if the instance has a client id (cid) set."""
        return hasattr(self, 'cid')

    def get_id(self):
        """Returns the id of the instance.  It prefers a real id, but if none
        is present, uses the cid. If no id-like value is set, an Exception is raised."""
        if self.is_root():
            return self.id_field.name
        elif self.has_id():
            return getattr(self, self.id_field)
        elif self.has_cid():
            return self.cid
        else:
            raise Exception("No id-like value set when get_id() called.")

    def modify_struct(self, struct, is_full_struct):
        """
        Optional override point. Modify a struct dict before it is returned
        from to_struct.
        :param is_full_struct: True if all fields in this model are being struct-ified.
        Should be True when to_struct is called to create the full model/collection
        tree or during a chip ADD.
        """
        return struct

    def to_struct(self, fields=None):
        """
        Returns a JSON-friendly structure -- a dict containing the properties
        named in *fields*.
        :param fields: An optional list of fields to return instead of all fields. This only makes
        sense when checking the fields for this particular model and will not be passed to child models
        or collections.
        """
        struct = {}
        # If no fields list is provided, struct-ify all fields and collections.
        if fields is None:
            struct_fields = self.fields.union(self.collections)
        else:
            struct_fields = frozenset(fields)

        # Scrub any server side only fields.
        struct_fields = struct_fields.difference(self.server_only_fields)

        # Add all of the requested fields to the struct.
        for name in struct_fields:
            self.assert_known_field(name)
            value = getattr(self, name, None)
            # If the field value is a Model or Collection, ask the value
            # to struct-ify itself.
            if isinstance(value, (Model, Collection)):
                value = value.to_struct()
            struct[name] = value

        # Always add the id_field if this instance has one (not cid or root.)
        if self.has_id() and not self.is_root():
            struct[self.id_field] = getattr(self, self.id_field, None)

        # Give subclasses a chance to modify the struct.
        self.modify_struct(struct, is_full_struct=(fields == None))

        return struct

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.get_id())

    def __eq__(self, other):
        return isinstance(other, Model) and self.get_id() == other.get_id()

    def __hash__(self):
        return hash(self.get_id())

class RootId(object):
    """ Special class to be used only in the id_field section of a Model class,
    which forces the model to be the root object, and the name of the root
    object will always be the *name* passed in to the constructor."""
    def __init__(self, name):
        self.name = name


class Collection(object):
    """Manages a collection of Model instances.  It behaves like a dict, where
    the keys are the ids of the individual models.  To use a Collection, simply
    defined a subclass:
        
        class BankAccountCollection(Collection):
            model_class = BankAccount
    
    Collections always are named (this is so they can generate their own chip
    paths), so both methods of construction accept a name as the first argument.
    The first construction method explicitly takes already-existing Model 
    objects (or their corresponding structs):
    
        bc = BankAccountCollection('accounts',
                                   {'ba_id':1234, 'balance':10},
                                   {'ba_id':4568, 'balance':15})
    
    The more interesting way of constructing a Collection is with the static
    load_later(), which accepts a function that will be called later (currently
    it is only called explicitly and when to_struct() is called).  Any 
    arguments to the loading function can be passed in during the call to 
    load_later and they will be stored for later use.  Example:
    
        def accounts_loader(conn, key):
            return conn.execute('select * from accounts where key=%s', key)
            
        bc = BankAccountCollection.load_later('accounts',
                                              accounts_loader, conn, 'mykey')
                                              
    Basically the point of load_later is to provide a common construction path
    for the collection while not hitting the database if not actually necessary.
    """
    model_class = None
    def __init__(self, name, *model_args):
        """Constructor, accepts a variable quantity of model structs that are 
        used to populate the collection initially."""
        assert name != None
        self.name = name
        self._models = {}
        self._parent = None  #Model instance
        self._loader = None
        self._loaded = True
        for model_arg in model_args:
            m = self.model_class(**model_arg)
            self.add(m)
    
    @classmethod
    def load_later(klass, name, load_func, *a, **kw):
        """Static factory method, accepts a name, and a loading function.
        The load_func returns a list that can include either Model subclass
        instances OR dicts with values to be passed to the model_class
        constructor. (See self.load())
        Returns a Collection object that will call that function."""
        m = klass(name)
        m._loaded = False
        m._loader = (load_func, a, kw)
        return m
    
    def add(self, model):
        """Adds an already-constructed model instance to the collection."""
        assert isinstance(model, self.model_class)  # it's a homogeneous collection
        m_id = str(model.get_id())
        assert m_id != None # needs a real id or cid
        # If the models have already been loaded, verify the model being added is
        # not already in the set. This allows for create_child to be used before a potential
        # lazy load has happened, which might load the newly created child from the DB again.
        if self._loaded:
            assert m_id not in self._models # collision
        model._set_parent(self)
        self._models[m_id] = model
        return model

    def delete_child(self, model):
        """Delete a model instance from the collection. This does not send a chip, send_chips
           will still need to be called on the model instance."""
        assert isinstance(model, self.model_class)  # it's a homogeneous collection
        m_id = str(model.get_id())
        assert m_id != None # needs a real id or cid
        assert m_id in self._models
        model._mark_deleted()
        del self._models[m_id]

    def create_child(self, **kw):
        """Creates a child (using the create method of *model_class*, 
        and adds it to the collection. Returns the created model."""
        m = self.model_class.create(**kw)
        self.add(m)
        return m

    def get_models(self):
        """ Return the dict of child Models. This will lazy load the models if a loader was defined. """
        self.load()
        return self._models

    @property
    def parent(self):
        return self._parent

    def _set_parent(self, parent):
        """Give the collection a parent.  This is used for constructing paths."""
        assert self._parent == None # implementing reparenting requires more work
        self._parent = parent

    def _chip_path(self):
        """Returns the path used in generated chips.  Uses the parent's path
        if present as a starting point."""
        assert self._parent != None # no chip path is valid without a parent
        base_path = self._parent._chip_path()

        base_path.append(self.name)
        return base_path
    
    def load(self, *args, **kw):
        """Call this function to explicitly load the collection from the 
        database.  Any arguments passed to this function become the arguments
        to the *load_func* that was passed in to load_later()."""
        if self._loaded:
            return
        args = args or self._loader[1]
        kw = kw or self._loader[2]
        loaded_models = self._loader[0](*args, **kw)
        for m in loaded_models:
            if isinstance(m, Model):
                self.add(m)
            else:
                self.add(self.model_class(**m))
        self._loaded = True

    def to_struct(self, fields=None):
        """Returns a JSON-friendly structure -- a dict mapping ids to model structs.
        :param fields: An optional list of fields on the Models in the Collection to
        return instead of all fields.
        """
        return dict([(k, v.to_struct(fields=fields))
               for k,v in self.get_models().iteritems()])

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, ",".join(self.get_models()))

    def _child_reindex(self, old_id, model):
        """Called by one of the models in the collection to indicate that its
        id has changed, and thus the collection needs to reorder itself."""
        assert old_id in self._models  # detect logic errors
        new_id = model.get_id()
        assert new_id != None
        assert new_id not in self._models
        del self._models[old_id]
        self._models[new_id] = model

    # the following few methods make the collection objects act a bit more
    # like Python dicts, as a convenience only
    def __len__(self):
        return len(self.get_models())
        
    def __getitem__(self, key):
        """ The key for the child Models is always the str representation of the supplied value. """
        return self.get_models()[str(key)]

    def __iter__(self):
        return self.get_models().__iter__()

    def get(self, key, default=None):
        """ The key for the child Models is always the str representation of the supplied value. """
        return self.get_models().get(str(key), default)

    def has_key(self, key):
        return self.get_models().has_key(str(key))

    def keys(self):
        return self.get_models().keys()

    def iterkeys(self):
        return self.get_models().iterkeys()

    def items(self):
        return self.get_models().items()

    def iteritems(self):
        return self.get_models().iteritems()

    def values(self):
        return self.get_models().values()

    def itervalues(self):
        return self.get_models().itervalues()

    def __contains__(self, key):
        """In addition to supporting 'if "thing_id" in collection', we also
        support 'if thing_instance in collection'."""
        if isinstance(key, Model):
            key = key.get_id()
        return (str(key) in self.get_models())
