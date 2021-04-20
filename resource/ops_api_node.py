# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
OpsAPINode is the main node for the game API.  Largely this file is about constructing
the gamestate object and getting it to the browser by various means.  The 
gamestate gets converted from its database representation to a JSON
structure here.
"""
from restish import resource

from front.lib import get_uuid, xjson
from front.models import user
from front.backend import gamestate
from front.resource import user_node, rover_node, message_node, progress_node, mission_node, species_node
from front.resource import achievement_node, invite_node, shop_node
from front.resource import json_success, json_success_with_chips

class OpsAPINode(resource.Resource):
    @resource.child()
    def gamestate(self, request, segments):
        return Gamestate()

    @resource.child()
    def fetch_chips(self, request, segments):
        return FetchChips()

    @resource.child()
    def user(self, request, segments):
        return user_node.UserParentNode(request), segments

    @resource.child('rover/{hexid}')
    def rover(self, request, segments, hexid):
        return rover_node.RoverNode(request, get_uuid(hexid)), segments

    @resource.child('message/{message_id}')
    def message(self, request, segments, message_id):
        return message_node.MessageParentNode(request, get_uuid(message_id)), segments

    @resource.child()
    def progress(self, request, segments):
        return progress_node.ProgressParentNode(request), segments

    @resource.child('mission/{mission_id}')
    def mission(self, request, segments, mission_id):
        return mission_node.MissionParentNode(request, mission_id), segments

    @resource.child('species/{species_id}')
    def species(self, request, segments, species_id):
        return species_node.SpeciesParentNode(request, species_id), segments

    @resource.child('achievement/{achievement_key}')
    def achievement(self, request, segments, achievement_key):
        return achievement_node.AchievementParentNode(request, achievement_key), segments

    @resource.child()
    def invite(self, request, segments):
        return invite_node.InviteParentNode(request), segments

    @resource.child()
    def shop(self, request, segments):
        return shop_node.ShopNode(), segments

class Gamestate(resource.Resource):
    """The url handler that simply returns the json serialization of the 
    gamestate.  This is intended to be hit by AJAX."""
    @resource.GET(accept=xjson.mime_type)
    def get(self, request):
        u = user.user_from_request(request)
        # Update the users last_accessed field.
        u.update_last_accessed()
        return json_success(gamestate.gamestate_for_user(u, request))

class FetchChips(resource.Resource):
    """Handle the /fetch_chips request from the client by grabbing everything from
    the chips table that is more recent than last_seen_chip_time."""
    @resource.GET(accept=xjson.mime_type)
    def get(self, request):
        return json_success_with_chips(request)
