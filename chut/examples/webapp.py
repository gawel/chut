# -*- coding: utf-8 -*-
from chut import * # noqa
requires('webob', 'waitress')
import webob


def application(environ, start_response):
    req = webob.Request(environ)
    resp = webob.Response()
    resp.text = req.path_info
    return resp(environ, start_response)


@console_script
def webapp(args):
    """
    Usage: %prog [--upgrade-deps]
    """
    serve(application, port=4000)
