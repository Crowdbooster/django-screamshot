import os
import logging
import subprocess
from tempfile import NamedTemporaryFile
import json
from urlparse import urljoin

from django.core.exceptions import ImproperlyConfigured

from . import app_settings


logger = logging.getLogger(__name__)


class CaptureError(Exception):
    pass


def casperjs_command():
    """
    Look up for ``casperjs`` in shell PATH and builds the whole capture
    command.
    """
    cmd = None
    sys_path = os.getenv('PATH', '').split(':')
    for binpath in sys_path:
        cmd = os.path.join(binpath, 'casperjs')
        if os.path.exists(cmd):
            break
    cmd = [cmd]
    try:
        proc = subprocess.Popen(cmd + ['--version'], stdout=subprocess.PIPE)
        proc.communicate()
        status = proc.returncode
        assert status == 0
    except OSError:
        raise ImproperlyConfigured("CasperJS binary cannot be found in PATH (%s)" % sys_path)
    except AssertionError:
        raise ImproperlyConfigured("CasperJS returned status code %s" % status)

    # Add extra CLI arguments
    cmd += app_settings['CLI_ARGS']

    # Concatenate with capture script
    app_path = os.path.dirname(__file__)
    capture = os.path.join(app_path, 'scripts', 'capture.js')
    assert os.path.exists(capture), 'Cannot find %s' % capture
    return cmd + [capture]


CASPERJS_CMD = casperjs_command()


def casperjs_capture(stream, url, method='get', width=None, height=None, selector=None, data=None, waitfor=None):
    """
    Captures web pages using ``casperjs``
    """
    output = None
    try:
        with NamedTemporaryFile('rwb', suffix='.png', delete=False) as f:
            output = f.name
            cmd = CASPERJS_CMD + [url, output]
            # Extra command-line options
            cmd += ['--method=%s' % method]
            if width:
                cmd += ['--width=%s' % width]
            if height:
                cmd += ['--height=%s' % height]
            if selector:
                cmd += ['--selector=%s' % selector]
            if data:
                cmd += ['--data="%s"' % json.dumps(data)]
            if waitfor:
                cmd += ['--waitfor=%s' % waitfor]
            logger.debug(cmd)
            # Run CasperJS process
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            stdout = proc.communicate()[0]
            if not os.path.exists(output):
                stdout = map(lambda x: x.split(':', 1)[1]
                             if ':' in x else x, stdout.splitlines())
                raise CaptureError(';'.join(stdout))
            # From file to stream
            with open(output) as out:
                stream.write(out.read())
    finally:
        if output:
            os.unlink(output)


def build_absolute_uri(request, url):
    """
    Allow to override printing url, not necessarily on the same
    server instance.
    """
    if app_settings.get('CAPTURE_ROOT_URL'):
        return urljoin(app_settings.get('CAPTURE_ROOT_URL'), url)
    return request.build_absolute_uri(url)
