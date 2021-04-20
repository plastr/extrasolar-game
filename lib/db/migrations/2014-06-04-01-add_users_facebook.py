forward = """
CREATE TABLE users_facebook (
  user_id binary(16) NOT NULL,
  uid bigint(20) NOT NULL,
  PRIMARY KEY (user_id),
  UNIQUE KEY uid (uid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
"""
reverse = """
DROP TABLE users_facebook;
"""
step(forward, reverse)
