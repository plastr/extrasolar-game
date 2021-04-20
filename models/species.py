# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from mako import lookup

from front import Constants, models, species_types
from front.lib import db, utils, urls
from front.data import load_json, schemas, assets
from front.models import chips
from front.models import subspecies as subspecies_module
from front.callbacks import run_callback, SPECIES_CB

# Template cache.
_template_lookup = lookup.TemplateLookup(input_encoding='utf-8', output_encoding='utf-8')
# Fields in speciesList which support Mako templating.
TEMPLATE_FIELDS = ['name', 'description']

# If the lowest 20 bits of a species_id are all 0, then that species_id is a reserved ID for items
# that are beyond the distance threshold for accurate identification.
SPECIES_TOO_FAR_MASK = 0xFFFFF

def add_new_species(ctx, user, species_id, subspecies_ids, target_ids):
    """
    This creates a new Species object and persists it. The detected_at field will have a time
    of "now". This should only be called when a new species is first detected by the user.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param species_id: int The unique id for this spcies. Defined in speciesList.json
    :param subspecies_ids: set object. Set of any subspecies_id that were detected along
        with the first detection of this species.
    :param target_is: set object. Set of tuples mapping the rover_id,target_ids which have
        identified this species. See __init__ for more documentation.
    """
    detected_at = user.epoch_now
    viewed_at = None
    with db.conn(ctx) as ctx:
        # user_id is only used when creating the Species in the database, it is not loaded
        # by chips as the user.species collection takes care of assigning a User to a Species.
        db.run(ctx, "insert_species", user_id=user.user_id, species_id=species_id, detected_at=detected_at)
        species = user.species.create_child(species_id=species_id, detected_at=detected_at, viewed_at=viewed_at,
                                            target_ids=target_ids, subspecies_ids=subspecies_ids, user=user)

        # NOTE: If subspecies_ids is not empty, then the species.subspecies collection will have
        # values and be part of the ADD chip for this species.

        # Send a chip for this species being added.
        species.send_chips(ctx, user)

        # If the full species information is being delayed to the client, send a future MOD chip with
        # the real information.
        if species.has_delayed_availability():
            new_params = {'name':species.name, 'description':species.description, 'science_name':species.science_name, 'icon':species.icon}
            chips.modify_in_future(ctx, user, species, deliver_at=species.available_at_date, **new_params)
    return species

class Species(chips.Model, models.UserChild):
    """
    Holds the list of Species attributes.
    :param species_id: int the unique identifier for this species.
    :param target_ids: set of tuples (rover_id, target_id) that identify the targets this species
        has been identified in. This is used by the client to conveniently lookup targets for this species.
        Set is used to guarantee a given mapping only appears once.
    :param user: The User associated with this Species. This is required as the user object is provided
        to the templating system when rendering the title and description fields.
    """
    id_field = 'species_id'
    fields = frozenset(['name', 'key', 'type', 'icon', 'description', 'science_name', 'detected_at', 'available_at',
                        'viewed_at', 'target_ids'])
    computed_fields = {
        'detected_at_date'  : models.EpochDatetimeField('detected_at'),
        'available_at_date': models.EpochDatetimeField('available_at'),
        'viewed_at_date': models.EpochDatetimeField('viewed_at')
    }
    collections = frozenset(['subspecies'])

    # user_id is a database only field.
    def __init__(self, species_id, detected_at, viewed_at, target_ids, subspecies_ids, user, user_id=None):
        # Lookup species definition from the JSON file.
        # Make a copy as we are going to change some fields.
        params = dict(_get_by_id(species_id))

        # Render the name and description fields.
        params['name'] = _render_template(params['key'], 'name', {'user': user})
        params['description'] = _render_template(params['key'], 'description', {'user': user})

        # Pack the subspecies_ids into a structure with the species_type which are the required
        # arguments to construct a SubSpecies object and will be used when creating the SubSpeciesCollection
        subspecies_params = [{'subspecies_id':s_id, 'species_type':params['type']} for s_id in subspecies_ids]

        # Compute the available_at value.
        minutes = delayed_minutes_for_id(params['species_id'])
        assert minutes <= Constants.MAX_SPECIES_DELAY_MINUTES, "Species data cannot be delayed more than MAX_SPECIES_DELAY_MINUTES [%s]" % params['key']
        available_at = detected_at + utils.in_seconds(minutes=minutes)

        super(Species, self).__init__(detected_at=detected_at, available_at=available_at, viewed_at=viewed_at,
                                      target_ids=target_ids,
                                      subspecies=SubSpeciesCollection('subspecies', *subspecies_params),
                                      **params)

        # Store an authoritative boolean as to whether this particular species had
        # its real description delayed to the client so that we do not use math based on
        # time seconds to determine this which might drift or otherwise be faulty.
        if minutes == 0:
            self.set_silent(_has_delayed_availability=False)
        else:
            self.set_silent(_has_delayed_availability=True)

    @property
    def user(self):
        # self.parent is user.species, the parent of that is the User itself
        return self.parent.parent

    @property
    def delayed_minutes(self):
        return delayed_minutes_for_id(self.species_id)

    @property
    def delayed_seconds_remaining(self):
        if self.has_delayed_availability() and self.is_currently_delayed():
            return self.available_at - self.user.epoch_now
        else:
            return 0

    def has_delayed_availability(self):
        return self._has_delayed_availability

    def is_currently_delayed(self):
        return self.user.epoch_now < self.available_at

    def is_organic(self):
        return self.type in species_types.ORGANIC

    # Some species, like "Unspecified photobiont" should be have an organic type, but should not be
    # included when we're counting organics for mission completion purposes.
    def include_in_count(self):
        return not self.key in Constants.SPECIES_IGNORE_IN_COUNT

    def was_viewed(self):
        return self.viewed_at != None

    @property
    def url_icon_medium(self):
        return assets.species_icon_url_for_dimension(self.icon, 150, 150)

    @property
    def url_icon_large(self):
        return assets.species_icon_url_for_dimension(self.icon, 300, 300)

    def add_subspecies_ids(self, subspecies_ids):
        """ Add the given subspecies_id to this species subspecies collection if needed. This is called
            when a new target rectangle has been created by the user that detected this species. """
        # Determine if any of the subspecies_ids are new.
        for subspecies_id in subspecies_ids:
            if subspecies_id not in self.subspecies:
                subspecies_module.add_new_subspecies(self.ctx, self.user, self, subspecies_id)

    def add_target_ids(self, target_ids):
        """ Add the given target_ids to this species target_id mapping if needed. This is called
            when a new target rectangle has been created by the user that detected this species. """
        # Determine if any of the target id mappings were not already associated with this species.
        new_target_ids = target_ids.difference(self.target_ids)
        if len(new_target_ids) > 0:
            # Create the union of the existing list of target_ids and the list of new pairings and
            # then assign that back to the target_ids attribute to trigger a MOD chip.
            self.target_ids = new_target_ids.union(self.target_ids)
            self.send_chips(self.ctx, self.user)

    def mark_viewed(self):
        with db.conn(self.ctx) as ctx:
            epoch_now = self.user.epoch_now
            db.run(ctx, "update_species_viewed_at", user_id=self.user.user_id, species_id=self.species_id, viewed_at=epoch_now)
            self.viewed_at = epoch_now # Make our state mirror the database's.
            self.send_chips(ctx, self.user)

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'mark_viewed':urls.species_mark_viewed(self.species_id)
            }

        # Replace the delayed fields in the struct if the available_at time has not arrived
        # so that the client cannot see this data until it has been identified by the scientists.
        if self.has_delayed_availability() and self.is_currently_delayed():
            unidentified = run_callback(SPECIES_CB, "unidentified_info", self.key, species=self)
            for key in unidentified:
                if key in struct:
                    struct[key] = unidentified[key]

        return struct

class SubSpeciesCollection(chips.Collection):
    model_class = subspecies_module.SubSpecies

## Module helper functions.
def are_organic(species_list):
    # Filter the given list of Species objects, returning only those which are ORGANIC.
    return [s for s in species_list if s.is_organic() and s.include_in_count()]

def is_organic_id(species_id):
    definition = _get_by_id(species_id)
    return definition['type'] in species_types.ORGANIC

def are_currently_delayed(species_list):
    # Filter the given list of Species objects, returning only those which have current delayed data.
    return [s for s in species_list if s.is_currently_delayed()]

# If the lowest 20 bits of this species_id are all 0, then this is a reserved ID for items
# that are beyond the distance threshold for accurate identification.
def is_too_far_for_id(species_id):
    return (species_id & SPECIES_TOO_FAR_MASK == 0)

def get_id_from_key(key):
    """ Return the species_id which matches the given species key. """
    return _g_species_id_by_key[key]

def get_key_from_id(species_id):
    """ Return the species key which matches the given species_id. """
    definition = _get_by_id(species_id)
    return definition['key']

def weighted_score_for_id(species_id, subspecies_id, density, target_species_count, all_species_count):
    """ Runs the scoring callback for the given species_id, passing through the remaining arguments. """
    definition = _get_by_id(species_id)
    score = run_callback(SPECIES_CB, "score_from_density", definition['key'],
                         species_id=species_id, subspecies_id=subspecies_id, species_type=definition['type'],
                         density=density, target_species_count=target_species_count, all_species_count=all_species_count)
    return score

def delayed_minutes_for_id(species_id):
    """ Returns then number of minutes that the full name and description (and any other data) is delayed from
        the client for the given species_id. May return 0 if there is no delay. """
    definition = _get_by_id(species_id)
    return run_callback(SPECIES_CB, "minutes_until_available", definition['key'],
                        species_type=definition['type'], species_id=species_id)

def is_known_species_key(species_key):
    """ Returns True if the given species_key was defined in the species definitions. """
    try:
        get_id_from_key(species_key)
        return True
    except KeyError:
        return False

def _render_template(species_key, field, template_data=None):
    """
    Render a species field (e.g. name, description) using the given species_key and field name.
    E.g. SPC_PLANT001, 'name'

    :param species_key: str The species key string to be rendered.
    :param field: str The field name being rendered, e.g. name or description.
    :param template_data: dict the template data to supply during rendering.
    """
    if template_data is None:
        template_data = {}

    # Create a unique key for this species key and field, e.g. SPC_PLANT001::name
    template_uri = _template_uri(species_key, field)
    template = _template_lookup.get_template(template_uri)
    return template.render(**template_data)

## Private JSON definition data loading functions.
def _get_all():
    return _g_all_species

def _get_by_id(species_id):
    return _get_all()[species_id]

def _template_uri(species_key, field):
    return species_key + "::" + field

_g_all_species = None
_g_species_id_by_key = None
def init_module(species_path):
    global _g_all_species
    global _g_species_id_by_key
    if _g_all_species is not None: return

    _g_all_species = {}
    _g_species_id_by_key = {}
    contents = load_json(species_path, schema=schemas.SPECIES_LIST)
    # Verify that both species_ids and keys are unique in the JSON file.
    for definition in contents['speciesList']:
        # Convert our species_id from a hex string (e.g., "0x000010") into an integer.
        definition['species_id'] = int(definition['species_id'], 16)
        if definition['species_id'] in _g_all_species:
            raise Exception("species_id not unique in species file [0x%06x]" % definition['species_id'])
        _g_all_species[definition['species_id']] = definition
        # Maintain a mapping of key -> species_id for lookup in get_by_key
        if definition['key'] in _g_species_id_by_key:
            raise Exception("species key not unique in species file [%s]" % definition['key'])
        _g_species_id_by_key[definition['key']] = definition['species_id']

        # If the speciesList definition does not have a science_name default the value to None
        if 'science_name' not in definition:
            definition['science_name'] = None

        # Populate all of the templates as well.
        for field in TEMPLATE_FIELDS:
            if field in definition:
                _template_lookup.put_string(_template_uri(definition['key'], field), definition[field])
