forward = """
CREATE TABLE edmodo_groups (
  group_id bigint(10) NOT NULL,
  sandbox tinyint(1) NOT NULL DEFAULT '0',
  created datetime NOT NULL,
  PRIMARY KEY (group_id),
  UNIQUE KEY group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
"""
reverse = """
DROP TABLE edmodo_groups;
"""
step(forward, reverse)
