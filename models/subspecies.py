# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import models
from front.data import load_json, schemas
from front.models import chips

def add_new_subspecies(ctx, user, species, subspecies_id):
    """
    This adds a new SubSpecies object to a given Species object. This should only be called
    when a given subspecies is first detected, as it issues an ADD chip.
    """
    subspecies = species.subspecies.create_child(subspecies_id=subspecies_id, species_type=species.type)
    # Send a chip for this subspecies being added.
    subspecies.send_chips(ctx, user)
    return subspecies

class SubSpecies(chips.Model, models.UserChild):
    """
    Holds the list of SubSpecies attributes.
    :param subspecies_id: int the unique identifier for this subspecies.
    """
    id_field = 'subspecies_id'
    fields = frozenset(['name'])

    def __init__(self, subspecies_id, species_type):
        # Lookup subspecies description from the JSON file.
        params = _get_by_id(subspecies_id, species_type)
        super(SubSpecies, self).__init__(**params)

    @property
    def species(self):
        # self.parent is species.subspecies, the parent of that is the species itself
        return self.parent.parent

    @property
    def user(self):
        return self.species.user

## Private JSON description data loading functions.
def _get_all():
    return _g_all_subspecies

def _get_by_id(subspecies_id, species_type):
    return _get_all()[species_type][subspecies_id]

_g_all_subspecies = None
def init_module(subspecies_path):
    global _g_all_subspecies
    if _g_all_subspecies is not None: return

    _g_all_subspecies = {}
    contents = load_json(subspecies_path, schema=schemas.SUBSPECIES_LIST)
    # Verify that subspecies_ids are unique per species type in the JSON file.
    for species_type, descriptions in contents['subSpeciesList'].iteritems():
        _g_all_subspecies[species_type] = {}
        for d in descriptions:
            if d['subspecies_id'] in _g_all_subspecies[species_type]:
                raise Exception("subspecies_id not unique for species type [%s][%s]" % (d['subspecies_id'], species_type))
            _g_all_subspecies[species_type][d['subspecies_id']] = d
