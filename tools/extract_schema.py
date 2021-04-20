#!/usr/bin/env python
# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os
import re
import subprocess

schema_header = """
-- ****************************************************************************
-- **  This file is generated -- if you want to change the                   **
-- **  schema, add a migration in the migrations directory                   **
-- ****************************************************************************
-- Naming style:
--   * use plural nouns  (e.g. 'users')
--   * compound tables (where you have a second table that just adds columns to
--   the first, such as users_password) should have the plural on the "core"
--   table name
--   * 'noun_id' is always the column name for an id for some noun, even in 
--     its own table
--   * any user-viewable text should be in UTF-8
--
"""

table_header = """
--
-- Table structure for table `%s`
--
"""

table_comments = {
    'users':"""
    -- The users table is simply an indirection table and only really
    -- exists to collate ids from the various methods of authorization.
    -- Because the character set is latin1, don't put any user-visible
    -- data in here; use another table""",
    'users_password':"""
    -- This table contains the usernames and passwords of users that signed up
    -- via the password auth stuff""",
    'rovers':"""
    -- This table contains the rovers""",
    'targets':"""
    -- This table contains the user-specified rover target positions""",
    'missions':"""
    -- This table contains the active missions for a user.  Note that the 
    -- specifics column is for configuring generic missions for the user's 
    -- specific needs, and is just a blob.  The specifics_hash column should 
    -- be populated with the hash of the specifics column as the name implies;
    -- it's there so that the user can't do the exact same mission twice."""
}            


def add_comment(match):
    tablename = match.group(1)
    if tablename in table_comments:
        return (table_header % tablename) + table_comments[tablename].strip() + "\n--\n" + match.group(0)
    return (table_header % tablename) + match.group(0)

def extract(dbname):
    p = subprocess.Popen(
        ["mysqldump", "-u", "root", dbname,
        "--no-data", "--skip-comments", "--skip-quote-names",
        "--skip-set-charset", "--skip-tz-utc"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    o, _ = p.communicate()
    o = schema_header + o
    o = re.sub(r'DROP TABLE IF EXISTS (.*);\n', add_comment, o)
    # get rid of annoying "@saved_cs_client" bullcrap surrounding each table
    o = re.compile(r'^.*?character_set_client.*?\n', re.M).sub('', o)
    # Get rid of AUTO_INCREMENT value setting.
    o = re.compile(r'AUTO_INCREMENT=[0-9]* ', re.M).sub('', o)

    # dump the contents of _yoyo_migrate because anyone using this schema will
    # want to skip the performed migrations
    p = subprocess.Popen(
        ["mysqldump", "-u", "root", dbname, "_yoyo_migration",
        "--no-create-info", "--skip-comments", "--skip-quote-names",
        "--skip-set-charset", "--skip-tz-utc"],  
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT)
    y, _ = p.communicate()
    # Set the creation times for the yoyo table to be NOW() so that the schema line doesn't change
    # and produce a diff unless a new migration has been added.
    y = re.sub(r"(,'\d+-\d+-\d+ \d+:\d+:\d+')", ",NOW()", y)
    o = o + "\n" + y + "\n"
    return o

if __name__ == "__main__":
    o = extract("ce4_dev")

    schema_file = os.path.join(os.path.dirname(__file__), "../lib/db/schema.sql")
    fd = open(schema_file, "w")
    fd.write(o)
    fd.close()
