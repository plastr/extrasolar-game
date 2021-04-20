# Copyright (c) 2010-2014 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import db, edmodo
from front.models import user as user_module

def get_classroom_data(request, access_token, user_token, use_sandbox):
    """
    :param request: The Request object
    :param access_token: The 24-hour access token for the teacher requesting access to the data.
    :param user_token: The Edmodo unique ID for the teacher requesting access to the data.
    :param use_sandbox: A Boolean indicating whether the Edmodo API calls should go to the sandbox server.
    Returns a struct with data for all classroom members and progress. Example output:
        {'error':'error message',
         'columns':[{'label':'Name', 'key':'name', 'type':'string', 'tooltip':'The name of the rover driver'}, ...]
         'groups':['title':'Science 101', 'members':[
            {'name':'Jenny Jones', 'last_active':'2 days ago', 'MSG_SCI_PHOTOSYNTHESISa':0,
            'MSG_SCI_PHOTOSYNTHESISb':0, 'MSG_SCI_VARIATIONb':0, 'MSG_SCI_FLIGHTb':0, ...}, ...
          ], ...]
        }
    """
    # DEBUG: It may be useful to just return the access tokens.
    #return {'access_token':access_token, 'user_token':user_token, 'use_sandbox':use_sandbox}

    # We need to use different servers and secret keys, depending on if this request is
    # coming from the Edmodo sandbox.
    conf = request.environ['front.config']
    edmodo_servers = conf['edmodo.servers'].split(',')
    edmodo_secret_keys = conf['edmodo.secret_keys'].split(',')
    if use_sandbox:
        server = edmodo_servers[0]
        secret_key = edmodo_secret_keys[0]
    else:
        server = edmodo_servers[1]
        secret_key = edmodo_secret_keys[1]

    try:
        # Initialize the Edmodo API helper.
        edmodoAPI = edmodo.EdmodoAPI(server=server, api_version='v1.1')
        # The first step in our chain of API commands is to get the teacher's groups.
        edmodo_groups = edmodoAPI.get_object('/groupsForUser', api_key=secret_key, access_token=access_token, user_token=user_token)
        all_group_ids = [str(group['group_id']) for group in edmodo_groups]
        edmodo_members = edmodoAPI.get_object('/members', api_key=secret_key, access_token=access_token, group_id=','.join(all_group_ids))
    except edmodo.EdmodoAPIError, e:
        return {'error':'Edmodo API Error: %s' % str(e)}

    # We send data for each column along with the payload so that these spoilers
    # don't appear in the JS/HTML for other players.
    result = {}
    result['columns'] = [
        {'label':'Name', 'key':'name', 'type':'string', 'tooltip':'The name of the rover driver'},
        {'label':'Active', 'key':'last_active', 'type':'string', 'tooltip':'How long has it been since this rover driver last accessed their account.'},
        {'label':'Distance', 'key':'distance', 'type':'string', 'tooltip':'Total distance this rover driver has traveled on the planet.'},
        {'label':'Photos', 'key':'photos_taken', 'type':'number', 'tooltip':'Total number of photos this rover driver has taken.'},
        {'label':'Tags', 'key':'tags', 'type':'string', 'tooltip':'Total number of items that the rover driver has attempted to tag in their photos and the number of successful identifications.'},
        {'label':'Plants', 'key':'tagged_plants', 'type':'number', 'tooltip':'Total number of photobiont (plant) species that this rover driver has identified.'},
        {'label':'Animals', 'key':'tagged_animals', 'type':'number', 'tooltip':'Total number of motobiont (animal) species that the rover driver has successfully identified.'},
        {'label':'Missions', 'key':'completed_missions', 'type':'number', 'tooltip':'Total number of missions that have been completed by this rover driver.'},
        {'label':'Blog&nbsp;1', 'key':'MSG_SCI_PHOTOSYNTHESISa', 'type':'check', 'tooltip':'This column is checked if the rover driver has received and read the message from Jane with the subject "Good work", which includes a link to her <a href="http://www.exoresearch.com/blog/exobiology/" target="_blank">blog post</a> about the biology basics for researching alien species.'},
        {'label':'Blog&nbsp;2', 'key':'MSG_SCI_PHOTOSYNTHESISb', 'type':'check', 'tooltip':'This column is checked if the rover driver has received and read the message from Jane with the subject "Oops", which includes a link to her <a href="http://www.exoresearch.com/blog/bio_methods/" target="_blank">blog post</a> about visual techniques for biological classification.'},
        {'label':'Blog&nbsp;3', 'key':'MSG_SCI_VARIATIONb', 'type':'check', 'tooltip':'This column is checked if the rover driver has received and read the message from Jane with the subject "Re: Variations on a Theme", which includes a link to her <a href="http://www.exoresearch.com/blog/variation/" target="_blank">blog post</a> about species variation.'},
        {'label':'Blog&nbsp;4', 'key':'MSG_SCI_FLIGHTb', 'type':'check', 'tooltip':'This column is checked if the rover driver has received and read the message from Jane with the subject "Re: Flight", which includes a link to her <a href="http://www.exoresearch.com/blog/convergent_evolution/" target="_blank">blog post</a> about convergent evolution.'},
    ]

    result['groups'] = []
    with db.conn(request) as ctx:
        for g in edmodo_groups:
            # Ignore groups where we don't have an install record.
            if not db.row(ctx, "edmodo_group_exists", group_id=g['group_id'], sandbox=(1 if use_sandbox else 0))['exist']:
                continue;
            # Each group has a title and an array of members.
            result_group = {'title':g['title'], 'members':[]}
            # Iterate over only the members in group g, appending member data into our group.
            for m in edmodo_members:
                if str(g['group_id']) == str(m['group_id']):
                    result_group['members'].append(_get_member_data(request, m))
            result['groups'].append(result_group)
    return result

def _get_member_data(request, member_data):
    """
    Given the data for a single member returned by a call to the /members Edmodo API,
    retrieve relevant details for player. Note that if the player hasn't signed in yet,
    there may not be a corresponding user in our database.
    """
    result = {'name':member_data['first_name'] + ' ' + member_data['last_name']}
    u = user_module.user_from_edmodo_uid(request, member_data['user_id'])
    if u:
        result['last_active'] = u.profile_approx_time_since_last_accessed()
        result['distance'] = str(u.profile_total_distance_traveled_rounded())+'m';
        result['photos_taken'] = len(u.all_picture_targets())
        result['tags'] = '%d/%d' % (len(u.all_image_rects()), len(u.all_image_rects_with_species()))
        result['completed_missions'] = len(u.missions.done(root_only=True))
        result['tagged_plants'] = len(u.species.plants())
        result['tagged_animals'] = len(u.species.animals())
        msg = u.messages.by_type('MSG_SCI_PHOTOSYNTHESISa')
        result['MSG_SCI_PHOTOSYNTHESISa'] = 1 if (msg and msg.was_read()) else 0
        msg = u.messages.by_type('MSG_SCI_PHOTOSYNTHESISb')
        result['MSG_SCI_PHOTOSYNTHESISb'] = 1 if (msg and msg.was_read()) else 0
        msg = u.messages.by_type('MSG_SCI_VARIATIONb')
        result['MSG_SCI_VARIATIONb'] = 1 if (msg and msg.was_read()) else 0
        msg = u.messages.by_type('MSG_SCI_FLIGHTb')
        result['MSG_SCI_FLIGHTb'] = 1 if (msg and msg.was_read()) else 0
    else:
        result['last_active'] = 'never'
        result['distance'] = '0m'
        result['tags'] = '0/0'
    return result

