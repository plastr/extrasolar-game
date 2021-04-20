# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
#
import os, ConfigParser
import importlib
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from front.lib import utils

# The current Version for the application. Uses a version.txt file in production
# which is generated during deploy and generates from the live repository on
# application startup in development. See Version class below for details
# and to see how this value is initialized.
VERSION = None

# Shared constants
class Constants(object):
    MIN_FAST_TARGET_SECONDS = utils.in_seconds(hours=1)  # Minimum time to take a new photo with the FAST_MOVE capability.
    MIN_TARGET_SECONDS      = utils.in_seconds(hours=4)  # Minimum time to take a new photo.
    MAX_TARGET_SECONDS      = utils.in_seconds(hours=22) # Maximum time to take a new photo.
    MAX_TRAVEL_DISTANCE     = 50.0 # Max distance between targets (plus epsilon) in meters.
    # These GRACE values are epsilons which allow for a bit of leeway when validating the
    # data from the client for a new target, in case things get delayed a bit or floating point math loss of precison.
    TARGET_SECONDS_GRACE    = utils.in_seconds(minutes=5)
    TRAVEL_DISTANCE_GRACE   = 1.0

    # The number of hours of activity which has happened before the user logs in the
    # first time. This is used to determine a new users 'epoch' value before any initial
    # rovers, targets, or other gamestate data is created. All activity that happens in
    # new_user_setup which is expected to happen before the user logs in must happen in
    # this number of hours.
    EPOCH_START_HOURS = 30
    # The number of seconds of leeway before arrival_time to allow certain 'scrubbed' data
    # in a target to be permitted into the gamestate.
    TARGET_DATA_LEEWAY_SECONDS = 30
    # The number of initial invitations to grant new users.
    INITIAL_INVITATIONS = 0
    # The list of client progress keys used to mark progress and completion of the simulator mission.
    SIMULATOR_PROGRESS_KEYS = ['PRO_TUT_01_STEP_09', 'PRO_TUT_01', 'PRO_TUT_03', 'PRO_TUT_04']
    # Max field length values for user data.
    MAX_LEN_EMAIL = 255
    MAX_LEN_FIRST = 127
    MAX_LEN_LAST  = 127
    MAX_LEN_PASS  = 50
    # Maximum number of minutes that species data can be delayed/hidden from the client.
    MAX_SPECIES_DELAY_MINUTES = 30
    # Some species, like "Unspecified photobiont" should be have an organic type, but should not be
    # included when we're counting organics for mission completion purposes.
    SPECIES_IGNORE_IN_COUNT = ('SPC_PLANT65535', 'SPC_ANIMAL65535')
    # Number of seconds of no user activity which will trigger a lure alert notification email.
    LURE_ALERT_WINDOW = utils.in_seconds(hours=118)
    # Number of seconds of no user activity after which no activity alerts will be sent.
    ACTIVITY_ALERT_INACTIVE_THRESHOLD = utils.in_seconds(days=10)
    # Be sure that before activity alerts are turned off, a lure would have been attempted/checked for a user.
    assert ACTIVITY_ALERT_INACTIVE_THRESHOLD > LURE_ALERT_WINDOW

class InitialMessages(object):
    # The number of minutes after user creation that the backdoor verify email is sent.
    EMAIL_VERIFY_DELAY_MINUTES = 5
    # The number of minutes after user validation that the welcome email is sent.
    EMAIL_WELCOME_DELAY_MINUTES = 10    
    # The number of minues after the player completes the simulator that they receive the Jane welcome message.
    MSG_JANE_INTRO_DELAY_MINUES = 10
    # The number of minues after the player completes the simulator that they receive the Kryptex welcome message.
    MSG_KTHANKS_DELAY_MINUES = 30
    # The number of hours after user creation that the second backdoor verify email is sent, if user is still not valid.
    EMAIL_VERIFY02_DELAY_HOURS = 22
    # The number of minutes after which all 'initial' messages or emails will have been sent.
    # Leave EMAIL_VERIFY02_DELAY_HOURS out of this list as its a huge delay and this list is really only used to
    # flush all initial messages when validating a user in testing, meaning EMAIL_VERIFY02 will not be sent.
    ALL_DELAY_MINUTES = max((EMAIL_VERIFY_DELAY_MINUTES, EMAIL_WELCOME_DELAY_MINUTES, MSG_JANE_INTRO_DELAY_MINUES, MSG_KTHANKS_DELAY_MINUES))

# rover key definitions.
class rover_keys(object):
    RVR_S1_INITIAL = "RVR_S1_INITIAL"
    RVR_S1_UPGRADE = "RVR_S1_UPGRADE"
    RVR_S1_NEW_ISLAND = "RVR_S1_NEW_ISLAND"
    RVR_S1_FINAL = "RVR_S1_FINAL"
    # Put these in a tuple so they have a predictable sort for migrating old rovers.
    ALL = (RVR_S1_INITIAL, RVR_S1_UPGRADE, RVR_S1_NEW_ISLAND, RVR_S1_FINAL)

# rover chassis definitions and mapping to rover keys.
class rover_chassis(object):
    RVR_CHASSIS_JRS = "RVR_CHASSIS_JRS"
    RVR_CHASSIS_SRK = "RVR_CHASSIS_SRK"
    ALL = set([RVR_CHASSIS_JRS, RVR_CHASSIS_SRK])

    # Map a rover key to the chassis for that rover.
    for_key = {
        rover_keys.RVR_S1_INITIAL: RVR_CHASSIS_JRS,
        rover_keys.RVR_S1_UPGRADE: RVR_CHASSIS_SRK,
        rover_keys.RVR_S1_NEW_ISLAND: RVR_CHASSIS_SRK,
        rover_keys.RVR_S1_FINAL: RVR_CHASSIS_SRK
    }
    assert set(for_key.keys()) == set(rover_keys.ALL), "Every rover key must have a rover chassis."

# target image type definitions.
class target_image_types(object):
    PHOTO       = "PHOTO"
    THUMB       = "THUMB"
    THUMB_LARGE = "THUMB_LARGE"
    SPECIES     = "SPECIES"
    WALLPAPER   = "WALLPAPER"
    INFRARED    = "INFRARED"
    ALL = set([PHOTO, THUMB, THUMB_LARGE, SPECIES, WALLPAPER, INFRARED])

# species type definitions.
class species_types(object):
    MANMADE = "MANMADE"
    ARTIFACT = "ARTIFACT"
    PLANT = "PLANT"
    ANIMAL = "ANIMAL"
    # Species type sets.
    INORGANIC = (MANMADE, ARTIFACT)
    ORGANIC = (PLANT, ANIMAL)
    ALL = set(INORGANIC + ORGANIC)

# subspecies type definitions.
class subspecies_types(object):
    class animal(object):
        DEFAULT         = 0
        MALE            = 1
        FEMALE          = 2
    class plant(object):
        DEFAULT         = 0
        YOUNG           = 1
        DEAD            = 2
        VARIATION_B     = 3
        LOCATION_B      = 4
        BIOLUMINESCENT  = 5
    class artifact(object):
        DEFAULT         = 0
        LOCATION_B      = 1
        LOCATION_C      = 2
        LOCATION_D      = 3
        LOCATION_E      = 4
        LOCATION_F      = 5

# gift type definitions.
class gift_types(object):
    GFT_NO_PASS = "GFT_NO_PASS"
    GFT_S1_PASS = "GFT_S1_PASS"
    GFT_ALL_PASS = "GFT_ALL_PASS"
    # Put these in a tuple so they have a predictable sort for admin gift creation listing.
    ALL = (GFT_NO_PASS, GFT_S1_PASS, GFT_ALL_PASS)

# notification settings and mappings.
class activity_alert_types(object):
    OFF    = "OFF"
    SHORT  = "SHORT"
    MEDIUM = "MEDIUM"
    LONG   = "LONG"
    ALL = set([OFF, SHORT, MEDIUM, LONG])
    # The initial value for a new player.
    DEFAULT = MEDIUM

    # Map the notification frequencies to the window size in seconds.
    windows = {
        SHORT:  utils.in_seconds(minutes=30),
        MEDIUM: utils.in_seconds(minutes=90),
        LONG:   utils.in_seconds(hours=6)
    }

def read_config(deployment, config_location=BASEDIR):
    """
    Read in the .ini file for the given deployment (test, development etc.). This helper is only meant
    to be used directly by unit tests or debug code which need a ctx object for database operations.
    """
    config = ConfigParser.SafeConfigParser({'here': config_location})
    config_file = os.path.join(config_location, deployment + ".ini")
    if not os.path.exists(config_file):
        raise Exception("Configuration file does not exist [%s]" % config_file)
    config.read(config_file)

    # Configure the logging infrastructure.
    import logging.config
    logging.config.fileConfig(config_file)
    # Return just the app:config section.
    return dict(config.items('app:front'))

def read_config_and_init(deployment, config_location=BASEDIR):
    """
    Read in the .ini file for the given deployment (test, development etc.) and initialize all the modules
    which in the system which require it. This function is only meant to be used by command line scripts and tools.
    Returns the config object which is suitable for use as the database 'ctx' object.
    NOTE: This function should only be called once per process.
    """
    config = read_config(deployment, config_location=config_location)
    init_with_config(config)
    return config

INIT_MODULES = [
    ('front.lib.urls',                    ['tools_absolute_root', 'stripe.charge_info_url']),
    ('front.lib.secure_tokens',           ['secure_tokens.secret_key']),
    ('front.lib.s3',                      ['amazon.download.access_key', 'amazon.download.secret_key']),
    ('front.lib.email_ses',               ['email_module.dispatcher', 'amazon.ses.access_key', 'amazon.ses.secret_key']),
    ('front.lib.email_module',            ['email_module.dispatcher']),
    ('front.lib.db',                      ['sql_strict_mode', 'sql_query_stat_interval_seconds']),
    ('front.lib.db.named_query',          ['sql_debug_queries']),
    ('front.models.achievement',          []),
    ('front.models.capability',           []),
    ('front.models.message',              []),
    ('front.models.mission',              []),
    ('front.models.product',              []),
    ('front.models.region',               ['regions_file']),
    ('front.models.species',              ['species_list']),
    ('front.models.subspecies',           ['subspecies_list']),
    ('front.models.target_sound',         []),
    ('front.models.voucher',              []),
    # Depends on front.models.mission being init'd first.
    ('front.data.audio_regions',          ['audio_regions_file']),
    ('front.data.assets',                 []),
    ('front.backend.check_species',       ['checkspecies', 'local_scenes_dir']),
    ('front.resource.renderer_node',      ['renderer_auth_token']),
    ('front.resource.auth.password',      ['password.hash_rounds', 'signups_enabled']),
    ('front.resource.kiosk_node',         ['campaign_name.kiosk', 'campaign_name.demo']),
    ('front.backend.shop.stripe_gateway', ['stripe.secret_key']),
    ('front.models.shop',                 ['stripe.publishable_key'])
]

# Constants used when parsing config keys/values meant to be sent as parameters to template rendering.
TEMPLATE_CONFIG_PREFIX = "template."
TEMPLATE_CONFIG_ARGS = "__template_args"

# Initialize all of the modules which require configuration data or load data from disk.
def init_with_config(config):
    template_args = {}
    # Convert any boolean looking config values into real bool objects.
    for k,v in config.iteritems():
        if v == 'True' : config[k] = True
        if v == 'False': config[k] = False

        # Look for keys from the config (.ini file) that begin with "TEMPLATE_CONFIG_PREFIX".
        # If found, strip off the 'TEMPLATE_CONFIG_PREFIX' from the key and store those key/values in a private
        # key in the config object, TEMPLATE_CONFIG_ARGS.
        # e.g. template.some_key = some_value -> {"some_key": "some_value"}
        if k.startswith(TEMPLATE_CONFIG_PREFIX):
            template_args[k[len(TEMPLATE_CONFIG_PREFIX):]] = config[k]

    # Store any parsed template config arguments in a TEMPLATE_CONFIG_ARGS key so they are available already
    # parsed to the templating system.
    config[TEMPLATE_CONFIG_ARGS] = template_args

    # Iterate over every module listed in INIT_MODULES and pass any values
    # requested from the config object as positional arguments to init_module
    for module_name, config_props in INIT_MODULES:
        module = importlib.import_module(module_name)
        args = [config[prop] for prop in config_props]
        module.init_module(*args)

    # If sending of exceptions is enabled, configure the module.
    from front.lib import exceptions
    if config['send_exception_emails'] == True:
        exceptions.init_module(config['developer_email_address'])

## Version object
import subprocess, getpass
from datetime import datetime

class Version(object):
    VERSION_FILE = "version.txt"
    VERSION_DATE_FORMAT = "%Y%m%d%H%M%S"

    def __init__(self, rev, tag, date, dirty, username):
        self.rev = rev
        self.tag = tag
        self.date = date
        self.dirty = dirty
        self.username = username

    @classmethod
    def current_version(cls):
        # If the version file exists, load the version from that file.
        if os.path.exists(os.path.join(BASEDIR, cls.VERSION_FILE)):
            return cls.from_file(os.path.join(BASEDIR, cls.VERSION_FILE))

        # Otherwise generate the version from the current checkout.
        # This should only happen on a local dev machine.
        else:
            try:
                return cls.from_current_repo()
            except subprocess.CalledProcessError:
                return Version("invalid", "invalid", "20000101010101", False, "unknown")

    @classmethod
    def from_file(cls, full_path):
        with open(full_path) as f:
            return cls.from_string(f.readline().strip())

    @classmethod
    def from_string(cls, version_string):
        version_string, username = version_string.split(' ')

        parts = version_string.split(':')
        # Determine if the checkout was dirty.
        if len(parts) == 3:
            return Version(parts[0], parts[1], parts[2], False, username)
        else:
            return Version(parts[0], parts[1], parts[2], True, username)

    @classmethod
    def from_current_repo(cls):
        # Call out to the mercurial hg command line to get the current revision and tag name.
        hg_out = subprocess.check_output(['hg id -i -t'], shell=True, cwd=BASEDIR, stderr=subprocess.STDOUT)
        fields = hg_out.strip().split(" ")
        if len(fields) == 1:
            hg_rev = fields[0]
            hg_tag = 'NO_TAG'
        else:
            (hg_rev, hg_tag) = fields
        # If the revision ends with a + then the current checkout is dirty, make note of that and
        # strip the +
        if hg_rev.endswith("+"):
            hg_rev = hg_rev[:-1]
            is_dirty = True
        else:
            is_dirty = False

        date = datetime.utcnow().strftime(cls.VERSION_DATE_FORMAT)
        # getpass raises an exception if it is not implemented on the current platform.
        try:
            username = getpass.getuser()
        except:
            username = "unknown"
        return Version(hg_rev, hg_tag, date, is_dirty, username)

    def write(self, full_path):
        with open(full_path, "w") as f:
            f.write("%s" % self.file_str())

    @property
    def dt_date_utc(self):
        return datetime.strptime(self.date, self.VERSION_DATE_FORMAT)

    @property
    def dt_date_pst(self):
        return utils.utc_date_in_pst(self.dt_date_utc)

    def file_str(self):
        return "%s %s" % (self, self.username)

    # The 'safe' version of the version string does not contain the username.
    def __str__(self):
        if self.dirty:
            return "%s:%s:%s:dirty" % (self.rev, self.tag, self.date)
        else:
            return "%s:%s:%s" % (self.rev, self.tag, self.date)

# Initialize the constant.
VERSION = Version.current_version()
