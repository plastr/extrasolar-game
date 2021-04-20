# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import ctypes

from front import target_image_types
from front.lib import urls, event
from front.models import species as species_module
from front.models import image_rect as image_rect_module

import logging
logger = logging.getLogger(__name__)

# The species_id value that comes back from the check_species C code might contain
# subspecies data in the lower 4 bits. These masks are used to break the value apart
# into species_id and subspecies_id
SUBSPECIES_ID_MASK = 0x0000000F
SPECIES_ID_MASK = 0xFFFFFFF0

LOCAL_SPECIES_DIR = None
CHECKSPECIES_LIB_PATH = None
_lib_checkspecies = None
_score_image_rects = None
_callbackFUNCTYPE = None
def init_module(checkspecies_lib_path, local_scenes_dir):
    global CHECKSPECIES_LIB_PATH, LOCAL_SPECIES_DIR, _lib_checkspecies, _score_image_rects, _callbackFUNCTYPE
    CHECKSPECIES_LIB_PATH = checkspecies_lib_path
    LOCAL_SPECIES_DIR = local_scenes_dir
    _lib_checkspecies = ctypes.cdll.LoadLibrary(CHECKSPECIES_LIB_PATH)
    _score_image_rects = _lib_checkspecies.score_image_rects
    _callbackFUNCTYPE = ctypes.CFUNCTYPE(None, ctypes.POINTER(REGION_SCORE_STRUCT), ctypes.c_int, ctypes.c_char_p)
    _score_image_rects.argtypes = [ctypes.c_char_p, ctypes.POINTER(RECT_STRUCT), ctypes.c_int, _callbackFUNCTYPE]

def identify_species_in_target(ctx, target, rect_structs):
    """
    Identify any species in the given target's image using the rectangles defined in rect_structs.
    Returns a tuple (detected_species, error_msg). If detected_species is not None, it will contain
    a list of all species IDs that were detected. If it is None, then error_msg will contain more details
    about why check_species failed. This error message is not designed to be user facing.
    :param ctx: The database context.
    :param target: Target The target object which holds the captured image to detect species in.
    :param rect_structs: A structure of the following schema that defines rectangle to look for species in.
        [{'xmin': 0.01, 'ymin': 0.01, 'xmax': 0.24, 'ymax': 0.24}, ...]
      The rect seq value will be assigned by this function based on the current number of rects assigned
      to this target.
    """
    species_image_url = target.images[target_image_types.SPECIES]

    # If the scene is being served from the local server, construct the filesystem path
    # to the image data so that checkspecies can find it.
    if species_image_url.startswith(urls.scenes_base()):
        species_image_url = LOCAL_SPECIES_DIR + species_image_url
    # FUTURE: If this is not a local scene, sign the S3 URL using urls.s3_download_url
    # so that only the extrasolar_download user can see the species_id files.

    # Assign the seq values to the rect regions based on the current number of region rectangles identified
    # in this target. Make copies of the rect dicts coming in from the client as they may be global
    # constants in the testing code which are mutable and would remember their seq values.
    next_seq = target.image_rects.next_seq()
    rect_structs_with_seq = []
    for i, rect in enumerate(rect_structs):
        # Client code should no longer be supplying the seq. Eventually this assertion can be removed.
        assert rect.get('seq') is None
        rect_structs_with_seq.append(dict(seq=next_seq, **rect))
        next_seq += 1

    # Run the ImageRects through the checkspecies process and populate the scoring fields
    # (species_id_X, density_X). Get a set of all detected species as well.
    (rect_scores, error_msg) = _check_species(species_image_url, rect_structs_with_seq)

    # If something went wrong in check_species, we'll get None as a return value.
    if rect_scores is None:
        return (None, error_msg)

    # Select the species for each region and assign them a score.
    target_species_count = target.species_count()
    all_species_count = target.user.species_count()
    for rect_score in rect_scores:
        # NOTE: target_species_count should probably be updated as each species is selected in turn.
        rect_score.score_and_select_species(target_species_count, all_species_count)
        # Update target_species_count and all_species_count with the species which were
        # just selected for this region.
        target_species_count.update(rect_score.detected_species())
        all_species_count.update(rect_score.detected_species())

    # Put detected species from all scored regions in a single set
    # and all the detected subspecies in a dict mapping species_id to
    # the set of subspecies detected for that species_id
    # (NO_SUBSPECIES values are not included).
    all_detected_species = set()
    all_detected_subspecies = dict()
    for rect_score in rect_scores:
        detected_species = rect_score.detected_species()
        all_detected_species.update(detected_species)
        # If any species were detected, track any subspecies.
        for species_id in detected_species:
            # If this species_id has had subspecies detected already, then
            # merge the detected subspecies into its set in the dict.
            if species_id in all_detected_subspecies:
                all_detected_subspecies[species_id].update(rect_score.detected_subspecies()[species_id])
            # Otherwise initialize the value in the dict to the set of all
            # detected subspecies for this species_id.
            else:
                all_detected_subspecies[species_id] = rect_score.detected_subspecies()[species_id]

    # Inform the target object of any species detected so it can keep the user.species collection
    # up to date and store the rects in the database along with their scores. Also issue any chips.
    target.detected_species_in_rects(all_detected_species, all_detected_subspecies, rect_scores)

    # Dispatch the species_identified event with the check_species results.
    for species_id in all_detected_species:
        # Species which were too far away for detection are ignored.
        if not species_module.is_too_far_for_id(species_id):
            identified = target.user.species[species_id]
            subspecies = all_detected_subspecies[species_id]
            event.dispatch(ctx, target.user, event.types.SPECIES_ID, identified.key, target, identified, subspecies)

    return (all_detected_species, None)

class RectScore(image_rect_module.SpeciesRect):
    def __init__(self, rect_struct):
        """
        This class validates and holds the data provide by the client when requesting that a
        checkspecies evaluation be performed on a given target image.
        The class also provides methods meant to be used to pass this data to the checkspecies
        C library as well as receive the data back from that libary. Finally, there is a method
        which is called to select the species that should be listed as detected in this region
        as well as generate a score for that region.
        NOTE: All data in rect_struct is assumed to have come on checked from the client and will
        be validated by this constructor via assertions.

        Fields expected in rect_struct:
        :param seq: int, The unique id for this region within the target image.
        :param xmin: float, These four values are the rectangle coordinates [0.0, 1.0] within the image.
        :param ymin: ditto
        :param xmax: ditto
        :param ymax: ditto
        """
        # Verify that numeric values are their expected types. This data comes from the client
        # and so this validation is required.
        assert rect_struct.get('seq') != None
        self.seq = int(rect_struct['seq'])
        
        for field in ['xmin', 'ymin', 'xmax', 'ymax']:
            coords = rect_struct.get(field)
            # Verify the field was set, is a float, and is between 0.0 and 1.0
            assert coords != None
            coords = float(coords)
            setattr(self, field, coords)
        
        # For 360-degree panoramas, xmax can wrap around to 2.0
        # Other coordinates should be between 0.0 and 1.0.
        assert 0.0 <= self.xmin <= 1.0
        assert 0.0 <= self.ymin <= 1.0
        assert 0.0 <= self.xmax <= 2.0
        assert 0.0 <= self.ymax <= 1.0

        # For scoring storage. Populated by store_density_region and score_and_select_species
        self.speciesList = []
        self.species_id = None
        self.subspecies_id = None
        self.density = None

    def to_rect_struct(self):
        """ Return the data stored in this object required as input to the checkspecies C function. """
        return RECT_STRUCT(
            seq=self.seq,
            xmin=self.xmin, xmax=self.xmax,
            ymin=self.ymin, ymax=self.ymax
        )

    def store_density_region(self, density_region):
        """ Store the data which came back from checkspecies."""
        # NOTE: All data currently being copied from the C struct objects that compose the density_region
        # are primitive numbers which should be copy by value and therefore safe. If more complex values
        # are introduced at a later date, care might need to be taken to be sure the data is properly
        # copied from C object memory to Python memory.
        assert self.seq == density_region.seq
        for i in range(0, density_region.species_len):
            species = density_region.species_list[i]
            self.speciesList.append({'raw_species_id':species.raw_species_id, 'density':species.density})

    def score_and_select_species(self, target_species_count, all_species_count):
        """ Select any detected any species_ids, subspecies_ids and densities (recording them as detected) based on
            the provided parameters and using any weightings for each particular species. """
        # If there were no species detected at all, leave the default None scored values unchanged.
        if len(self.speciesList) > 0:
            high_score = 0.0
            for raw_species_id, density in [(i['raw_species_id'], i['density']) for i in self.speciesList]:
                # Parse out the subspecies_id from the raw_species_id and convert the raw_species_id
                # to the proper species_id 'parent' value (lower 4 bits set to 0)
                species_id = raw_species_id & SPECIES_ID_MASK
                subspecies_id = raw_species_id & SUBSPECIES_ID_MASK

                # Pass the species_id and density information to the species callback
                # to compute the score for this particular identification in this rectangle.
                weighted_score = species_module.weighted_score_for_id(
                    species_id, subspecies_id, density, target_species_count, all_species_count)

                if weighted_score > high_score:
                    self.species_id = species_id
                    self.subspecies_id = subspecies_id
                    self.density = density
                    high_score = weighted_score

def _check_species(fileOrURL, rect_structs):
    """
    :param rect_structs: A structure of the following schema that defines rectangle to look for species in.
        [{'xmin': 0.01, 'ymin': 0.01, 'seq': 0, 'xmax': 0.24, 'ymax': 0.24}, ...]
    Returns a tuple:
        A list of RectScore objects that have not yet had their scoring method run but hold the client data
            and results from the checkspecies call.
        An error string, if an error occurred.
    """
    # Create the Python side objects which will receieve the checkspecies data from the C side
    # via the callback function.
    rect_scores = [RectScore(struct) for struct in rect_structs]

    # Pack the rect user data into the C structs.
    rect_structs = [rect_score.to_rect_struct() for rect_score in rect_scores]
    rects_num = len(rect_structs)
    RectsArray = RECT_STRUCT * rects_num
    array = RectsArray(*rect_structs)

    callback = score_callback(rect_scores)
    retval = _score_image_rects(fileOrURL, array, rects_num, _callbackFUNCTYPE(callback))
    # Handle an error coming back from checkspecies.
    if retval > 0:
        return None, callback.error

    return rect_scores, None

# The libcheckspecies API structs.
class RECT_STRUCT(ctypes.Structure):
    _fields_ = ("seq", ctypes.c_int),\
               ("xmin", ctypes.c_float), ("xmax", ctypes.c_float),\
               ("ymin", ctypes.c_float), ("ymax", ctypes.c_float)

class SPECIES_ID_STRUCT(ctypes.Structure):
    _fields_ = ("raw_species_id", ctypes.c_int), ("density", ctypes.c_float)

class REGION_SCORE_STRUCT(ctypes.Structure):
    _fields_ = ("seq", ctypes.c_int),\
               ("species_list", ctypes.POINTER(SPECIES_ID_STRUCT)), ("species_len", ctypes.c_int)

# Closures cannot modify captured variables (unless they are mutable collections),
# so rather than use a collection, wrap the callback in an object to capture the results.
# This converts the C structs coming from libcheckspecies into Python dicts.
# regions is an array of [{'seq':int, 'speciesList': ['raw_species_id':int, 'density':float]}]
# The species_id is the 'raw' species_id because it might contain subspecies data packed
# into the last 4 bits of its value.
class score_callback(object):
    def __init__(self, rect_scores):
        self.error = None
        self.rect_scores = rect_scores
    def __call__(self, density_regions, num_scores, errorMsg):
        if errorMsg is not None:
            # Copy the result string, which was malloc'd in C, into a new Python string.
            # Just concating with the empty string is not enough.
            self.error = errorMsg + " "
        else:
            assert num_scores == len(self.rect_scores)
            for i in range(0, num_scores):
                self.rect_scores[i].store_density_region(density_regions[i])
