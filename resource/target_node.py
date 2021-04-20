# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import http, resource

from front import target_image_types
from front.lib import get_uuid, xjson, utils, urls, s3
from front.backend import check_species
from front.models import target
from front.resource import decode_json, json_success_with_chips, json_bad_request

import logging
logger = logging.getLogger(__name__)

class TargetParentNode(resource.Resource):
    def __init__(self, request, rover):
        self.rover = rover

    @resource.POST(accept=xjson.mime_type)
    def create(self, request):
        """A POST request to /rover/<id>/target gets to this handler.
           The result is a new Target created for this Rover."""
        body, error = decode_json(request, required={
            'lat': float,
            'lng': float,
            'arrival_delta': int,
            'yaw': float,
            'pitch': float,
            'metadata': dict
        })
        if body is None: return error

        fields = {}
        fields['lat']      = body['lat']
        fields['lng']      = body['lng']
        fields['yaw']      = body['yaw']
        fields['pitch']    = body['pitch']
        fields['metadata'] = body['metadata']

        # This fires TARGET_CREATED event.
        t = target.create_new_target_with_constraints(request, self.rover,
                                                      arrival_delta=body['arrival_delta'], **fields)
        if t is None:
            return json_bad_request(utils.tr('Error when creating target.'))
        else:
            # Update the users last_accessed field.
            self.rover.user.update_last_accessed()

            # The new target will be returned via a chip.
            return json_success_with_chips(request, json_body=body)

    @resource.child('{target_id}')
    def target(self, request, segments, target_id):
        """Specific targets are handled by TargetNode"""
        return TargetNode(request, self.rover.targets[get_uuid(target_id)])

class TargetNode(resource.Resource):
    """ Class for handling requests on already-existing targets."""
    def __init__(self, request, target):
        self.target = target

    @resource.child()
    def check_species(self, request, segments):
        """/rover/<id>/target/<id>/check_species"""
        return CheckSpeciesNode(self.target), segments

    @resource.child()
    def abort(self, request, segments):
        """/rover/<id>/target/<id>/abort"""
        return AbortNode(self.target), segments

    @resource.child('download_image/{image_type}')
    def download_image(self, request, segments, image_type):
        """/rover/<id>/target/<id>/download_image"""
        return DownloadImageNode(self.target, image_type), segments

    @resource.child()
    def mark_viewed(self, request, segments):
        """/rover/<id>/target/<id>/mark_viewed"""
        return MarkViewedNode(self.target), segments

class CheckSpeciesNode(resource.Resource):
    """This class is a controller (in the MVC sense) for check_species requests"""
    def __init__(self, target):
        self.target = target
        
    @resource.POST(accept=xjson.mime_type)
    def check(self, request):
        body, error = decode_json(request, required={'rects': list})
        if body is None: return error

        # Detect any species visible in the rectangles regions sent by the client.
        (detected_species, error_msg) = check_species.identify_species_in_target(request, self.target, body['rects'])
        if detected_species is None:
            logger.error("Failed to identify species. [%s]", error_msg)
            return json_bad_request(utils.tr('Error in species identification.'))

        # Update the users last_accessed field.
        self.target.user.update_last_accessed()

        # The target rects have changed and will be updated via a chip.
        return json_success_with_chips(request, json_body=body)

class AbortNode(resource.Resource):
    """This class is a controller (in the MVC sense) for abort requests"""
    def __init__(self, target):
        self.target = target
        
    @resource.POST(accept=xjson.mime_type)
    def abort(self, request):
        # Check to make sure that this target can be aborted.
        if not self.target.can_abort():
            logger.error("Refusing to abort target. [%s][%d]", self.target.target_id, self.target.user.epoch_now)
            return json_bad_request(utils.tr('Cannot abort this target.'))

        # Ask the rover to abort this target (and any future targets.)
        self.target.rover.abort_target(self.target)

        # The targets have been deleted and will be removed via a chip.
        return json_success_with_chips(request)

class DownloadImageNode(resource.Resource):
    def __init__(self, target, image_type):
        self.target = target
        self.image_type = image_type

    @resource.GET()
    def download_image(self, request):
        # If the image_type is an unknown type or the secret species_id or this target does not have the
        # request image type, return an error.
        if self.image_type not in target_image_types.ALL or self.image_type == target_image_types.SPECIES:
            return http.bad_request([('content-type', 'text/html')], "Invalid image type.")
        image_url = str(self.target.images.get(self.image_type))
        if image_url is None:
            return http.bad_request([('content-type', 'text/html')], "Invalid image type.")

        # If the image is a local, prerendered scene there is no easy way to set the content-disposition
        # so just redirect back to the image itself.
        if image_url.startswith(urls.scenes_base()):
            return http.see_other(image_url)

        # Use a download filename based on the current date and time.
        filename = self.target.arrival_time_date.strftime('%Y_%m_%d_%H%M.jpg')
        # Construct the S3 URL with the content-distribution set to attachment so that the user's
        # browser will trigger a download.
        download_url = s3.generate_download_url(image_url, filename)
        if download_url is None:
            logger.warn("Unable to generate signed download URL from target image: %s" % image_url)
            return http.see_other(image_url)
        else:
            return http.see_other(download_url)

class MarkViewedNode(resource.Resource):
    """This class is a controller (in the MVC sense) for mark_viewed requests"""
    def __init__(self, target):
        self.target = target

    @resource.POST(accept=xjson.mime_type)
    def mark_viewed(self, request):
        # Mark the target as viewed and issue a MOD chip.
        self.target.mark_viewed()

        # The target rects have changed and will be updated via a chip.
        return json_success_with_chips(request)
