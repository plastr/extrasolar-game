# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
WSGI/PasteDeploy application bootstrap module.
"""
from datetime import timedelta

from restish.app import RestishApp
from beaker.middleware import SessionMiddleware
from paste.gzipper import make_gzip_middleware

from front import init_with_config
from front.lib.exceptions import NotifyExceptionMiddleware
from front.lib.db import DatabaseMiddleware
from front.resource import root

def make_app(global_conf, **app_conf):
    """
    PasteDeploy WSGI application factory.

    Called by PasteDeply (or a compatable WSGI application host) to create the
    front WSGI application.
    """
    app = RestishApp(root.Root())
    app = setup_environ(app, global_conf, app_conf)
    return app

def setup_environ(app, global_conf, app_conf):
    """
    WSGI application wrapper factory for extending the WSGI environ with
    application-specific keys.
    """
    # Initialize all modules which require configuration data.
    init_with_config(app_conf)

    # Create any objects that should exist for the lifetime of the application
    # here. Don't forget to actually include them in the environ below!
    from front.lib.templating import make_templating
    templating = make_templating(app_conf)

    def application(environ, start_response):

        # Add additional keys to the environ here.
        environ['restish.templating'] = templating
        environ['front.config'] = app_conf

        return app(environ, start_response)

    # Configure the logging infrastructure.
    import logging.config
    logging.config.fileConfig(global_conf['__file__'])

    cookie_expires = timedelta(seconds=int(app_conf['client.session.cookie_expires']))
    application = NotifyExceptionMiddleware(application, app_conf)
    application = DatabaseMiddleware(application, app_conf)
    application = SessionMiddleware(application, app_conf, cookie_expires=cookie_expires)
    if app_conf['use_gzip_compression'] == "True":
        application = make_gzip_middleware(application, app_conf)
    return application
