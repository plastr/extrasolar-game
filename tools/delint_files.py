#!/usr/bin/env python
# Copyright (c) 2013 Lazy 8 Studios, LLC.
# All rights reserved.
# Make sure bad unicode characters haven't snuck in to our data files.

import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

def delint(filename):
    '''
    Walk line-by-line through the given file, looking for unexpected characters.
    Return the number of odd characters that are found.
    '''
    print "Checking file %s" % (filename)
    textfile = open(filename, "r")
    line_index = 0
    total_bad_chars = 0
    for line in textfile:
        line_index += 1
        for character_index, char in enumerate(line):
            c = ord(char)
            if c <= 8 or (c >= 16 and c <= 31) or c >= 127:
                total_bad_chars += 1
                print "  Unicode character \u%04X at line %d, character %d." % (ord(char), line_index, character_index)
    return total_bad_chars

total_bad_chars = 0
total_bad_chars += delint("front/templates/messages/message_types.yaml")
total_bad_chars += delint("front/templates/emails/email_types.yaml")
total_bad_chars += delint("front/data/mission_definitions.json")
total_bad_chars += delint("front/data/product_definitions.json")
total_bad_chars += delint("front/data/capability_definitions.json")
total_bad_chars += delint("front/data/voucher_definitions.json")
total_bad_chars += delint("front/data/asset_definitions.json")
total_bad_chars += delint("front/templates/terms_of_service_snippet.html")
total_bad_chars += delint("front/templates/privacy_policy_snippet.html")
total_bad_chars += delint("front/templates/facebook_login_snippet.html")
total_bad_chars += delint("front/templates/mobile_index.html")
total_bad_chars += delint("../common/data/speciesList.json")
total_bad_chars += delint("../common/data/regions.json")
print "Done. %d questionable characters found." % (total_bad_chars)