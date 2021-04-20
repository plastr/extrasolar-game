# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import csv
from restish import http, resource, templating

from front import VERSION, gift_types
from front.lib import get_uuid, utils, forms, xjson, urls, gametime, money
from front.data import assets
from front.models import user as user_module
from front.models import invite as invite_module
from front.backend import admin, stats, highlights, gamestate, renderer
from front.resource import decode_json, json_success, json_bad_request
from front.backend.admin import ADMIN_INVITER_EMAIL, ADMIN_INVITER_FIRST_NAME, ADMIN_INVITER_LAST_NAME

# Show recent users on the /admin page who have accessed the site within this number of hours ago.
RECENT_USERS_SINCE_HOURS = 48
# The maximum number of recent users to show, even if there are more that meet the RECENT_USERS_SINCE_HOURS
RECENT_USERS_LIMIT = 200
# The maximum number of recent targets to show on /admin page.
RECENT_TARGETS_LIMIT = 50
# The oldest target which will be shown on a recent targets table. This is used to cut down the overall
# number of target rows that need to be examined, since using LIMIT does not do this, and greatly speeds
# up these queries in production.
OLDEST_RECENT_TARGET_DAYS = 5
# The maximum number of recent transactions to show on /admin page.
RECENT_TRANSACTIONS_LIMIT = 3

class AdminNode(resource.Resource):
    @resource.child()
    def api(self, request, segments):
        """Handles everything under /admin/api"""
        return APINode()

    @resource.GET()
    @templating.page('admin/index.html')
    def index(self, request):
        params = {
            'current_version': VERSION,
            'oldest_recent_target_days': OLDEST_RECENT_TARGET_DAYS
        }
        return params

    @resource.POST()
    def lookup(self, request):
        ok, fields = forms.fetch(request, ['user_search_term'])
        if ok:
            user_search_term = fields['user_search_term']
            return http.see_other(urls.add_query_param_to_url(urls.admin_search_users_with_term(user_search_term)))
        else:
            return http.bad_request([('content-type', 'text/html')], "Bad parameters. No search query term provided.")

    @resource.child()
    def recent_users_and_targets_html(self, request, segments):
        return RecentUsersAndTargets()

    @resource.child('search_users')
    def search_users(self, request, segments):
        return AdminSearchUsersNode()

    @resource.child('user/{user_id}')
    def user(self, request, segments, user_id):
        return AdminUserNode(request, get_uuid(user_id))

    @resource.child('user/{user_id}/map')
    def user_map(self, request, segments, user_id):
        return AdminUserMapNode(request, get_uuid(user_id))

    @resource.child('target/{target_id}')
    def target(self, request, segments, target_id):
        return AdminTargetNode(request, get_uuid(target_id))

    @resource.child('invoice/{invoice_id}')
    def invoice(self, request, segments, invoice_id):
        return AdminInvoiceNode(request, get_uuid(invoice_id))

    @resource.child('gifts')
    def gifts(self, request, segments):
        return AdminGiftsNode()

    @resource.child('invites')
    def invites(self, request, segments):
        return AdminInvitesNode()

    @resource.child('users')
    def users(self, request, segments):
        return AdminUsersNode()

    @resource.child('targets')
    def targets(self, request, segments):
        return AdminTargetsNode()

    @resource.child('transactions')
    def transactions(self, request, segments):
        return AdminTransactionsNode()

    @resource.child('deferreds')
    def deferreds(self, request, segments):
        return AdminDeferredsNode()

    @resource.child('email_queue')
    def email_queue(self, request, segments):
        return AdminEmailQueueNode()

    @resource.child('stats')
    def stats(self, request, segments):
        return AdminStatsNode()

    @resource.child('stats/attrition')
    def attrition(self, request, segments):
        return AdminStatsAttritionNode()

    @resource.child('query')
    def query(self, request, segments):
        return AdminQueryNode()

class RecentUsersAndTargets(resource.Resource):
    @resource.GET(accept=xjson.mime_type)
    def recent_users_and_targets_html(self, request):
        recent_users = admin.recent_users(request, limit=RECENT_USERS_LIMIT, last_accessed_hours=RECENT_USERS_SINCE_HOURS)
        all_users_count = admin.all_users_count(request)
        recent_targets = admin.recent_targets(request, limit=RECENT_TARGETS_LIMIT, oldest_recent_target_days=OLDEST_RECENT_TARGET_DAYS)
        recent_transactions = admin.recent_transactions(request, limit=RECENT_TRANSACTIONS_LIMIT)
        all_transactions_money = admin.all_transactions_amount(request)
        all_transactions_money_display = money.format_money(all_transactions_money)
        params = {
            'recent_users': recent_users,
            'all_users_count': all_users_count,
            'all_transactions_money_display': all_transactions_money_display,
            'recent_targets': recent_targets,
            'recent_transactions': recent_transactions,
            'format_field': format_field,
            'format_email': format_email,
            'format_user_label': format_user_label,
            'format_utc': format_utc
        }
        return json_success({
            'recent_users_html': templating.render(request, 'admin/recent_users.html', params),
            'recent_targets_html': templating.render(request, 'admin/recent_targets.html', params),
            'recent_transactions_html': templating.render(request, 'admin/recent_transactions.html', params)
        })

class AdminSearchUsersNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/search_users.html')
    def search_users(self, request):
        limit = 500
        # If there was a no_user param add an error message
        search_term = request.GET.get('search_term', None)
        if search_term is None:
            return {'error': utils.tr("No search query term provided.")}
        search_term = search_term.strip()
        found_users = admin.search_for_users(request, search_term, limit=limit)
        return {
            'found_users': found_users,
            'search_term': search_term,
            'limit': limit,
            'format_email': format_email,
            'format_user_label': format_user_label
        }

class AdminUserNode(resource.Resource):
    def __init__(self, request, user_id):
        self.user_id = user_id

    @resource.GET()
    @templating.page('admin/user.html')
    def user(self, request):
        user = user_module.user_from_context(request, self.user_id, check_exists=True)
        if user is None:
            return {'error': utils.tr("This user does not exist.")}
        # Ask the user object to load and cache all of the gamestate data most of which is going to be
        # used on the admin user page.
        user.load_gamestate_row_cache()
        # Load all the invitations using the faster recent invite queries rather than iterating through
        # all of user.invitations and lazy loading everything.
        invite_limit = 300
        recent_invites = admin.recent_invites(request, sender_id=user.user_id, limit=invite_limit)
        return {
            'u': user,
            'invite_limit': invite_limit,
            'user_invitations': recent_invites,
            'format_field': format_field,
            'format_email': format_email,
            'format_utc': format_utc,
            'format_utc_approx': format_utc_approx
        }

class AdminUserMapNode(resource.Resource):
    def __init__(self, request, user_id):
        self.user_id = user_id

    @resource.GET()
    @templating.page('admin/map.html')
    def map(self, request):
        user = user_module.user_from_context(request, self.user_id, check_exists=True)
        if user is None:
            return {'error': utils.tr("This user does not exist.")}
        return {
            'u': user,
            'gamestate': gamestate.gamestate_for_user(user, request),
            'assets_json_s':assets.get_asset_json()
        }

class AdminTargetNode(resource.Resource):
    def __init__(self, request, target_id):
        self.target_id = target_id

    @resource.GET()
    @templating.page('admin/target.html')
    def target(self, request):
        user = user_module.user_from_target_id(request, self.target_id)
        target = user.rovers.find_target_by_id(self.target_id)
        if target is None:
            return {'error': utils.tr("This target does not exist.")}
        if target.is_picture():
            renderer_target_struct = renderer.process_target_struct(user, target)
        else:
            renderer_target_struct = {}
        return {
            'target': target,
            'user': target.user,
            'renderer_target_struct': renderer_target_struct,
            'format_email': format_email
        }

class AdminInvoiceNode(resource.Resource):
    def __init__(self, request, invoice_id):
        self.invoice_id = invoice_id

    @resource.GET()
    @templating.page('admin/invoice.html')
    def invoice(self, request):
        user = user_module.user_from_invoice_id(request, self.invoice_id)
        if user is None:
            return {'error': utils.tr("This user or invoice does not exist.")}
        found = [i for i in user.shop.invoices if i.invoice_id == self.invoice_id]
        if len(found) == 0:
            return {'error': utils.tr("This invoice does not exist.")}
        invoice = found[0]
        return {
            'u': user,
            'invoice': invoice,
            'format_email': format_email,
            'format_utc': format_utc
        }

class AdminGiftsNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/recent_gifts.html')
    def get(self, request):
        limit = 500
        recent_gifts = admin.recent_gifts(request, limit=limit)
        return {
            'recent_gifts': recent_gifts,
            'page_title': "Recent Gifts",
            'limit': limit,
            'format_email': format_email,
            'format_utc': format_utc
        }

    @resource.child()
    def mine(self, request, segments):
        return AdminGiftsMineNode()

    @resource.child()
    def new(self, request, segments):
        return AdminGiftsNewNode()

class AdminGiftsMineNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/recent_gifts.html')
    def get(self, request):
        limit = 500
        user = user_module.user_from_request(request)
        recent_gifts = admin.recent_gifts(request, creator_id=user.user_id, limit=limit)
        return {
            'recent_gifts': recent_gifts,
            'page_title': "My Gifts",
            'limit': limit,
            'format_email': format_email,
            'format_utc': format_utc
        }

class AdminGiftsNewNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/new_gift.html')
    def get(self, request):
        return {
            'all_gift_types': gift_types.ALL
        }

    @resource.POST()
    def post(self, request):
        ok, fields = forms.fetch(request, ['generate_number', 'gift_annotation', 'gift_type', 'gift_campaign_name'], blanks=['gift_campaign_name'])
        if ok:
            generate_number = int(fields['generate_number'])
            if generate_number <= 0:
                return http.bad_request([('content-type', 'text/html')], "Refusing to generate no gifts.")
            gift_annotation = fields['gift_annotation']
            if len(gift_annotation) < 5:
                return http.bad_request([('content-type', 'text/html')], "Please use an annotation longer than 5 characters.")
            gift_type = fields['gift_type']
            if gift_type not in gift_types.ALL:
                return http.bad_request([('content-type', 'text/html')], "Unknown gift_type %s" % gift_type)
            gift_campaign_name = fields['gift_campaign_name'].strip()
            if len(gift_campaign_name) == 0:
                gift_campaign_name = None

            user = user_module.user_from_request(request)
            for _ in range(0, generate_number):
                admin.create_admin_gift_of_type(request, user, gift_type, gift_annotation, campaign_name=gift_campaign_name)
            return http.see_other(urls.admin_gifts_mine())
        else:
            return http.bad_request([('content-type', 'text/html')], "Bad parameters.")

class AdminInvitesNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/recent_invites.html')
    def get(self, request):
        limit = 500
        recent_invites = admin.recent_invites(request, limit=limit)
        return {
            'recent_invites': recent_invites,
            'page_title': "Recent Invitations",
            'limit': limit,
            'format_email': format_email,
            'format_utc': format_utc
        }

    @resource.child()
    def system(self, request, segments):
        return AdminInvitesSystemNode()

    @resource.child()
    def new(self, request, segments):
        return AdminInvitesNewNode()

class AdminInvitesSystemNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/recent_invites.html')
    def get(self, request):
        limit = 500
        admin_inviter = admin.get_admin_inviter_user(request)
        recent_invites = admin.recent_invites(request, sender_id=admin_inviter.user_id, limit=limit)
        return {
            'recent_invites': recent_invites,
            'page_title': "System (Turing) Invitations",
            'limit': limit,
            'format_email': format_email,
            'format_utc': format_utc
        }

class AdminInvitesNewNode(resource.Resource):
    NO_GIFT_TYPE = "No Gift"

    @resource.GET()
    @templating.page('admin/new_invite.html')
    def get(self, request):
        return {
            'all_gift_types': (self.NO_GIFT_TYPE,) + gift_types.ALL,
            'inviter_email': ADMIN_INVITER_EMAIL,
            'inviter_first_name': ADMIN_INVITER_FIRST_NAME,
            'inviter_last_name': ADMIN_INVITER_LAST_NAME
        }

    @resource.POST()
    def post(self, request):
        ok, fields = forms.fetch(request, ['gift_type', 'invitation_message', 'inviter_email', 'recipient_emails_and_names',
                                 'invitation_campaign_name'], blanks=['invitation_campaign_name'])
        if ok:
            user = user_module.user_from_request(request)
            # Future proof allowing an admin to pick who the sender is.
            inviter_email = fields['inviter_email']
            assert inviter_email == ADMIN_INVITER_EMAIL

            gift_type = fields['gift_type']
            if gift_type == self.NO_GIFT_TYPE:
                gift_type = None
                gift_annotation = None
            elif gift_type not in gift_types.ALL:
                return http.bad_request([('content-type', 'text/html')], "Unknown gift_type %s" % gift_type)
            else:
                # Gift annotation is required if a gift type is selected.
                gift_annotation = request.POST['gift_annotation']
                if len(gift_annotation) < 5:
                    return http.bad_request([('content-type', 'text/html')], "Please use an annotation longer than 5 characters.")

            invitation_message = fields['invitation_message']
            if len(invitation_message) < 5:
                return http.bad_request([('content-type', 'text/html')], "Please use an invitation message longer than 5 characters.")
            invitation_campaign_name = fields['invitation_campaign_name'].strip()
            if len(invitation_campaign_name) == 0:
                invitation_campaign_name = None

            # The lists of emails and optional first and last names are in a CSV format
            recipient_emails_and_names = fields['recipient_emails_and_names']
            recipient_emails_and_names_list = recipient_emails_and_names.strip().split('\n')
            invitations_params = []
            # NOTE: This helper function strips whitespace from each CSV value.
            for entry in unicode_csv_reader(recipient_emails_and_names_list, fieldnames=['email','first_name','last_name'], strip=True):
                if len(entry) != 3:
                    return http.bad_request([('content-type', 'text/html')], "Bad invite entry [%s]." % entry)

                if entry['email'] is None:
                    return http.bad_request([('content-type', 'text/html')], "Missing email entry in invite row.")
                if entry['first_name'] is None: entry['first_name'] = ""
                if entry['last_name'] is None: entry['last_name'] = ""
                params, error = invite_module.validate_invite_params(user, entry['email'], entry['first_name'], entry['last_name'],
                                                                     invitation_message,
                                                                     attaching_gift=gift_type is not None,
                                                                     admin_invite=True)
                if not params:
                    return http.bad_request([('content-type', 'text/html')], "Bad invite entry [%s][%s]." % (entry, error))
                invitations_params.append(params)
            if len(invitations_params) == 0:
                return http.bad_request([('content-type', 'text/html')], "Unable to parse any invite entries.")

            # Send all of the invitations now that they are parsed.
            for invite_params in invitations_params:
                admin.send_admin_invite_with_gift_type(request, user, invite_params, gift_type, gift_annotation,
                                                       campaign_name=invitation_campaign_name)

            return http.see_other(urls.admin_invites_system())
        else:
            return http.bad_request([('content-type', 'text/html')], "Bad parameters.")

def format_deferred_run_at(deferred_row):
    """ Show a user friendly version of the deferred row's run_at field, including showing if it is overdue. """
    till_run_at = utils.seconds_between_datetimes(gametime.now(), deferred_row.run_at)
    if till_run_at < 0:
        return "OVERDUE: " + utils.format_time_approx(abs(till_run_at))
    else:
        return utils.format_time_approx(till_run_at)

class AdminUsersNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/users.html')
    def get(self, request):
        limit = 500
        campaign_name = request.GET.get('campaign_name', None)
        if campaign_name is not None:
            recent_users = admin.recent_users(request, limit=limit, campaign_name=campaign_name)
        else:
            recent_users = admin.recent_users(request, limit=limit)
        all_users_count = admin.all_users_count(request)
        return {
            'recent_users': recent_users,
            'all_users_count': all_users_count,
            'show_user_full_name': True,
            'limit': limit,
            'format_email': format_email,
            'format_utc': format_utc,
            'format_field': format_field,
            'format_user_label': format_user_label
        }

class AdminTargetsNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/targets.html')
    def get(self, request):
        limit = 200
        oldest_recent_target_days = OLDEST_RECENT_TARGET_DAYS
        recent_targets = admin.recent_targets(request, limit=limit, oldest_recent_target_days=oldest_recent_target_days)
        return {
            'recent_targets': recent_targets,
            'oldest_recent_target_days': oldest_recent_target_days,
            'limit': limit,
            'format_email': format_email
        }

class AdminTransactionsNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/transactions.html')
    def get(self, request):
        limit = 300
        recent_transactions = admin.recent_transactions(request, limit=limit)
        total_money = sum((t.money for t in recent_transactions), money.from_amount_and_currency(0, 'USD'))
        total_money_display = money.format_money(total_money)
        all_transactions_money = admin.all_transactions_amount(request)
        all_transactions_money_display = money.format_money(all_transactions_money)
        return {
            'recent_transactions': recent_transactions,
            'total_money_display': total_money_display,
            'all_transactions_money_display': all_transactions_money_display,
            'limit': limit,
            'format_utc': format_utc
        }

class AdminDeferredsNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/deferreds.html')
    def get(self, request):
        pending_deferreds = admin.pending_deferreds(request)
        return {
            'pending_deferreds': pending_deferreds,
            'format_deferred_run_at': format_deferred_run_at,
            'format_email': format_email,
            'format_utc': format_utc
        }

class AdminEmailQueueNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/email_queue.html')
    def get(self, request):
        queued_emails = admin.queued_emails(request)
        return {
            'queued_emails': queued_emails,
            'format_utc': format_utc
        }

class AdminStatsNode(resource.Resource):
    DISPLAY_CHARTS = stats.STATS_PAGE_CHARTS
    TEMPLATE = 'admin/stats.html'

    @resource.GET()
    def get(self, request):
        use_debug_data = request.GET.get('debug', None) != None
        template_data = {
            'all_chart_names': self.DISPLAY_CHARTS,
            'url_admin_api_chart_data': urls.admin_api_chart_data(),
            'use_debug_data': use_debug_data
        }
        params = {
            'all_chart_names': self.DISPLAY_CHARTS,
            'template_data_s': xjson.dumps(template_data)
        }
        content = templating.render(request, self.TEMPLATE, params)
        return http.ok([('content-type', 'text/html')], content)

class AdminStatsAttritionNode(AdminStatsNode):
    DISPLAY_CHARTS = stats.ATTRITION_PAGE_CHARTS
    TEMPLATE = 'admin/attrition.html'

class AdminQueryNode(resource.Resource):
    @resource.GET()
    @templating.page('admin/query.html')
    def get(self, request):
        return {}

    @resource.POST()
    @templating.page('admin/query_result.html')
    def run_query(self, request):
        """
        Build a custom SQL query based on the inputs.
        An example query of this form:
            select * from (select users.email, (select count(*) from messages where messages.user_id = users.user_id
            and messages.msg_type="MSG_LASTTHINGa") as msg0, (select count(*) from messages
            where messages.user_id = users.user_id and messages.msg_type="MSG_LASTTHINGb") as msg1 from users) as tbl_1
            where msg0=0 and msg1=1;
        """
        ok, fields = forms.fetch(request, ['msg0_id', 'msg0_sent', 'msg0_locked', 'msg1_id',
            'msg1_sent', 'msg1_locked', 'mis0_id', 'mis0_status', 'mis1_id', 'mis1_status'],
            blanks=['msg0_id', 'msg0_sent', 'msg0_locked', 'msg1_id', 'msg1_sent', 'msg1_locked',
            'mis0_id', 'mis0_status', 'mis1_id', 'mis1_status'])
        if not ok:
            return {'error': 'Bad parameters.'}
        # For each message with a non-empty ID, create a subquery that returns only the count of that message type
        # with the given parameters.
        # e.g., (select count(*) from messages where messages.user_id=users.user_id and messages.msg_type="MSG_OBELISK01a") as msg0
        # We'll simultaneously build a criteria_list that will be used to check the outputs of each subquery.
        # e.g., 'msg0=1 and msg1=1'
        subquery_list = ''
        criteria_list = ''
        for i in range(2):
            msg_type = fields['msg%d_id' % i]
            if msg_type != '':
                if subquery_list != '':
                    subquery_list += ',\n'
                    criteria_list += ' and '
                subquery_list += '(select count(*) from messages where messages.user_id=users.user_id and messages.msg_type="%s"' % (msg_type)
                if fields['msg%d_locked' % i] == 'TRUE':
                    subquery_list += ' and messages.locked=1'
                elif fields['msg%d_locked' % i] == 'FALSE':
                    subquery_list += ' and messages.locked=0'
                if fields['msg%d_sent' % i] == 'TRUE':
                    criteria_list += 'msg%d=1' % (i)
                else:
                    criteria_list += 'msg%d=0' % (i)
                subquery_list += ') as msg%d' % (i)
        # Append subqueries and subquery criteria for missions.
        for i in range(2):
            mis_def = fields['mis%d_id' % i]
            if mis_def != '':
                if subquery_list != '':
                    subquery_list += ',\n'
                    criteria_list += ' and '
                subquery_list += '(select count(*) from missions where missions.user_id=users.user_id and missions.mission_definition="%s"' % (mis_def)
                if fields['mis%d_status' % i] == 'STARTED':
                    subquery_list += ' and missions.done=0'
                    criteria_list += 'mis%d=1' % (i)
                elif fields['mis%d_status' % i] == 'DONE':
                    subquery_list += ' and missions.done=1'
                    criteria_list += 'mis%d=1' % (i)
                else:
                    criteria_list += 'mis%d=0' % (i)
                subquery_list += ') as mis%d' % (i)

        if subquery_list == '':
            return {'error': 'All inputs were left blank.'}
                
        # Put it all together into the final query.
        query = 'select * from (select users.email,\n%s\nfrom users) as tbl_1 where %s' % (subquery_list, criteria_list)
        return { 'sql_query': query }

## The admin REST API.
class APINode(resource.Resource):
    @resource.child()
    def chart_data(self, request, segments):
        return ChartData()

    @resource.child()
    def user_increment_invites_left(self, request, segments):
        return IncrementInvitesLeft()

    @resource.child()
    def user_edit_campaign_name(self, request, segments):
        return EditCampaignName()

    @resource.child()
    def reprocess_target(self, request, segments):
        return ReprocessTarget()

    @resource.child()
    def highlight_add(self, request, segments):
        return HighlightAdd()

    @resource.child()
    def highlight_remove(self, request, segments):
        return HighlightRemove()

class ChartData(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={'chart_name': unicode, 'use_debug_data': bool})
        if body is None: return error
        chart_name     = body['chart_name']
        use_debug_data = body['use_debug_data']
        if chart_name not in stats.ALL_CHARTS:
            return json_bad_request(utils.tr('This is an unknown chart name: ' + chart_name))

        stat_func = getattr(stats, chart_name + '_stats')
        if stat_func is None: raise Exception("No stat function for chart named " + chart_name)
        # Call through to the stats module and load the chart data and options for this chart.
        chart_type, gtable, options = stat_func(request, use_debug_data=use_debug_data)
        return json_success({
            'chart_name': chart_name,
            'chart_type': chart_type,
            'chart_options': options,
            # The Google Chart API has a custom JSON serializer so use that serializer, then convert back
            # to a Python object so that the whole chart response can be serialized together.
            'chart_data': xjson.loads(gtable.ToJSon())
        })

class IncrementInvitesLeft(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={'user_id': unicode})
        if body is None: return error
        user_id = get_uuid(body['user_id'])

        user = user_module.user_from_context(request, user_id, check_exists=True)
        if user is None:
            return json_bad_request(utils.tr('This user does not exist.'))
        user.increment_invites_left()
        return json_success({'invites_left': user.invites_left})

class EditCampaignName(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={'user_id': unicode, 'campaign_name': unicode})
        if body is None: return error
        user_id = get_uuid(body['user_id'])
        campaign_name = body['campaign_name'].strip()
        if len(campaign_name) > 1024:
            return json_bad_request(utils.tr('Campaign name too long.'))

        user = user_module.user_from_context(request, user_id, check_exists=True)
        if user is None:
            return json_bad_request(utils.tr('This user does not exist.'))
        if len(campaign_name) > 0:
            user.add_metadata("MET_CAMPAIGN_NAME", campaign_name)
        else:
            user.clear_metadata("MET_CAMPAIGN_NAME")
        return json_success({'campaign_name': campaign_name})

class ReprocessTarget(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={'target_id': unicode})
        if body is None: return error
        target_id = get_uuid(body['target_id'])

        user = user_module.user_from_target_id(request, target_id)
        if user is None:
            return json_bad_request(utils.tr('This target does not exist.'))
        target = user.rovers.find_target_by_id(target_id)
        # Only picture and not-neutered targets can be marked highlighted.
        if not target.is_picture():
            return json_bad_request(utils.tr('Only picture targets can be reprocessed.'))
        if target.is_neutered():
            return json_bad_request(utils.tr('Neutered targets can not be reprocessed.'))

        target.mark_for_rerender()
        return json_success()

class HighlightAdd(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        return process_highlight_request(request, highlights.add_target_highlight)

class HighlightRemove(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        return process_highlight_request(request, highlights.remove_target_highlight)

def process_highlight_request(request, highlight_action):
    body, error = decode_json(request, required={'target_id': unicode})
    if body is None: return error
    target_id = get_uuid(body['target_id'])

    user = user_module.user_from_target_id(request, target_id)
    if user is None:
        return json_bad_request(utils.tr('This target does not exist.'))
    target = user.rovers.find_target_by_id(target_id)
    # Only picture, non-classified and not-neutered targets can be marked highlighted.
    if not target.is_picture():
        return json_bad_request(utils.tr('Only picture targets can be highlighted.'))
    if target.is_classified():
        return json_bad_request(utils.tr('Classified targets can not be highlighted.'))
    if target.is_neutered():
        return json_bad_request(utils.tr('Neutered targets can not be highlighted.'))

    highlight_action(request, target)
    return json_success()

def format_utc(utc_dt):
    pst = utils.utc_date_in_pst(utc_dt)
    return pst

def format_utc_approx(utc_dt):
    return utils.format_time_approx(utils.seconds_between_datetimes(utc_dt, gametime.now()))

MAX_LENGTH = 30
def format_user_label(user, max_length=MAX_LENGTH):
    str = ''
    if user.auth != 'PASS':
        str += user.auth + ': '
    if user.email:
        str += user.email
    else:
        str += user.first_name + ' ' + user.last_name
    return _truncate_string(str)

def format_email(email, max_length=MAX_LENGTH):
    """
    Keep email fields to a max width in the admin UI
    """
    if email:
        return _truncate_string(email, max_length)
    return "None"

def format_field(text, max_length=MAX_LENGTH):
    """
    Keep description/name fields to a max width in the admin UI
    """
    if text is None: return None
    return _truncate_string(text, max_length)

def _truncate_string(text, max_length=MAX_LENGTH):
    """
    Keep string fields to a max width in the admin UI

    >>> _truncate_string('test@example.com')
    'test@example.com'
    >>> _truncate_string('thirty@charactersistoolong.com')
    'thirty@charactersistoolong.com'
    >>> len(_truncate_string('thirty@charactersistoolong.com'))
    30
    >>> _truncate_string('thirty@charactersistoolongnow.com')
    'thirty@charactersistoolongn...'
    >>> len(_truncate_string('thirty@charactersistoolongnow.com'))
    30
    """
    if len(text) > max_length:
        return text[:max_length - 3] + '...'
    else:
        return text

# Modified from http://docs.python.org/2/library/csv.html
def unicode_csv_reader(unicode_csv_data, strip=False, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.DictReader(_utf_8_encoder(unicode_csv_data),
                                dialect=dialect, **kwargs)
    formatter = _format_val(strip=strip)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield dict((k, formatter(v)) for k,v in row.iteritems())

def _format_val(strip=False):
    def _f(v):
        if v is None: return None
        if not isinstance(v, basestring): return v
        if strip: v = v.strip()
        return unicode(v, 'utf-8')
    return _f

def _utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')
