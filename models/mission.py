# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import hashlib, pkg_resources
from mako import lookup

from front import models
from front.lib import db, xjson, urls, gametime
from front.backend import deferred
from front.data import load_json, schemas, assets
from front.models import chips, region
from front.callbacks import run_callback, MISSION_CB

import logging
logger = logging.getLogger(__name__)

# The path relative to this package where the mission data is stored.
MISSION_DEFINITIONS = pkg_resources.resource_filename('front', 'data/mission_definitions.json')

# Template cache.
_template_lookup = lookup.TemplateLookup(input_encoding='utf-8', output_encoding='utf-8')
# Fields in speciesList which support Mako templating.
TEMPLATE_FIELDS = ['title', 'summary', 'description']

def add_mission(ctx, user, mission_definition, mission_parent=None, **kwargs):
    """
    Create a new Mission Model object for the given user.
    Note: specifics is for configuring generic missions for the user's  specific needs, and is serialized
    JSON stored as a string in the database.  The specifics_hash is populated with the hash of the specifics
    as the name implies; it's there so that the user can't do the exact same mission twice.
    The mission_id is the combination of the mission_definition and the specifics, with the parent_id
    having a similar formulation.
    NOTE: If the given mission_definition has already been added to this user, then this function will log
    a warning and return None indicating the mission already existed. This behavior exists so that if the ordering
    of when missions are added is changed on the live system to reflect for instance a change in the story, then
    if a user had already received a mission in the previous version of the story it will not raise an exception here,
    hopefully allowing a smoother migration experience for existing users to the new story version.

    :param ctx: The database context.
    :param user: The User who will own this Mission.
    :param mission_definition: str The key which identifies this mission type.
        Defined in mission_definitions.json.
    :param mission_parent: Mission The optional Mission instance which is the parent of this Mission.
    :param kwargs: dict All other keyword arguments will be passed through to the creation_hook for this
        Mission's mission_callbacks callback. These might be useful when creating the mission specifics.
    """
    # As we change the story script, sometimes we change the order when a mission is being added
    # to the game. This guard is intended to make that migration more smooth. NOTE: It is critical
    # that a given MIS_ key always refers to the same 'mission concept'.
    if user.missions.get_only_by_definition(mission_definition) is not None:
        logger.warning("Refusing to add exising mission_definition to user. [%s][%s]", mission_definition, user.user_id)
        return None

    # Determine the md5 hashes of the mission specifics for this Mission instance by running
    # the create_specifics callback for the mission code associated with this mission_definition.
    specifics = run_callback(MISSION_CB, "create_specifics", mission_definition, ctx=ctx, user=user, **kwargs)
    dumped_specifics = xjson.dumps(specifics)
    md5 = hashlib.md5()
    md5.update(dumped_specifics)
    specifics_hash = md5.hexdigest()
    if mission_parent:
        parent_hash = mission_parent.specifics_hash
    else:
        parent_hash = ''

    params = {}
    params['mission_definition'] = mission_definition
    params['specifics'] = dumped_specifics
    params['specifics_hash'] = specifics_hash
    params['parent_hash'] = parent_hash
    params['done'] = 0
    params['done_at'] = None
    params['started_at'] = user.epoch_now
    params['viewed_at'] = None

    # We need to snapshot the existing list of regions for this user as once the
    # new mission is added to the gamestate it will potentially influence the list
    # of regions, which will potentially make the check if it is a new region later
    # in this factory function fail.
    current_user_regions = user.regions.keys()

    with db.conn(ctx) as ctx:
        db.run(ctx, "insert_mission", user_id=user.user_id, created=gametime.now(), **params)
    new_mission = user.missions.create_child(mission_parent=mission_parent, user=user, **params)

    # If we have a parent, add ourselves to the hierarchy.
    if mission_parent != None:
        mission_parent.parts.append(new_mission)

    # Issue ADD chips for any regions defined/available for this mission at creation time.
    for region_id, constructor_args in new_mission.region_list_callback():
        # Adding a region more than once may cause inconsistencies with ADD/DELETE chips.
        assert region_id not in current_user_regions
        region.add_region_to_user(ctx, user, region_id, **constructor_args)
        current_user_regions.append(region_id)

    # Issue the mission ADD chip.
    new_mission.send_chips(ctx, user)

    # If this mission has any children, add them now.
    child_parts = run_callback(MISSION_CB, "create_parts", mission_definition, mission=new_mission)
    for child_mission_def in child_parts:
        add_mission(ctx, user, child_mission_def, mission_parent=new_mission, **kwargs)

    # Trigger the was_created callback.
    run_callback(MISSION_CB, "was_created", mission_definition, ctx=ctx, user=user, mission=new_mission)

    return new_mission

class Mission(chips.Model, models.UserChild):
    # These fields come from the mission definitions JSON file.
    DEFINITION_FIELDS = frozenset(['title', 'summary', 'description', 'done_notice', 'parent_definition', 'type', 'sort',
                                   'title_icon', 'description_icon'])

    id_field = 'mission_id'
    fields = frozenset(['mission_definition', 'done', 'done_at', 'specifics', 'specifics_hash', 'started_at', 'viewed_at',
                        'region_ids', 'parent_id', 'parent_hash', 'mission_parent', 'parts']).union(DEFINITION_FIELDS)

    # The list of region_ids being provided to the gamestate by the mission, in its current
    # done/not done state. Provided to the gamestate in the 'region_ids' field.
    # Note that because LazyFields values are cached, if the 'done' state of this mission changes
    # the value of region_ids might need refreshing.
    region_ids = chips.LazyField("region_ids", lambda m: m._region_list_ids())

    computed_fields = {
        'started_at_date': models.EpochDatetimeField('started_at'),
        'viewed_at_date': models.EpochDatetimeField('viewed_at'),
    }

    server_only_fields = frozenset(['parts', 'parent_hash', 'specifics_hash', 'mission_parent'])
    unmanaged_fields = frozenset(['mission_parent'])

    # user_id, created and updated are database only fields.
    def __init__(self, mission_definition, parent_hash, done, specifics, specifics_hash, user,
                 mission_parent=None, user_id=None, created=None, updated=None, **params):
        # Populate the fields which come from the mission definition.
        definition = get_mission_definition(mission_definition)
        for field in self.DEFINITION_FIELDS:
            params[field] = definition.get(field, None)

        # This comes from the mission definition file.
        parent_definition = params.get('parent_definition')
        if mission_parent is not None:
            params['parent_id'] = mission_parent.mission_id
        elif parent_definition is not None and parent_hash is not None:
            params['parent_id'] = "%s-%s" % (parent_definition, parent_hash)
        else:
            params['parent_id'] = None
        params['parts'] = []

        # Convert the specifics hash which is stored in the DB as serialized JSON back into
        # a Python dict.
        specifics = xjson.loads(specifics)
        # Construct the mission id which is the definition name and the md5 hash of the specifics.
        mission_id = make_mission_id(mission_definition, specifics_hash)

        # Render the title, summary and description fields.
        params['title'] = _render_template(mission_definition, 'title', {'user': user})
        if params['summary'] is not None:
            params['summary'] = _render_template(mission_definition, 'summary', {'user': user})
        if params['description'] is not None:
            params['description'] = _render_template(mission_definition, 'description', {'user': user})

        super(Mission, self).__init__(mission_id=mission_id, mission_definition=mission_definition,
            mission_parent = mission_parent, parent_hash=parent_hash, done=done,
            specifics=specifics, specifics_hash=specifics_hash, **params)

    @property
    def user(self):
        # self.parent is user.missions, the parent of that is the User itself
        return self.parent.parent

    def is_root_mission(self):
        """ Returns True if this mission is a 'root' mission, either a childless single mission or the parent
            mission for one or more children.
            NOTE: This is not called is_root as that method already exists in chips.Model """
        return self.parent_id == None

    def is_done(self):
        return self.done == 1

    def was_viewed(self):
        return self.viewed_at != None

    @property
    def url_title_icon(self):
        definition = assets.mission_icon_definition(self.title_icon)
        return definition['done'] if self.is_done() else definition['active']

    @property
    def url_description_icon(self):
        definition = assets.mission_icon_definition(self.description_icon)
        return definition['done'] if self.is_done() else definition['active']

    def next_step(self):
        """ Return the next step/sibling mission to this mission. This asserts that this
            mission has a parent. If there is no next step, None is returned. """
        assert self.mission_parent != None # We should have a parent.
        # Will raise ValueError if somehow this mission is not known to the parent.
        index = self.mission_parent.parts.index(self)
        # We are the first step, there is not previous.
        if index == len(self.mission_parent.parts) - 1:
            return None
        else:
            return self.mission_parent.parts[index + 1]

    def previous_step(self):
        """ Return the previous step/sibling mission to this mission. This asserts that this
            mission has a parent. If there is no previous step, None is returned. """
        assert self.mission_parent != None # We should have a parent.
        # Will raise ValueError if somehow this mission is not known to the parent.
        index = self.mission_parent.parts.index(self)
        # We are the first step, there is not previous.
        if index == 0:
            return None
        else:
            return self.mission_parent.parts[index - 1]

    def siblings(self):
        """ Return the array of all other siblings, not including self. """
        assert self.mission_parent != None # We should have a parent.
        return [part for part in self.mission_parent.parts if part != self]

    def done_siblings(self):
        """ Return the array of done siblings, not including self. """
        assert self.mission_parent != None # We should have a parent.
        return [part for part in self.mission_parent.parts if part != self and part.is_done()]

    def mark_done(self):
        # As we change the story script, sometimes we change the order when a mission is being marked done
        # in the game. This guard is intended to make that migration more smooth.
        if self.is_done():
            logger.warning("Refusing to mark already done mission_definition done again. [%s][%s]", self.mission_definition, self.user.user_id)
            return

        # Snapshot the list of regions provided by this mission before it is marked done. If any new regions
        # are added when it is done or any are no longer present, then the correct ADD and DELETE chips will be
        # issued at the end of this method.
        # We need to snapshot the existing list of region_ids for this mission as the lazy loader
        # might populate the done mission regions and will potentially influence the list
        # of regions, which will potentially make the check if it is a new region later
        # in this method fail.
        # NOTE: Currently this code makes no attempt to determine if the region being deleted is also
        # provided by some other data in the gamestate. In other words, regions returned by a missions
        # region_list are assumed to be unique to that mission and can be safely removed from the gamestate
        # when the mission is marked done.
        not_done_region_ids = self.region_ids

        # We need to snapshot the existing list of regions for this user as the lazy loader
        # might populate the done mission regions and will potentially influence the list
        # of regions, which will potentially make the check if it is a new region later
        # in this method fail.
        not_done_user_regions = self.user.regions.keys()

        # Mark the instance as done.
        epoch_now = self.user.epoch_now
        self.done = 1 # Make our state mirror the database's.
        self.done_at = epoch_now
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_mission_done', done=self.done, done_at=self.done_at, user_id=self.user.user_id,
                mission_definition=self.mission_definition, specifics_hash=self.specifics_hash)

        # The list of region_ids might have changed because the done state has changed so trigger
        # a MOD on that field. If it has changed, trigger the setattr so that it will be included in the MOD
        # and update the lazy field value.
        done_region_ids = self._region_list_ids()
        if done_region_ids != not_done_region_ids:
            self.region_ids = done_region_ids

        # Determine if any region_ids were added or removed.
        added_region_ids   = done_region_ids.difference(not_done_region_ids)
        deleted_region_ids = not_done_region_ids.difference(done_region_ids)

        # Issue the chip for the done and region_ids changes.
        self.send_chips(ctx, self.user)

        # Inform the callback that this mission was marked done.
        run_callback(MISSION_CB, "marked_done", self.mission_definition, ctx=ctx, user=self.user, mission=self)

        # Issue DELETE chips for any regions defined/available when this mission was not_done now that it is done.
        for region_id in deleted_region_ids:
            self.user.regions.delete_by_id(region_id)

        # Issue ADD chips for any regions defined/available for this mission now that it is done.
        for region_id, constructor_args in self.region_list_callback():
            # Need to filter out any regions that were also provided in not_done_region_list.
            if region_id in added_region_ids:
                # Adding a region more than once may cause inconsistencies with ADD/DELETE chips.
                assert region_id not in not_done_user_regions
                region.add_region_to_user(ctx, self.user, region_id, **constructor_args)
                not_done_user_regions.append(region_id)

    def mark_parent_done(self):
        assert self.mission_parent != None
        self.mission_parent.mark_done()

    def mark_done_after(self, after_seconds):
        """ Use the the deferred system to mark this mission done after a delay of 'after_seconds' seconds
            if the mission is not already marked done or hasn't already been queued to be marked done in deferred. """
        # If the mission is already done, do not queue up a deferred to mark it done again.
        if self.is_done():
            return
        with db.conn(self.ctx) as ctx:
            # Only allow one deferred action at a time to mark a given mission done, even if
            # the run_at time is different.
            if deferred.is_queued_to_run_later_for_user(ctx, deferred.types.MISSION_DONE_AFTER, self.mission_definition, self.user):
                return
            deferred.run_later(ctx, deferred.types.MISSION_DONE_AFTER, self.mission_definition, self.user, after_seconds)

    def mark_viewed(self):
        """ Mark this mission as 'viewed' (set a value of 'now' for viewed_at).
            If this mission is a parent mission with child parts, all the child parts are
            also marked viewed. """
        with db.conn(self.ctx) as ctx:
            epoch_now = self.user.epoch_now
            # If this is a parent mission with child parts,
            # mark them all viewed as well.
            for m in self.parts:
                m.mark_viewed()

            db.run(ctx, "update_mission_viewed_at", user_id=self.user.user_id,
                mission_definition=self.mission_definition, specifics_hash=self.specifics_hash, viewed_at=epoch_now)
            self.viewed_at = epoch_now # Make our state mirror the database's.
            self.send_chips(ctx, self.user)

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'mark_viewed':urls.mission_mark_viewed(self.mission_id)
            }
        return struct

    def region_list_callback(self):
        """ Returns a list of tuples which map a region_id to any arguments to pass to the constructor
            of that region. The list might be different based on whether this mission is done or not.
            e.g. [(region_id1, {}, region_id2, {center: [123, 456]})].
            This data is only meant to be used when filling the user.regions list or when creating a
            new mission."""
        region_ids_or_packs = run_callback(MISSION_CB, "region_list", self.mission_definition, mission=self)
        return models.convert_to_region_descriptions(region_ids_or_packs)

    def validate_new_target_params_callback(self, rover, arrival_delta, params):
        """ This is a passthrough to the mission_callbacks.validate_new_target_params method. """
        return run_callback(MISSION_CB, "validate_new_target_params", self.mission_definition, user=self.user,
                            mission=self, rover=rover, arrival_delta=arrival_delta, params=params)

    def _region_list_ids(self):
        return set((region_id for (region_id, args) in self.region_list_callback()))

def make_mission_id(mission_definition, specifics_hash):
    """ Returns the string mission_id which is composed from the mission_definition and specifics_hash. """
    return "%s-%s" % (mission_definition, specifics_hash)

def is_known_mission_definition(mission_definition):
    """ Returns True if the given mission_definition was defined in the mission definitions. """
    return mission_definition in _get_all_mission_definitions()

def get_mission_definition(definition_key):
    """
    Return the mission definition as a dictionary for the given mission definition name.

    :param definition_key: str key for this mission definition e.g MIS_TUT01. Defined in
    mission_definitions.json
    """
    return _get_all_mission_definitions()[definition_key]

def _render_template(mission_definition, field, template_data=None):
    """
    Render a mission field (e.g. title, summary, description) using the given mission_definition and field name.
    E.g. MIS_ARTIFACT01, 'title'

    :param mission_definition: str The mission_definition string to be rendered.
    :param field: str The field name being rendered, e.g. title, summary or description.
    :param template_data: dict the template data to supply during rendering.
    """
    if template_data is None:
        template_data = {}

    # Create a unique key for this mission and field, e.g. MIS_ARTIFACT01::title
    template_uri = _template_uri(mission_definition, field)
    template = _template_lookup.get_template(template_uri)
    return template.render(**template_data)

def _get_all_mission_definitions():
    """ Load the JSON file that contains the mission definitions """
    return _g_mission_definitions

# Fields with 'None' default values are optional in the mission_definitions file and will have the value of
# None/null in the gamestate if not defined in that file.
def _add_mission_definition(mission_definition, type, title, sort, summary=None, description=None,
                            done_notice=None, parent_definition=None, title_icon=None, description_icon=None):
    # Skip values from the method parameters which are None.
    definition = dict([(key, value) for (key, value) in locals().iteritems()
                       if value is not None])
    # Enforce a few additional rules:
    # child missions must have a description.
    if 'parent_definition' in definition:
        if 'description' not in definition:
            raise Exception("Child missions must have a description %s" % mission_definition)
    # parent missions must have a summary.
    else:
        if 'summary' not in definition:
            raise Exception("Parent missions must have a summary %s" % mission_definition)

    _g_mission_definitions[mission_definition] = definition
    # Populate all of the templates as well.
    for field in TEMPLATE_FIELDS:
        if field in definition:
            _template_lookup.put_string(_template_uri(mission_definition, field), definition[field])

def _template_uri(mission_definition, field):
    return mission_definition + "::" + field

_g_mission_definitions = None
def init_module():
    global _g_mission_definitions
    if _g_mission_definitions is not None: return

    _g_mission_definitions = {}
    definitions = load_json(MISSION_DEFINITIONS, schema=schemas.MISSION_DEFINITIONS)
    for mission_definition, definition in definitions.iteritems():
        _add_mission_definition(mission_definition, **definition)
