forward = """
CREATE TABLE email_queue (
  queue_id binary(16) NOT NULL,
  email_from varchar(255) NOT NULL,
  email_to varchar(255) NOT NULL,
  email_subject varchar(1024) NOT NULL,
  body_html text NOT NULL,
  created datetime NOT NULL,
  PRIMARY KEY (queue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
"""
reverse = """
DROP TABLE email_queue;
"""
step(forward, reverse)
