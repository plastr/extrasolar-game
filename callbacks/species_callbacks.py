# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.

from front import species_types
from front.lib import utils
from front.models import species as species_module
from front.models import message as message_module
from front.callbacks import mission_callbacks

import logging
logger = logging.getLogger(__name__)

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def minutes_until_available(cls, species_type, species_id):
        """
        A callback which returns the number of minutes after the species was first identified that all of
        its 'real' descriptive information should be made available to the user.
        :param species_type: The species type field. The Species instance is not available as this callback
            is called inside of __init__.
        Returns the number of minutes after first detection the data should be available. Can return 0.
        """
        if species_module.is_too_far_for_id(species_id):
            return 0
        if species_type == species_types.MANMADE:
            return 0
        return 30

    @classmethod
    def unidentified_info(cls, species):
        """
        If this species is delaying certain information to the client when first identified, return
        the placeholder overrides in a dict from this callback.
        """
        if species.is_organic():
            return {
                'name': utils.tr("Pending analysis at XRI"),
                'description': utils.tr("This species has not been seen before. Our scientists are working to identify it and will update this information soon."),
                'science_name': None,
                'icon': 'SPC_ICON_PENDING'
            }
        else:
            return {
                'name': utils.tr("Pending analysis at XRI"),
                'description': utils.tr("We are unable to identify this object. Our scientists are working to identify it and will update this information soon."),
                'science_name': None,
                'icon': 'SPC_ICON_PENDING'
            }

    @classmethod
    def score_from_density(cls, species_id, subspecies_id, species_type, density, target_species_count, all_species_count):
        """
        A callback which is called whenever a given species is being identified in a target image to
        determine the 'score' that should be applied to that species. This determines which species
        in the same rectangle are selected as the 'detected' ones.
        Returns a float between 0.0 and 1.0.
        :param species_id: The species_id field.
        :param subspecies_id: The subspecies_id field of the identified species.
        :param species_type: The species type field e.g. MANMADE.
        :param density: float The density (pixels per region) of this species being identified in the target.
        :param target_species_count: Counter A mapping of how often this species_id has already been
            identified in this target.
        :param all_species_count: Counter A mapping of how often this species_id has already been
            identified in all the user's targets.
        """
        weight = 1.0
        if species_type == species_types.ANIMAL:
            weight = 1.2
        # manmade or alien artifacts 'weigh' more than organics.
        elif species_type == species_types.MANMADE:
            weight = 1.5
        elif species_type == species_types.ARTIFACT:
            weight = 1.8

        score = density * weight
        # Clamp the score between 0.0 and 1.0
        if score > 1.0:
            score = 1.0
        elif score < 0.0:
            score = 0.0
        return score

    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        """
        A callback which is called whenever a given species is identified in a target image.
        :param ctx: The database context.
        :param user: The User who owns this species.
        :param target: The target where the identification happened.
        :param identified: The Species which was detected/identified.
        :param subspecies: The set of subspecies_ids that were detected/identified (at most 1 currently).
        """
        return

class SPC_PLANT032_Callbacks(BaseCallbacks):
    ''' Tagging the gordy tree kicks off a series of missions. '''
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        mission_callbacks.send_sci_cellular_start_messages(ctx, user, identified.species_id)

# When all of the following 3 species have been tagged, it should trigger MSG_SCI_VARIATIONc
class SPC_PLANT012_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        mission_callbacks.send_sci_variation_message(ctx, user)

class SPC_PLANT033_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        mission_callbacks.send_sci_variation_message(ctx, user)

class SPC_PLANT034_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        mission_callbacks.send_sci_variation_message(ctx, user)

# Tagging the starspore kicks off MIS_SCI_FLOWERS.
class SPC_PLANT028_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        if not user.messages.has_been_queued_or_delivered('MSG_SCI_FLOWERSa'):
            # Jane: What do these "flowers" do?
            message_module.send_later(ctx, user, 'MSG_SCI_FLOWERSa', utils.in_seconds(minutes=35))

# Any of the following 3 species should trigger MIS_SCI_BIOLUMINESCENCE
class SPC_PLANT015_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        mission_callbacks.trigger_sci_bioluminescence(ctx, user, identified.species_id)

class SPC_PLANT022_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        mission_callbacks.trigger_sci_bioluminescence(ctx, user, identified.species_id)

class SPC_PLANT031_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        mission_callbacks.trigger_sci_bioluminescence(ctx, user, identified.species_id)

# Tagging the sail flyer kicks off MIS_SCI_FLIGHT.
class SPC_ANIMAL004_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        if not user.messages.has_been_queued_or_delivered('MSG_SCI_FLIGHTa'):
            # Jane: Find x3
            message_module.send_later(ctx, user, 'MSG_SCI_FLIGHTa', utils.in_seconds(minutes=35))

# Tagging the aquatics in the swimming rover image.
class SPC_ANIMAL65535_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        if not subspecies and not user.messages.has_been_queued_or_delivered('MSG_JANE_AQUATIC_ANIMAL'):
            # Jane: What happened? motobionts?
            message_module.send_later(ctx, user, 'MSG_JANE_AQUATIC_ANIMAL', utils.in_seconds(minutes=30))

# Tagging any plant in the S1 finale image triggers a message from Jane.
class SPC_PLANT65535_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, target, identified, subspecies):
        if not subspecies and not user.messages.has_been_queued_or_delivered('MSG_JANE_S1_ISLAND2'):
            # Jane: Where was this even taken?
            message_module.send_later(ctx, user, 'MSG_JANE_S1_ISLAND2', utils.in_seconds(minutes=30))

