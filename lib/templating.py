# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
Templating support library and renderer configuration.
"""
from restish import templating, url
from urlparse import urlparse, parse_qs

from front import TEMPLATE_CONFIG_ARGS
from front.lib import urls

def make_templating(app_conf):
    """
    Create a Templating instance for the application to use when generating
    content from templates.
    """
    renderer = make_renderer(app_conf)
    return Templating(renderer)

class Templating(templating.Templating):
    """
    Application-specific templating implementation.

    Overriding "args" methods makes it trivial to push extra, application-wide
    data to the templates without any assistance from the resource.
    """
    def args(self, request):
        """
        Return a dict of args that should always be present.
        """
        config = request.environ['front.config']
        # Pull in any key/values from the config whose key's started with TEMPLATE_CONFIG_PREFIX.
        # Note that TEMPLATE_CONFIG_PREFIX is stripped from the keys before they are passed to the templates.
        # e.g. template.some_key = some_value -> {"some_key": "some_value"}
        template_args = dict(config[TEMPLATE_CONFIG_ARGS])
        # Add in the default template keys that are available to every template.
        template_args.update({
            'urls': urls,
            'static_url_version': urls.static_url_version,
            'request_url': url.URLAccessor(request),
            'request': request,
            'query_strings': parse_qs(urlparse(request.path_qs).query)
        })
        return template_args

    def render(self, request, template, args=None, encoding=None):
        """
        Render the template and args, optionally encoding to a byte string.
        NOTE: We pass a utf-8 encoding into Mako which encodes the rendered template
        into a str (bytes) object instead of a unicode object which makes the output
        play nicely with Webtest and mod_wsgi (and presumably other strict WSGI servers)
        """
        return self.renderer(template, args, encoding='utf-8')

def make_renderer(app_conf):
    """
    Create and return a restish.templating "renderer".
    """
    import pkg_resources
    import os.path
    from restish.contrib.makorenderer import MakoRenderer
    return MakoRenderer(
            directories=[
                pkg_resources.resource_filename('front', 'templates')
                ],
            module_directory=os.path.join(app_conf['cache_dir'], 'templates'),
            input_encoding='utf-8', output_encoding='utf-8',
            default_filters=['unicode', 'h']
            )

