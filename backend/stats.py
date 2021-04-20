# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
# This module provides backend services to various admin stats functionality.
import collections
from datetime import timedelta, datetime

from front.external import gviz_api

from front.lib import db, gametime, money
from front.data.rows import get_db_rows_for_query

# List all charts by name so that the admin_node can iterate over them to gather data.
STATS_PAGE_CHARTS     = ['daily_user_creation', 'daily_transaction_creation', 'daily_target_creation', 'daily_invitation_creation', 'hourly_renderer_utilization']
ATTRITION_PAGE_CHARTS = ['recent_message_attrition']
ALL_CHARTS = STATS_PAGE_CHARTS + ATTRITION_PAGE_CHARTS

# Format strings for SQL group queries.
DAY_FORMAT  = '%Y%m%d'
HOUR_FORMAT = '%Y%m%d:%H'

def daily_user_creation_stats(ctx, days_ago=30, use_debug_data=False):
    chart_type = 'ColumnChart'
    table_description = [
        ('day',     "string", "Day"),
        ('created', "number", "Created"),
        ('valid',   "number", "Valid")
    ]
    chart_options = {
        # Title string values interpolated below.
        'title': 'User Creation and Validation (last %d days) (%d total created shown)'
    }
    gtable = gviz_api.DataTable(table_description)

    rows = _db_rows_for_daily_chart(ctx, 'daily_user_creation', days_ago, use_debug_data)
    # Convert the 'rolled up' database results into the final table data.
    current_day = None
    total_users = 0
    data = collections.OrderedDict()
    for r in rows:
        if current_day != r['day']:
            # After processing a given day calculate the conversion rate for that day.
            if current_day is not None:
                conversion = round((float(data[current_day]['valid'])/float(data[current_day]['total'])) * 100, 2)
                data[current_day]['conversion'] = conversion
            # Now point at the new day being processed.
            current_day = r['day']
            if current_day is not None:
                # Convert the day to a compressed format (month/day) for display.
                day = datetime.strptime(current_day, DAY_FORMAT)
                day = '%d/%d' % (day.month, day.day)
                # Initialize all the counting values as its possible for a day to have no total or valid values if
                # no users were created or no valid users on that day.
                # NOTE: It is possible for there to be missing days as well, but those will just not be displayed.
                data[current_day] = {'day':day, 'total':0, 'valid':0, 'not_valid':0}
            else:
                total_users = r['count']
                continue

        if   r['valid'] is None: data[current_day]['total']     = r['count']
        elif r['valid'] == 0:    data[current_day]['not_valid'] = r['count']
        elif r['valid'] == 1:    data[current_day]['valid']     = r['count']
        else: raise Exception("Unexpected valid value %s" % r['valid'])

    # Sort order is preserved by using an OrderedDict. sorted(data.keys()) would also work as the
    # string data format for the day values sort in the correct order.
    for k, v in data.iteritems():
        gtable.AppendData([(v['day'], int(v['total']), (int(v['valid']), '%d (%0.2f%%)' % (v['valid'], v['conversion'])))])
    # Merge in the title values.
    chart_options['title'] = chart_options['title'] % (days_ago, total_users)
    return chart_type, gtable, chart_options

def daily_transaction_creation_stats(ctx, days_ago=30, use_debug_data=False):
    chart_type = 'ColumnChart'
    table_description = [
        ('day',     "string", "Day"),
        ('amount',  "number", "Amount", { 'color': "#e5e4e2" }),
        ('count',   "number", "Count")
    ]
    chart_options = {
        # Title string values interpolated below.
        'title' : 'Transaction Creation (last %d days) (%s total shown)',
        'vAxis' : { 'format': '$#,###' },
        # Green for money, blue for counts
        'series': { 0: { 'color': '#20991d' }, 1: { 'color': '#4061cb' } }
    }
    gtable = gviz_api.DataTable(table_description)

    rows = _db_rows_for_daily_chart(ctx, 'daily_transaction_creation', days_ago, use_debug_data)
    # Convert the database results into the final table data.
    data = collections.OrderedDict()
    for r in rows:
        current_day = r['day']
        data[current_day] = {}
        # Convert the day to a compressed format (month/day) for display.
        day = datetime.strptime(current_day, DAY_FORMAT)
        day = '%d/%d' % (day.month, day.day)
        data[current_day]['day']    = day
        data[current_day]['amount'] = r['sum']
        data[current_day]['count']  = r['count']

    # Sort order is preserved by using an OrderedDict. sorted(data.keys()) would also work as the
    # string data format for the day values sort in the correct order.
    total_amount = money.from_amount_and_currency(0, 'USD')
    for k, v in data.iteritems():
        amount_int = int(v['amount'])
        amount_money = money.from_amount_and_currency(amount_int, 'USD')
        gtable.AppendData([(v['day'], (amount_int / 100, money.format_money(amount_money)), int(v['count']))])
        total_amount += amount_money
    # Merge in the title values.
    chart_options['title'] = chart_options['title'] % (days_ago, money.format_money(total_amount))
    return chart_type, gtable, chart_options

def daily_target_creation_stats(ctx, days_ago=30, use_debug_data=False):
    chart_type = 'LineChart'
    table_description = [
        ('day',           "string", "Day"),
        ('target_count',  "number", "Targets"),
        ('user_count',    "number", "Users")
    ]
    chart_options = {
        # Title string values interpolated below.
        'title': 'Target Creation (last %d days) (%s total targets shown)'
    }
    gtable = gviz_api.DataTable(table_description)

    rows = _db_rows_for_daily_chart(ctx, 'daily_target_creation', days_ago, use_debug_data)
    # Convert the database results into the final table data.
    data = collections.OrderedDict()
    for r in rows:
        current_day = r['day']
        data[current_day] = {}
        # Convert the day to a compressed format (month/day) for display.
        day = datetime.strptime(current_day, DAY_FORMAT)
        day = '%d/%d' % (day.month, day.day)
        data[current_day]['day']          = day
        data[current_day]['target_count'] = r['target_count']
        data[current_day]['user_count']   = r['user_count']
        data[current_day]['targets_each'] = float(r['target_count']) / float(r['user_count'])

    # Sort order is preserved by using an OrderedDict. sorted(data.keys()) would also work as the
    # string data format for the day values sort in the correct order.
    total_targets = 0
    for k, v in data.iteritems():
        gtable.AppendData([(v['day'], int(v['target_count']), (int(v['user_count']), '%d (%0.2f)' % (v['user_count'], v['targets_each'])))])
        total_targets += int(v['target_count'])
    # Merge in the title values.
    chart_options['title'] = chart_options['title'] % (days_ago, total_targets)
    return chart_type, gtable, chart_options

# NOTE: This function is a copy and pasted version of daily_user_creation_stats function with some field
# names changed. If a third similar chart is required, consider factoring out shared code.
def daily_invitation_creation_stats(ctx, days_ago=30, use_debug_data=False):
    chart_type = 'ColumnChart'
    table_description = [
        ('day',      "string", "Day"),
        ('created',  "number", "Created"),
        ('accepted', "number", "Accepted")
    ]
    chart_options = {
        # Title string values interpolated below.
        'title': 'Invitation Creation and Acceptance (last %d days) (%d total created shown)'
    }
    gtable = gviz_api.DataTable(table_description)

    rows = _db_rows_for_daily_chart(ctx, 'daily_invitation_creation', days_ago, use_debug_data)
    # Convert the 'rolled up' database results into the final table data.
    current_day = None
    total_invites = 0
    data = collections.OrderedDict()
    for r in rows:
        if current_day != r['day']:
            # After processing a given day calculate the conversion rate for that day.
            if current_day is not None:
                conversion = round((float(data[current_day]['accepted'])/float(data[current_day]['total'])) * 100, 2)
                data[current_day]['conversion'] = conversion
            # Now point at the new day being processed.
            current_day = r['day']
            if current_day is not None:
                # Convert the day to a compressed format (month/day) for display.
                day = datetime.strptime(current_day, DAY_FORMAT)
                day = '%d/%d' % (day.month, day.day)
                # Initialize all the counting values as its possible for a day to have no total or accepted values if
                # no invitations were created or no accepted invitations on that day.
                # NOTE: It is possible for there to be missing days as well, but those will just not be displayed.
                data[current_day] = {'day':day, 'total':0, 'accepted':0, 'not_accepted':0}
            else:
                total_invites = r['count']
                continue

        if   r['accepted'] is None: data[current_day]['total']        = r['count']
        elif r['accepted'] == 0:    data[current_day]['not_accepted'] = r['count']
        elif r['accepted'] == 1:    data[current_day]['accepted']     = r['count']
        else: raise Exception("Unexpected accepted value %s" % r['accepted'])

    # Sort order is preserved by using an OrderedDict. sorted(data.keys()) would also work as the
    # string data format for the day values sort in the correct order.
    for k, v in data.iteritems():
        gtable.AppendData([(v['day'], int(v['total']), (int(v['accepted']), '%d (%0.2f%%)' % (v['accepted'], v['conversion'])))])
    # Merge in the title values.
    chart_options['title'] = chart_options['title'] % (days_ago, total_invites)
    return chart_type, gtable, chart_options

def hourly_renderer_utilization_stats(ctx, hours_ago=48, use_debug_data=False):
    chart_type = 'LineChart'
    # A slot for each instances utilization will be added once all known instances are found.
    table_description = [
        ('hour', "string", "Hour")
    ]
    chart_options = {
        # Title string values interpolated below.
        'title': 'Renderer Utilization (last %d hours) (%s total targets shown)',
        'vAxis' : { 'format': '#,###%' },
        'legend': { 'position': 'bottom' }
    }

    rows = _db_rows_for_hourly_chart(ctx, 'hourly_renderer_utilization', hours_ago, use_debug_data)
    # Find all instance names in order of when they first appear and add them to the table description schema.
    instance_names = []
    for r in rows:
        if r['instance_name'] not in instance_names:
            instance_names.append(r['instance_name'])
            table_description.append(('instance_name_'+str(len(instance_names)), "number", r['instance_name']))
    gtable = gviz_api.DataTable(table_description)

    # Convert the database results into the final table data.
    current_hour = None
    # Used to compute how many hours ago each column of data was.
    hours_before_now = 0
    data = collections.OrderedDict()
    for r in rows:
        if current_hour != r['hour']:
            current_hour = r['hour']
            # Initialize the instance tracking dict. Use an OrderedDict initialized with all known instance names
            # as it is not guaranteed that every instance will have data for every hour (adding or removing an
            # instance can happen in production).
            instances = collections.OrderedDict([(i_name, (0.0, "0%")) for i_name in instance_names])
            data[current_hour] = {'hour':hours_ago - hours_before_now, 'instances':instances, 'target_count':0}
            hours_before_now += 1
        # Compute and store the utilization % per instance. The sum_total_time is the total number of milliseconds
        # that renderer spent doing work in the hour window, so divide that by the number of milliseconds in an hour
        # to find utilization percentage and then format that for display as a string with a % sign.
        utilization = r['sum_total_time']/3600000
        data[current_hour]['instances'][r['instance_name']] = (utilization, '%0.2f%% (%d)' % (utilization * 100, r['count']))
        data[current_hour]['target_count'] += r['count']

    # Sort order is preserved by using an OrderedDict. sorted(data.keys()) would also work as the
    # string data format for the day values sort in the correct order.
    total_targets = 0
    for k, v in data.iteritems():
        gtable.AppendData([([(v['hour'], "%d hours ago" % v['hour'])] + v['instances'].values())])
        total_targets += int(v['target_count'])
    # Merge in the title values.
    chart_options['title'] = chart_options['title'] % (hours_ago, total_targets)
    return chart_type, gtable, chart_options

# Exclude these msg_type prefixes from the chart, usually because when they occur in the story is too
# random to be useful.
MSG_TYPE_EXCLUDE_PREFIXES = [
    'MSG_SCI',
    'MSG_ACH',
    'MSG_DELIVER',
    'MSG_NO_FORWARD',
    'MSG_FIND'
]
MESSAGE_ATTRITION_INACTIVE_DAYS = 7
def recent_message_attrition_stats(ctx, days_ago=30 + MESSAGE_ATTRITION_INACTIVE_DAYS, use_debug_data=False):
    chart_type = 'ComboChart'
    table_description = [
        ('msg_type',  "string", "msg_type"),
        ('count',     "number", "User Count"),
        ('attrition', "number", "Dropoff From Previous Message")
    ]
    chart_options = {
        # Title string values interpolated below.
        'title': 'Last Message Received By Users (created in last %d days and inactive more than %d days)\nExcluding prefixes: %s',
        # NOTE: 'chartArea' is set on client as it varies based on orientation
        'orientation': 'horizontal',
        'hAxis': {
            'minTextSpacing': 1,
            'maxAlternation': 1,
            'slantedTextAngle': 90,
            'textStyle': { 'fontSize': "10" },
        },
        'fontSize': "12",
        'vAxes':[
            { 'fontSize': 10 }, # Left axis (msg_type)
            # Note that this label and tick marks will not draw in vertical orientation, annoying.
            { 'fontSize': 10, 'format': '#,###%' } # Right axis (attrition)
        ],
        'series': {
        0: {
            'targetAxisIndex': 0,
            'lineWidth': 3,
            'pointSize': 6
        },
        1: {
            'targetAxisIndex': 1,
            'type': "bars",
            'color': 'lightgrey'
        }}
    }
    gtable = gviz_api.DataTable(table_description)

    # NOTE: Reuse the convenient 'start' computing and other useful plumbing from _db_rows_for_daily_chart
    # but the 'end' and 'date_format' parameters are ignored by this query.
    inactive_start = gametime.now() - timedelta(days=MESSAGE_ATTRITION_INACTIVE_DAYS)
    rows = _db_rows_for_daily_chart(ctx, 'recent_message_attrition', days_ago, use_debug_data, inactive_start=inactive_start)

    last_count = 0
    data = []
    for r in rows:
        # Exclude any msg_types which match any excluded prefix.
        if len([p for p in MSG_TYPE_EXCLUDE_PREFIXES if r['msg_type'].startswith(p)]) > 0:
            continue

        msg_type = r['msg_type'].replace('MSG_', '')
        count = r['count']
        attrition = 0.0
        if last_count > count:
            attrition = 1.0 - float(count) / float(last_count)
        data.append({'msg_type':msg_type, 'count':count, 'attrition':attrition})
        last_count = count

    for v in data:
        gtable.AppendData([(v['msg_type'], int(v['count']), (float(v['attrition']), '%0.2f%%' % (v['attrition'] * 100)))])
    # Merge in the title values.
    chart_options['title'] = chart_options['title'] % (days_ago, MESSAGE_ATTRITION_INACTIVE_DAYS, ", ".join(MSG_TYPE_EXCLUDE_PREFIXES))
    return chart_type, gtable, chart_options

def _db_rows_for_daily_chart(ctx, chart_name, days_ago, use_debug_data, **kwargs):
    today = gametime.now().date()
    # Filter the data back days_ago days, where day >= start (includes start day) and day < end (excludes end day)
    # Exclude 'today' by adding + 1 to days_ago as data is still being added to this day 'bucket'
    # and it will be confusing to the admins if this data constantly changes.
    end   = today
    start = end - timedelta(days=days_ago + 1)
    if use_debug_data:
        return get_db_rows_for_query('select_%s_stats' % chart_name)
    else:
        with db.conn(ctx) as ctx:
            return db.rows(ctx, 'stats/select_%s_stats' % chart_name, start=start, end=end, date_format=DAY_FORMAT, **kwargs)

def _db_rows_for_hourly_chart(ctx, chart_name, hours_ago, use_debug_data):
    # Strip off the current minutes and seconds so that the upper bound is < the start of the current hour.
    now   = gametime.now()
    end   = now.replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours_ago)
    assert end - start == timedelta(hours=48)
    if use_debug_data:
        return get_db_rows_for_query('select_%s_stats' % chart_name)
    else:
        with db.conn(ctx) as ctx:
            return db.rows(ctx, 'stats/select_%s_stats' % chart_name, start=start, end=end, date_format=HOUR_FORMAT)
