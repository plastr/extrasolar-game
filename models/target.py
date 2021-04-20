# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import logging
import uuid
from collections import Counter
from datetime import timedelta

from front import models, target_image_types, Constants
from front.backend import deferred
from front.callbacks import run_callback, TARGET_CB
from front.lib import db, get_uuid, urls, gametime, event, utils, geometry
from front.models import chips, image_rect, target_sound, species as species_module


logger = logging.getLogger(__name__)

def create_new_target_with_constraints(ctx, rover, arrival_delta, scene=None, **params):
    """
    This creates a new Target object for the given Rover and persists it. These are
    used to describe a target location on the map where a Rover has gone.
    As opposed to create_new_target, this function verifies that the Target to be created
    meets the game constraints for the time between arrival_time and start_time, as well as
    the maximum distance a Target may travel from the previous Target.
    Note that all targets created with this function will have the user_created flag set to 1.
    Returns the newly created Target object.
    If there was an unrecoverable error in the constaint/validation code, None will be returned and
    no target will be created.

    :param arrival_delta: int The number of seconds the client is requesting from 'now' that this
        target should be arrived at. This is just a request from the client, the server may constrain
        this value when computing the true arrival_time for various reasons.
    NOTE: start_time and arrival_time should NOT be provided to this function, only arrival_delta.
    NOTE: See create_new_target documentation for details on remaining parameters.
    """
    # Create the target_id now so that it is available for logging in the validate_new_target_params callback.
    target_id = uuid.uuid1()

    # Validate and constrain the client supplied data by calling into target_callbacks
    params = run_callback(TARGET_CB, "validate_new_target_params", ctx=ctx, user=rover.user, rover=rover,
                           arrival_delta=arrival_delta, target_id=target_id, params=params)
    # If there was an unrecoverable error in the constaint/validation code, None will be returned.
    if params is None:
        return None
    else:
        # And now actually create the target.
        return create_new_target(ctx, rover, user_created=1, scene=scene, _target_id=target_id, **params)

def create_new_target(ctx, rover, user_created=0, scene=None, _target_id=None, **params):
    """
    This creates a new Target object for the given Rover and persists it. These are
    used to describe a target location on the map where a Rover has gone.
    Returns the newly created Target object.

    :param ctx: The database context.
    :param rover: Rover The rover which owns this target.
    :param user_created: 0/1 boolean, indicates whether this target was created by the user or the 'system'
        for instance the first rover target or initial rover photos.
    :param scene: Scene Optionally pass a Scene object to attach its photos to this target.
    :param _target_id: If a previous function has already created a target_id, it may be passed through
        via this private param. Only intended to be used by create_new_target_with_constraints.

    Required fields in params:
    :param start_time: int When the rover left this target to go to the next target, in number of seconds since user.epoch_now.
    :param arrival_time: int When the rover arrived at this target, in number of seconds since user.epoch_now.
    :param lat: float The latitude of this target on the map.
    :param lng: float The longitude of this target on the map.

    Optional fields in params:
    :param yaw: float The yaw this target was facing. Defaults to 0.0.
    :param pitch: float The pitch angle this target reflects. Defaults to 0.0.
    :param picture: int Whether this target does or will have an image associated with it (1 or 0).
        Defaults to 1.
    :param processed: int Whether this target has had its image rendered and is available to be
        displayed (1 or 0). Defaults to 0.
    :param viewed_at: datetime When this target was first viewed by the user. Defaults to None which
        indicates this target has not been viewed.
    :param locked_at: datetime When this target was locked for rendering. Defaults to None which
        indicates this target is not locked.
    :param metadata: dict The initial keys and optional values to populate in this targets metadata
        field. Note that the values cannot be None, but they can be empty strings. Defaults to
        an empty dictionary.
    """
    assert params.get('start_time') != None
    assert params.get('arrival_time') != None
    assert params.get('lat') != None
    assert params.get('lng') != None
    params.setdefault('yaw', 0.0)
    params.setdefault('pitch', 0.0)
    params.setdefault('picture', 1)
    params.setdefault('processed', 0)
    params.setdefault('classified', 0)
    params.setdefault('highlighted', 0)
    params.setdefault('seq', 0)
    params.setdefault('viewed_at', None)
    params.setdefault('locked_at', None)
    params.setdefault('metadata', {})
    assert params.get('target_id') is None
    # If the target_id was not assigned (by create_new_target_with_constraints for instance) then create it now.
    if _target_id is None:
        params['target_id'] = uuid.uuid1()
    # Otherwise use the supplied private value.
    else:
        params['target_id'] = _target_id
    # Insert the server only fields.
    params['user_created'] = user_created
    params['neutered'] = 0
    params['render_at'] = rover.user.after_epoch_as_datetime(params['start_time'])

    with db.conn(ctx) as ctx:
        # rover_id is only used when creating the Target in the database, it is not loaded
        # by chips as the rover.targets collection takes care of assigning a Rover to a Target.
        db.run(ctx, "insert_target", user_id=rover.user.user_id, rover_id=rover.rover_id, created=gametime.now(), **params)
        # If supplied a scene, pass it to the constructor as the images field.
        if scene is not None:
            params['images'] = scene.to_struct()
        t = rover.targets.create_child(user_id=rover.user.user_id, rover_id=rover.rover_id, **params)

        # If supplied with metadata, insert it into the database.
        if len(params['metadata']) > 0:
            for k,v in params['metadata'].iteritems():
                t._insert_metadata(k,v)

        # If supplied a scene, insert it into the database for this Target.
        if scene is not None:
            assert t.is_processed(), "Refusing to create an unprocessed target with a scene [%s]" % rover.user.user_id
            if t.has_been_arrived_at(leeway_seconds=Constants.TARGET_DATA_LEEWAY_SECONDS):
                t._insert_scene(ctx, scene)
            # If the target has not been arrived at, use mark_processed_with_scene so that the MOD chip
            # with the image data is queued (since this target is most likely not going to be processed by the renderer)
            else:
                t.mark_processed_with_scene(scene, t.metadata, classified=t.classified)

        # Issue the ADD chip.
        t.send_chips(ctx, rover.user)
        # Dispatch the target_created event to the callback system.
        event.dispatch(ctx, rover.user, event.types.TARGET_CREATED, None, t)
        # If the just created target has a previous target that has been arrived at and if this new target
        # has not been arrived at (excluding the initial targets created in the past)
        # then dispatch the TARGET_EN_ROUTE event for this target as the rover begins to immediatly move towards it.
        # See deferred.py to see how the TARGET_EN_ROUTE event is dispatched for other targets.
        prev_target = t.previous()
        if prev_target is not None and prev_target.has_been_arrived_at() and not t.has_been_arrived_at():
            event.dispatch(ctx, rover.user, event.types.TARGET_EN_ROUTE, None, t)

        # Create a deferred action to trigger the arrived_at_target event.
        delay = rover.user.seconds_between_now_and_after_epoch(t.arrival_time)
        # It is unsupported to have a user created target arriving in the past.
        if t.was_user_created() and delay <= 0:
            raise Exception("Cannot support user created targets in the past (no time travel!) [%s]" % t.rover.user.user_id)
        # If this target has not yet been arrived at, queue a deferred action to trigger the arrived_at_target event.
        if delay > 0:
            # The subtype for the deferred event is a string representation of the target_id UUID.
            target_id_subtype = str(t.target_id).replace('-', '')
            # Only allow one target_arrived deferred per target_id
            if not deferred.is_queued_to_run_later_for_user(ctx, deferred.types.TARGET_ARRIVED, target_id_subtype, rover.user):
                deferred.run_later(ctx, deferred.types.TARGET_ARRIVED, target_id_subtype, rover.user, delay)
        # NOTE: If this is a non user created target (like initial rover targets and photos created by the system)
        # that was arrived at in the PAST then NO arrived_at_target event will be fire.
    return t

class TargetRow(object):
    """ This mixin class holds useful helper methods and similar code that only depends on the inheriting class
        having access to the 'basic' target database data: all the targets table fields as well as the images and
        metadata dictionaries. It does not depend on being in the rover targets collection, therefore it cannot
        depend on a 'parent' property nor can it depend on having a 'sounds' or 'image_rects' collection. """
    @property
    def url_image_thumbnail(self):
        return self._image_url(target_image_types.THUMB)
    @property
    def url_image_photo(self):
        return self._image_url(target_image_types.PHOTO)
    @property
    def url_image_infrared(self):
        return self._image_url(target_image_types.INFRARED)
    @property
    def url_image_species(self):
        return self._image_url(target_image_types.SPECIES)
    @property
    def url_image_wallpaper(self):
        return self._image_url(target_image_types.WALLPAPER)

    @property
    def url_public_photo(self):
        return urls.target_public_photo(self.target_id)

    @property
    def url_admin(self):
        return urls.admin_target(self.target_id)

    def was_user_created(self):
        """ Returns True if this target was created by the user, as opposed to having been created
            by the system, either in the initial user creation or initial rover location etc. """
        return self.user_created == 1

    def is_locked(self):
        return self.locked_at != None

    def is_picture(self):
        return self.picture == 1

    def is_processed(self):
        return self.processed == 1

    def is_neutered(self):
        return self.neutered == 1

    def is_classified(self):
        return self.classified == 1

    def is_highlighted(self):
        return self.highlighted == 1

    def is_panorama(self):
        return 'TGT_FEATURE_PANORAMA' in self.metadata

    def is_infrared(self):
        return 'TGT_FEATURE_INFRARED' in self.metadata

    def was_viewed(self):
        return self.viewed_at != None

    def _image_url(self, image_type):
        url = self.images.get(image_type, None)
        if url is None: return ""
        else:           return url

class Target(chips.Model, TargetRow, models.UserChild):
    id_field = 'target_id'
    fields = frozenset(['start_time', 'arrival_time', 'lat', 'lng', 'yaw', 'pitch',
                        'picture', 'processed', 'classified', 'user_created', 'neutered', 'highlighted', 'viewed_at',
                        'can_abort_until', 'images', 'metadata', 'seq', 'locked_at', 'render_at', 'user_id', 'rover_id'])
    computed_fields = {
        'start_time_date'  : models.EpochDatetimeField('start_time'),
        'arrival_time_date': models.EpochDatetimeField('arrival_time'),
        'viewed_at_date'   : models.EpochDatetimeField('viewed_at'),
    }
    collections = frozenset(['sounds', 'image_rects'])
    server_only_fields = frozenset(['user_id', 'rover_id', 'user_created', 'neutered', 'seq', 'locked_at', 'render_at'])
    # A target metadata key prefix that should only be visible on the server. (renderer bookkeeping data)
    server_only_metadata_key_prefix = 'TGT_RDR_'

    images = chips.LazyField("images",  lambda m: m._load_images())
    metadata = chips.LazyField("metadata", lambda m: m._load_target_metadata())

    # user_id, rover_id, created and updated are database only fields.
    def __init__(self, target_id, user_id, rover_id, created=None, updated=None, **params):
        # If the UUID data is coming straight from the database row, convert it to a UUID instance.
        target_id = get_uuid(target_id)
        user_id = get_uuid(user_id)
        rover_id = get_uuid(rover_id)
        # Either an epoch delta time (an integer) which is the deadline past which a target cannot be aborted
        # or None, indicating this target can never be aborted.
        can_abort_until = run_callback(TARGET_CB, "target_can_abort_until", target_id=target_id, params=params)
        super(Target, self).__init__(target_id=target_id, user_id=user_id, rover_id=rover_id, can_abort_until=can_abort_until,
                                     sounds = TargetSoundCollection.load_later('sounds', self._load_target_sounds),
                                     image_rects = ImageRectCollection.load_later('image_rects', self._load_image_rects),
                                     **params)
    @property
    def rover(self):
        # self.parent is rover.targets, the parent of that is the rover itself
        return self.parent.parent

    @property
    def user(self):
        return self.rover.user

    def previous(self):
        """ Return the previous/earlier target or None if this is the first target.
            NOTE: This currently only traverses the targets for this target's rover, not all rover's targets. """
        targets = self.rover.targets.by_arrival_time()
        index_prev = targets.index(self) - 1
        if index_prev < 0:
            return None
        else:
            return targets[index_prev]

    def next(self):
        """ Return the next/later target to this one or None if this is the last target.
            NOTE: This currently only traverses the targets for this target's rover, not all rover's targets. """
        targets = self.rover.targets.by_arrival_time()
        index_next = targets.index(self) + 1
        if index_next > (len(targets) - 1):
            return None
        else:
            return targets[index_next]

    def traverses_region(self, region):
        """ Returns True if this target traverses the given RegionGeometry object. """
        previous = self.previous()
        # If this is the first target, determine if it is inside of the region.
        if previous is None:
            return self.is_inside_region(region)
        else:
            return region.coords_traverse([previous.lat, previous.lng], [self.lat, self.lng])

    def is_inside_region(self, region):
        """ Returns True if this target is inside of the given RegionGeometry object. """
        return region.point_inside(self.lat, self.lng)

    def straight_distance_between_targets(self, other):
        """ Returns the distance, in meters, between this target and the given target.
            NOTE: This is the direct distance between them, it does not factor in any targets
            between these two targets, if any. See rover.distance_traveled for that code. """
        return geometry.dist_between_lat_lng(self.lat, self.lng, other.lat, other.lng)

    def can_abort(self):
        """ Returns True if this target is allowed to be aborted, False otherwise. """
        if self.can_abort_until is None:
            return False
        else:
            return self.can_abort_until >= self.user.epoch_now

    def lock_for_processing(self):
        """ Lock this target for render processing. Will issue warning log if already locked. """
        if self.is_locked():
            logger.warn("Breaking lock on Target: %s locked_at:[%s] %s",
                self, self.locked_at, self.user)

        with db.conn(self.ctx) as ctx:
            locked_at = gametime.now()
            db.run(ctx, "update_target_locked_at", target_id=self.target_id, locked_at=locked_at)
            self.locked_at = locked_at  # Make our state mirror the database's.
            # No reason to send a chip since this field is not serialized.

    def has_been_arrived_at(self, leeway_seconds=0):
        return self.user.epoch_now >= self.arrival_time - utils.in_seconds(seconds=leeway_seconds)

    def mark_processed_with_scene(self, scene, metadata, classified=0):
        """
        Mark this target as processed with the supplied Scene for the processed images.
        This will issue a future chip (delivered at this Target's arrival_time) for the
        changes to the processed flag and images list. The Target will also be unlocked.
        :param metadata: Provide the metadata dictionary of keys and values to associate
        with this target. These will be merged with any existing metadata values. If there
        is no metadata, supply an empty dictionary.
        NOTE: It is not supported to delete metadata keys, so the supplied metadata dictionary
        keys must contain at least all of the keys in the current metadata value.
        :param classified: Optionally provide a value for the 'classified' field if this
        target image contains classified information. Defaults to 0, meaning not classified.
        """
        with db.conn(self.ctx) as ctx:
            # Add the scene to the target.
            self._insert_scene(ctx, scene)

            ## And if the metadata has changed:
            # Any new metadata keys need to be inserted and any metadata keys whose value has changed
            # need to be updated.
            # And 'set' the value on the target object which will trigger a MOD chip for the metadata field.
            old_metadata = self.metadata
            if metadata != old_metadata:
                # There must not be any keys that were in the original metadata that do not exist in the
                # possibly new metadata value (it is not supported to delete metadata keys)
                deleted = set(old_metadata.keys()).difference(set(metadata.keys()))
                assert len(deleted) == 0, "Deleting a target metdata key is not supported."

                for k,v in metadata.iteritems():
                    if k not in old_metadata or old_metadata[k] != v:
                        # Insert the new key and value into the database.
                        self._insert_metadata(k, v)
                # Assign the renderer provided metadata dict to the metadata attribute to trigger a MOD chip.
                self.metadata = metadata
                self.send_chips(ctx, self.user)

            # Flag the target as unlocked and processed in the database.
            db.run(ctx, "update_target_unlock_and_processed", target_id=self.target_id, classified=classified)
            self.locked_at = None  # Make our state mirror the database's.
            self.set_silent(processed = 1)           # No reason to send chip as processed and classified
            self.set_silent(classified = classified) # will be set to 0 for pending targets.
            self.set_silent(images = scene.to_struct())

            # Send a future MOD chip with the target marked processed and with new images.
            new_params = {'processed':1, 'classified':classified, 'images':scene.to_struct_for_client()}
            deliver_at = self.arrival_time_date - timedelta(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)
            chips.modify_in_future(ctx, self.user, self, deliver_at=deliver_at, **new_params)

    def mark_as_neutered(self):
        """
        Mark this target as "neutered", meaning that the photo will never actually be
        rendered but it will appear to the client as a legitimate pending target.
        It is expected that some subsequent process, perhaps a deferred action,
        will delete this target before it should have been rendered, from the clients
        perspective.
        """
        with db.conn(self.ctx) as ctx:
            # Flag the target as processed in the database.
            db.run(ctx, "update_target_processed_for_neuter", target_id=self.target_id)
            self.processed = 1  # Make our state mirror the database's.
            self.neutered = 1
            # No reason to send chip as processed will be set to 0 for pending targets and neutered is server only.

    def mark_for_rerender(self):
        """
        Mark this target as not processed, meaning that the photo should be rerendered.
        """
        with db.conn(self.ctx) as ctx:
            # If the original render_at time is in the past, then update it to be 'now', mainly so alerting systems
            # know this target is being reprocessed.
            self.render_at = max(self.render_at, gametime.now())
            # Flag the target as not processed in the database.
            db.run(ctx, "update_target_processed_for_rerender", target_id=self.target_id, render_at=self.render_at)
            self.processed = 0  # Make our state mirror the database's.
            # No reason to send chip as we will allow the client to continue to show
            # the current images until rerendering can happen.

    def mark_viewed(self):
        with db.conn(self.ctx) as ctx:
            epoch_now = self.user.epoch_now
            db.run(ctx, "update_target_viewed_at", target_id=self.target_id, viewed_at=epoch_now)
            self.viewed_at = epoch_now # Make our state mirror the database's.
            self.send_chips(ctx, self.user)

    def mark_highlighted(self):
        """
        Mark this target as "highlighted". See backend.highlights module.
        """
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_target_highlighted', target_id=self.target_id, highlighted=1)
            self.highlighted = 1  # Make our state mirror the database's.
            self.send_chips(ctx, self.user)

    def mark_unhighlighted(self):
        """
        Un-mark this target as "highlighted"/remove highlighted flag. See backend.highlights module.
        """
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_target_highlighted', target_id=self.target_id, highlighted=0)
            self.highlighted = 0  # Make our state mirror the database's.
            self.send_chips(ctx, self.user)

    def species_count(self, only_subspecies_id=None):
        '''
        Returns a Counter object of the number of times a given species_id was
        detected in all targets for this user.
        :param only_subspecies_id: int, if included, limit counts to this subspecies type.
        '''
        count = Counter()
        for image_rect in self.image_rects.itervalues():
            count += image_rect.species_count(only_subspecies_id=only_subspecies_id)
        return count

    def subspecies_count_for_species(self, species_id):
        '''
        Returns a Counter object of the number of times a given subspecies_id was
        observed for the indicated species.
        :param species_id: int, the id of the species that we're interested in.
        '''
        count = Counter()
        for image_rect in self.image_rects.itervalues():
            count += image_rect.subspecies_count_for_species(species_id=species_id)
        return count

    def detected_species_in_rects(self, detected_species, detected_subspecies, rect_scores):
        """ Called when species have been detected in this target. Any chips required to update the
            user.species collection will be dispatched, as well as image_rect objects created. """
        # Update the user.species collection as required.
        target_ids = set([(self.rover.rover_id, self.target_id)])
        for species_id in detected_species:
            # Species which were too far away for detection are ignored.
            if not species_module.is_too_far_for_id(species_id):
                subspecies_ids = detected_subspecies[species_id]
                if species_id not in self.user.species:
                    # If this is a newly detected species, add it to the collection and issue an add chip.
                    species_module.add_new_species(self.ctx, self.user, species_id, subspecies_ids, target_ids)
                else:
                    # If this was a previously detected species, then we might need to update the target_ids
                    # list for that species object. Check to see if any of the target_ids (rover_id, target_id)
                    # pairings are new for this species. If so, issue a MOD chip for the species collection.
                    existing = self.user.species[species_id]
                    existing.add_target_ids(target_ids)
                    # If this was a previously detected species then we might need to update the subspecies
                    # collection. This will issue an ADD chip if any of these subspecies_ids are new.
                    existing.add_subspecies_ids(subspecies_ids)

        for rect_score in rect_scores:
            image_rect.create_new_image_rect_from_score(self.ctx, self, rect_score)

    def has_detected_sound(self, sound_key):
        """ Return true if the indicated sound_key has alraedy been detected for this target, false otherwise. """
        return sound_key in self.sounds

    def detected_sound(self, sound_key):
        """ Mark this target has having detected/recorded the given sound. An ADD chip will be issued
            for arrival_time unless already arrived.
            See target_sound.create_new_target_sound for more information. """
        sound = target_sound.create_new_target_sound(self.ctx, self, sound_key)
        return sound

    def add_metadata(self, key, value=''):
        """ Add a metadata key and optional value to this target. This will replace any existing key and value
            already associated with this target and trigger a MOD chip. """
        # Insert the new key and value into the database.
        self._insert_metadata(key, value)
        # Update the models metadata dictionary with the new key and value.
        self.metadata[key] = value
        # Then assign that back to the metadata attribute to trigger a MOD chip.
        self.metadata = self.metadata
        self.send_chips(self.ctx, self.user)

    def add_metadata_unique(self, key, value=''):
        """ Add a metadata key and optional value to this target. The key is expected to be unique across all
            targets for this user. If the key is already present on an existing target, then the key will not
            be added to the target and False will be returned. Otherwise the key and value will be added and
            True will be returned."""
        if self.user.has_target_with_metadata_key(key):
            return False
        else:
            self.add_metadata(key, value)
            return True

    def to_struct_renderer_input(self):
        struct = self.to_struct(fields=['arrival_time', 'start_time', 'lat', 'lng', 'yaw', 'pitch',
                                        'picture', 'processed', 'metadata'])
        # The renderer is expecting start_time_date and arrival_time_date as seconds since the 1970 epoch
        struct['start_time_date'] = self.start_time_date
        struct['arrival_time_date'] = self.arrival_time_date
        return struct

    def to_struct_public(self):
        # Return a dict containing all of the 'public API' fields, ready to be JSONified.
        return {
            'target_id': self.target_id,
            'url_photo': self.url_image_photo,
            'url_infrared': self.url_image_infrared,
            'url_thumbnail': self.url_image_thumbnail,
            'url_public_photo': self.url_public_photo,
            'url_image_wallpaper': self.url_image_wallpaper
        }

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'check_species':urls.rover_target_check_species(self.rover.rover_id, self.target_id),
                'abort_target':urls.rover_target_abort(self.rover.rover_id, self.target_id),
                'mark_viewed':urls.rover_target_mark_viewed(self.rover.rover_id, self.target_id),
                'public_photo':self.url_public_photo,
                'download_image':urls.rover_target_download_image(self.rover.rover_id, self.target_id)
            }

        # Remove the image URLs and set processed and classified to 0 to inform the client that the target
        # that the image data is not available until arrival_time and hide it from prying eyes.
        # Add a 30 second leeway so that the URLs can be made available close to the time they
        # will be needed by the client incase the user loads the gamestate very close to arrival_time
        # but before the MOD chip has arrived.
        if not self.has_been_arrived_at(leeway_seconds=Constants.TARGET_DATA_LEEWAY_SECONDS):
            if 'processed' in struct:  struct['processed'] = 0
            if 'classified' in struct: struct['classified'] = 0
            if 'images' in struct:     struct['images'] = {}
            # Sound data is also hidden until arrival.
            # NOTE: sounds is a proper collection so this is a very heavy handed move to wipe it
            # out but no other mechanism currently exists to hide data in a collection.
            if 'sounds' in struct:     struct['sounds'] = {}
        # The client/gamestate never gets to see the species identification image.
        if 'images' in struct:
            if target_image_types.SPECIES in struct['images']:
                del struct['images'][target_image_types.SPECIES]
        # Remove any server only metadata keys.
        if 'metadata' in struct:
            for k in struct['metadata'].keys():
                if k.startswith(self.server_only_metadata_key_prefix):
                    del struct['metadata'][k]
        return struct

    def _insert_scene(self, ctx, scene):
        """
        Insert all images in a scene for this target, adding each image type required.
        :param ctx: The database context.
        :param scene: A Scene object holding all of the image URLs for this scene.
        """
        self._insert_image(ctx, target_image_types.PHOTO, scene.photo)
        self._insert_image(ctx, target_image_types.THUMB, scene.thumb)
        self._insert_image(ctx, target_image_types.SPECIES, scene.species)
        # Some scene types are options.
        if scene.wallpaper != None:
            self._insert_image(ctx, target_image_types.WALLPAPER, scene.wallpaper)
        if scene.infrared != None:
            self._insert_image(ctx, target_image_types.INFRARED, scene.infrared)
        if scene.thumb_large != None:
            self._insert_image(ctx, target_image_types.THUMB_LARGE, scene.thumb_large)

    def _insert_image(self, ctx, image_type, url):
        assert image_type in target_image_types.ALL
        # We us an insert_or_update query in case we need to rerender a bad target image.
        db.run(ctx, "insert_or_update_target_image",
               user_id=self.user.user_id, target_id=self.target_id, type=image_type, url=url, created=gametime.now())

    def _insert_metadata(self, key, value=""):
        """ Insert the given metadata key (and optional value) into the database.
            NOTE: This does NOT handle chips for the 'metadata' target property which should be handled
            by the caller. """
        assert key.startswith("TGT_"), "Metadata keys must start with a TGT_ prefix."
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'insert_or_update_target_metadata', user_id=self.user.user_id, target_id=self.target_id,
                   key=key, value=value, created=gametime.now())

    def _load_target_sounds(self):
        with db.conn(self.ctx) as ctx:
            rows = ctx.row_cache.get_rows_from_query("gamestate/select_target_sounds_by_user_id", self.target_id)
            if rows is not None:
                return rows
            else:
                return db.rows(ctx, "select_target_sounds", target_id = self.target_id)

    def _load_image_rects(self):
        with db.conn(self.ctx) as ctx:
            rows = ctx.row_cache.get_rows_from_query("gamestate/select_target_image_rects_by_user_id", self.target_id)
            if rows is not None:
                return rows
            else:
                return db.rows(ctx, "select_target_image_rects", target_id = self.target_id)

    ## Lazy load attribute methods.
    def _load_images(self):
        """ Returns information about a taken image for this target.  Returns a
        single dict of the form:  {'PHOTO':'http:////', 'SPECIES'...}
        """
        with db.conn(self.ctx) as ctx:
            rows = ctx.row_cache.get_rows_from_query("gamestate/select_target_images_by_user_id", self.target_id)
            if rows is None:
                rows = db.rows(ctx, "select_target_images", target_id=self.target_id)
        return dict(((r['type'], r['url']) for r in rows))

    def _load_target_metadata(self):
        with db.conn(self.ctx) as ctx:
            rows = ctx.row_cache.get_rows_from_query("gamestate/select_target_metadata_by_user_id", self.target_id)
            if rows is None:
                rows = db.rows(ctx, "select_target_metadata", target_id=self.target_id)
        return dict(((r['key'], r['value']) for r in rows))

class TargetSoundCollection(chips.Collection):
    model_class = target_sound.TargetSound

class ImageRectCollection(chips.Collection):
    model_class = image_rect.ImageRect

    def next_seq(self):
        """ Returns the next seq value to assign to a new image rect in this collection. """
        for i in range(0, len(self)):
            # Assert that each seq is assigned in order and there are no gaps.
            assert i in self
        # Return the next valid seq, which we now know is the next 0-based index value.
        return (len(self) - 1) + 1
