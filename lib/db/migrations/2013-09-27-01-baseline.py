forward = """
CREATE TABLE achievements (
  user_id binary(16) NOT NULL,
  achievement_key char(32) NOT NULL,
  achieved_at int(10) unsigned NOT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (user_id,achievement_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE capabilities (
  user_id binary(16) NOT NULL,
  capability_key char(32) NOT NULL,
  uses int(10) unsigned NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  PRIMARY KEY (user_id,capability_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE chips (
  user_id binary(16) NOT NULL,
  transient tinyint(1) NOT NULL DEFAULT '1',
  content blob NOT NULL,
  seq bigint(20) NOT NULL AUTO_INCREMENT,
  `time` bigint(20) unsigned NOT NULL,
  PRIMARY KEY (seq),
  KEY user_id_time (user_id,`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE deferred (
  deferred_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  deferred_type char(32) NOT NULL,
  subtype char(32) NOT NULL,
  run_at datetime NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  payload varchar(1024) DEFAULT NULL,
  PRIMARY KEY (deferred_id),
  KEY user_id_deferred_type (user_id,deferred_type,subtype)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE gifts (
  gift_id binary(16) NOT NULL,
  gift_type char(32) NOT NULL,
  creator_id binary(16) NOT NULL,
  redeemer_id binary(16) DEFAULT NULL,
  annotation varchar(127) NOT NULL,
  created datetime NOT NULL,
  redeemed_at datetime DEFAULT NULL,
  PRIMARY KEY (creator_id,gift_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE highlighted_targets (
  target_id binary(16) NOT NULL,
  available_at datetime NOT NULL,
  highlighted_at datetime NOT NULL,
  PRIMARY KEY (target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE invitation_gifts (
  invite_id binary(16) NOT NULL,
  gift_id binary(16) NOT NULL,
  PRIMARY KEY (invite_id,gift_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE invitations (
  invite_id binary(16) NOT NULL,
  sender_id binary(16) NOT NULL,
  recipient_id binary(16) DEFAULT NULL,
  recipient_email varchar(255) NOT NULL,
  recipient_first_name varchar(127) NOT NULL,
  recipient_last_name varchar(127) NOT NULL,
  sent_at datetime NOT NULL,
  accepted_at datetime DEFAULT NULL,
  PRIMARY KEY (sender_id,invite_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE invoices (
  invoice_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  currency char(8) DEFAULT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_current_email varchar(255) NOT NULL,
  PRIMARY KEY (user_id,invoice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE landers (
  lander_id binary(16) NOT NULL,
  lat double NOT NULL,
  lng double NOT NULL,
  PRIMARY KEY (lander_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE messages (
  message_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  msg_type char(32) NOT NULL,
  sent_at int(10) unsigned NOT NULL,
  read_at int(10) unsigned DEFAULT NULL,
  locked tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (message_id,user_id),
  UNIQUE KEY user_id_msg_type (user_id,msg_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE missions (
  user_id binary(16) NOT NULL,
  mission_definition char(32) NOT NULL,
  specifics_hash char(32) NOT NULL DEFAULT '',
  specifics varchar(1024) NOT NULL,
  done tinyint(1) NOT NULL DEFAULT '0',
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  started_at int(10) unsigned NOT NULL,
  parent_hash char(32) NOT NULL DEFAULT '',
  done_at int(10) unsigned DEFAULT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (user_id,mission_definition,specifics_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE purchased_products (
  product_id binary(16) NOT NULL,
  invoice_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  product_key char(32) NOT NULL,
  price int(10) unsigned NOT NULL,
  currency char(8) NOT NULL,
  purchased_at int(10) unsigned NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id,product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE rovers (
  rover_id binary(16) NOT NULL,
  user_id binary(16) DEFAULT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  active tinyint(4) NOT NULL DEFAULT '1',
  lander_id binary(16) NOT NULL,
  PRIMARY KEY (rover_id),
  KEY user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE species (
  user_id binary(16) NOT NULL,
  species_id int(10) unsigned NOT NULL DEFAULT '0',
  detected_at int(10) unsigned NOT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (user_id,species_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE target_image_rects (
  xmin double NOT NULL,
  ymin double NOT NULL,
  xmax double NOT NULL,
  ymax double NOT NULL,
  density double DEFAULT NULL,
  target_id binary(16) NOT NULL,
  species_id int(10) unsigned DEFAULT NULL,
  seq int(11) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  subspecies_id int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (target_id,seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE target_images (
  `type` varchar(20) NOT NULL DEFAULT '',
  url varchar(256) NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  target_id binary(16) NOT NULL,
  PRIMARY KEY (target_id,`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE target_metadata (
  target_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (target_id,`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE target_sounds (
  sound_key char(32) NOT NULL,
  target_id binary(16) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (target_id,sound_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE targets (
  rover_id binary(16) NOT NULL,
  seq int(10) unsigned NOT NULL DEFAULT '0',
  lat double NOT NULL,
  lng double NOT NULL,
  arrival_time int(10) unsigned NOT NULL,
  yaw double NOT NULL,
  pitch double NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  processed tinyint(1) NOT NULL DEFAULT '0',
  picture tinyint(1) NOT NULL DEFAULT '0',
  target_id binary(16) NOT NULL,
  start_time int(10) unsigned NOT NULL,
  locked_at datetime DEFAULT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  classified tinyint(1) NOT NULL DEFAULT '0',
  highlighted tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (rover_id,arrival_time,seq),
  UNIQUE KEY target_id (target_id),
  KEY lat (lat),
  KEY lng (lng),
  KEY time_picture (arrival_time,picture)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE transaction_gateway_data (
  transaction_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  PRIMARY KEY (transaction_id,`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE transactions (
  transaction_id binary(16) NOT NULL,
  invoice_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  transaction_type char(32) NOT NULL,
  amount int(10) unsigned NOT NULL,
  currency char(8) NOT NULL,
  gateway_type char(32) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (invoice_id,transaction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE user_map_tiles (
  user_id binary(16) NOT NULL,
  zoom int(3) NOT NULL,
  x bigint(20) NOT NULL,
  y bigint(20) NOT NULL,
  arrival_time int(10) unsigned NOT NULL,
  expiry_time datetime DEFAULT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  PRIMARY KEY (user_id,zoom,x,y,arrival_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE users (
  user_id binary(16) NOT NULL,
  authentication char(5) NOT NULL,
  dev tinyint(4) NOT NULL DEFAULT '0',
  email varchar(255) NOT NULL,
  first_name varchar(127) NOT NULL,
  last_name varchar(127) NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  valid tinyint(4) NOT NULL DEFAULT '0',
  epoch datetime NOT NULL,
  last_accessed datetime NOT NULL,
  viewed_alerts_at int(10) unsigned DEFAULT NULL,
  inviter_id binary(16) DEFAULT NULL,
  invites_left int(10) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (user_id),
  UNIQUE KEY email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE users_metadata (
  user_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id,`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE users_notification (
  user_id binary(16) NOT NULL,
  wants_notification tinyint(1) NOT NULL DEFAULT '0',
  digest_window_start datetime DEFAULT NULL,
  digest_last_sent datetime DEFAULT NULL,
  frequency char(32) NOT NULL,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE users_password (
  user_id binary(16) NOT NULL,
  `password` varchar(128) NOT NULL,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE users_progress (
  user_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  achieved_at int(10) unsigned NOT NULL,
  PRIMARY KEY (user_id,`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE users_shop (
  user_id binary(16) NOT NULL,
  stripe_customer_id char(32) DEFAULT NULL,
  stripe_customer_data varchar(1024) DEFAULT NULL,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE vouchers (
  user_id binary(16) NOT NULL,
  voucher_key char(32) NOT NULL,
  delivered_at int(10) unsigned NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id,voucher_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;"""

def no_backward(conn):
    raise Exception("Cannot rollback the baseline migration.")

def multi_exec(conn, stmts):
    # you can't run a semicolon-delimited series of statements normally;
    # this function gets it done
    curs = conn.cursor()
    for stmt in stmts.split(';'):
        if stmt:
            curs.execute(stmt.rstrip(';'))
    
step(lambda conn: multi_exec(conn, forward),
     no_backward,
     # allow yoyo to think it's succeeded even if it fails, so that we can "apply" it
     # to already-existing databases
     ignore_errors='apply')