# Copyright 2014, Scalyr, Inc.
#
# Note, this can be run in standalone mode by:
# python -m scalyr_agent.run_monitor
# scalyr_agent.builtin_monitors.apache_monitor
import httplib
import urllib2
import socket
import urlparse

from scalyr_agent import ScalyrMonitor, define_config_option, define_log_field, define_metric

httpSourceAddress = "127.0.0.1"

__monitor__ = __name__

define_config_option(__monitor__, 'module',
                     'Always ``scalyr_agent.builtin_monitors.apache_monitor``',
                     convert_to=str, required_option=True)
define_config_option(__monitor__, 'id',
                     'Optional. Included in each log message generated by this monitor, as a field named ``instance``.  '
                     'Allows you to distinguish between values recorded by different monitors. This is especially '
                     'useful if you are running multiple Apache instances on a single server; you can monitor each '
                     'instance with a separate apache_monitor record in the Scalyr Agent configuration.',
                     convert_to=str)
define_config_option(__monitor__, 'status_url',
                     'Optional.  Specifies the URL -- in particular, the port number -- at which the Apache status '
                     'module is served.  The URL should end in ``/?auto`` to indicate the machine-readable version of '
                     'the page should be returned.', default='http://localhost/server-status/?auto')
define_config_option(__monitor__, 'source_address',
                     'Optional (defaults to \'%s\'). The IP address to be used as the source address when fetching '
                     'the status URL.  Many servers require this to be 127.0.0.1 because they only server the status '
                     'page to requests from localhost.' % httpSourceAddress, default=httpSourceAddress)

define_log_field(__monitor__, 'monitor', 'Always ``apache_monitor``.')
define_log_field(__monitor__, 'metric', 'The metric name.  See the metric tables for more information.')
define_log_field(__monitor__, 'value', 'The value of the metric.')
define_log_field(__monitor__, 'instance', 'The ``id`` value from the monitor configuration.')

define_metric(__monitor__, 'apache.connections.active', 'The number of connections that are being handled '
                                                        'asynchronously (not using  workers) currently open on the '
                                                        'server')
define_metric(__monitor__, 'apache.connections.writing', 'The number of connections that are being handled '
                                                         'asynchronously (not using workers) that are currently '
                                                         'writing response data.')
define_metric(__monitor__, 'apache.connections.idle', 'The number of connections that are being handled '
                                                      'asynchronously (not using workers) that are currently '
                                                      'idle / sending keepalives.')
define_metric(__monitor__, 'apache.connections.closing', 'The number of connections that are being handled '
                                                         'asynchronously (not using workers) that are currently '
                                                         'closing.')
define_metric(__monitor__, 'apache.workers.active', 'How many workers are currently active.  Each worker is a process '
                                                    'handling an incoming request.')
define_metric(__monitor__, 'apache.workers.idle', 'How many of the workers are currently idle.  Each worker is a '
                                                  'process that can handle an incoming request.')


# Taken from:
#   http://stackoverflow.com/questions/1150332/source-interface-with-python-and-urllib2
#
# For connecting to local machine, specifying the source IP may be required.  So, using
# this mechanism should allow that.  Since getting status requires "opening up" a
# non-standard/user-facing web page, it is best to be cautious.
#
# Note - the use of a global is ugly, but this form is more compatible than with another
# method mentioned which would not require the global.  (The cleaner version was added
# in Python 2.7.)
class BindableHTTPConnection(httplib.HTTPConnection):

    def connect(self):
        """Connect to the host and port specified in __init__."""
        self.sock = socket.socket()
        self.sock.bind((self.source_ip, 0))
        if isinstance(self.timeout, float):
            self.sock.settimeout(self.timeout)
        self.sock.connect((self.host, self.port))


def BindableHTTPConnectionFactory(source_ip):
    def _get(host, port=None, strict=None, timeout=0):
        bhc = BindableHTTPConnection(
            host,
            port=port,
            strict=strict,
            timeout=timeout)
        bhc.source_ip = source_ip
        return bhc
    return _get


class BindableHTTPHandler(urllib2.HTTPHandler):

    def http_open(self, req):
        return self.do_open(
            BindableHTTPConnectionFactory(httpSourceAddress), req)


class ApacheMonitor(ScalyrMonitor):
    """
# Apache Monitor

This agent monitor plugin records performance and usage data from an Apache server.

@class=bg-warning docInfoPanel: An *agent monitor plugin* is a component of the Scalyr Agent. To use a plugin,
simply add it to the ``monitors`` section of the Scalyr Agent configuration file (``/etc/scalyr/agent.json``).
For more information, see [Agent Plugins](/help/scalyr-agent#plugins).


## Configuring Apache

To use this monitor, you will need to configure your Apache server to enable the status module. For details,
see the [Apache documentation](http://httpd.apache.org/docs/2.2/mod/mod_status.html).

First, verify that the module is enabled in your Apache server. On most Linux installations, you can use the
following command:

    ls /etc/apache2/mods-enabled

If you see ``status.conf`` and ``status.load`` present, the module is enabled. Otherwise, use the following
command (again, for most Linux installations):

    sudo /usr/sbin/a2enmod status

On some platforms, you may need to use different commands to enable the status module. Also, if Apache was
compiled manually, the module may not be available. Consult the documentation for your particular platform.
Here are some links:

- [CentOS 5/RHEL 5](https://www.centos.org/docs/5/html/5.1/Deployment_Guide/s1-apache-addmods.html)
- [Ubuntu 14.04](https://help.ubuntu.com/14.04/serverguide/httpd.html)
- [Windows](http://httpd.apache.org/docs/2.0/platform/windows.html#cust)


Next, you must enable the status module, usually by updating the ``VirtualHost`` configuration section of your
Apache server. On Linux, this is typically found in the ``/etc/apache2/sites-available`` directory, in the file
that corresponds to your site.

Add the following to the ``VirtualHost`` section (between ``<VirtualHost>`` and ``</VirtualHost>``):

    <Location /server-status>
       SetHandler server-status
       Order deny,allow
       Deny from all
       Allow from 127.0.0.1
    </Location>

This specifies that the status page should be served at ``http://<address>/server-status``, and can't be accessed
from other servers.

Once you make the configuration change, you will need to restart Apache.  On most Linux systems, use the following
command:

    sudo service apache2 restart

To verify that the status module is working properly, you can view it manually. Execute this command on the server
(substituting the appropriate port number as needed):

    curl http://localhost:80/server-status

If you have any difficulty enabling the status module, drop us a line at [support@scalyr.com](mailto:support@scalyr.com).


## Sample Configuration

Here is a typical configuration fragment:

    monitors: [
      {
          module: "scalyr_agent.builtin_monitors.apache_monitor",
          status_url: "http://localhost:80/server-status/?auto"
      }
    ]

If your Apache server is running on a nonstandard port, replace ``80`` with the appropriate port number. For additional
options, see Configuration Reference.
    """
    def _initialize(self):
        global httpSourceAddress
        self.__url = self._config.get('status_url',
                                      default='http://localhost/server-status/?auto')
        self.__sourceaddress = self._config.get('source_addresss',
                                                default=httpSourceAddress)
        httpSourceAddress = self.__sourceaddress

    def _parse_data(self, data):
        fields = {
            "Total Accesses:": "total_accesses",
            "Total kBytes:": "total_kbytes_sent",
            "Uptime:": "uptime",
            "ReqPerSec:": "request_per_sec",
            "BytesPerSec:": "bytes_per_sec",
            "BytesPerReq:": "bytes_per_req",
            "BusyWorkers:": "busy_workers",
            "IdleWorkers:": "idle_workers",
            "ConnsTotal:": "connections_total",
            "ConnsAsyncWriting:": "async_connections_writing",
            "ConnsAsyncKeepAlive:": "async_connections_keep_alive",
            "ConnsAsyncClosing:": "async_connections_closing",
        }
        result = {}
        lines = data.splitlines()
        i = 0
        # skip any blank lines
        while len(lines[i]) == 0:
            i = i + 1
        while i < len(lines):
            for key in fields:
                if lines[i].startswith(key):
                    values = lines[i].split()
                    result[fields[key]] = values[1]
            i = i + 1
        return result

    def _get_status(self):
        data = None
        # verify that the URL is valid
        try:
            url = urlparse.urlparse(self.__url)
        except Exception, e:
            self._logger.error(
                "The URL configured for requesting the status page appears to be invalid.  Please verify that the URL is correct in your monitor configuration.  The specified url: %s" %
                self.__url)
            return data
        # attempt to request server status
        try:
            opener = urllib2.build_opener(BindableHTTPHandler)
            handle = opener.open(self.__url)
            data = handle.read()
            if data is not None:
                data = self._parse_data(data)
        except urllib2.HTTPError, err:
            message = "An HTTP error occurred attempting to retrieve the status.  Please consult your server logs to determine the cause.  HTTP error code: ", err.code
            if err.code == 404:
                message = "The URL used to request the status page appears to be incorrect.  Please verify the correct URL and update your apache_monitor configuration."
            elif err.code == 403:
                message = "The server is denying access to the URL specified for requesting the status page.  Please verify that permissions to access the status page are correctly configured in your server configuration and that your apache_monitor configuration reflects the same configuration requirements."
            elif err.code >= 500 or err.code < 600:
                message = "The server failed to fulfill the request to get the status page.  Please consult your server logs to determine the cause.  HTTP error code: ", err.code
            self._logger.error(message)
            data = None
        except urllib2.URLError, err:
            message = "The was an error attempting to reach the server.  Make sure the server is running and properly configured.  The error reported is: ", err
            if err.reason.errno == 111:
                message = "The HTTP server does not appear to running or cannot be reached.  Please check that it is running and is reachable at the address: %s" % url.netloc
            self._logger.error(message)
            data = None
        except Exception, e:
            self._logger.error(
                "An error occurred attempting to request the server status: %s" %
                e)
            data = None
        return data

    """
    # Currently disabled as it requires platform specific functionality.  This will need
    # be reactivated once a cross platform solution is implemented.
    def _get_procinfo(self):
        try:
            data = subprocess.Popen("ps aux | grep apache | grep -v grep | grep -v scalyr | awk '{print $2, $3, $4}'", shell=True, stdout=subprocess.PIPE).stdout.read()
            result = {}
            lines = data.splitlines()
            i = 0
            while i < len(lines):
                if len(lines[i]) != 0:
                    values = lines[i].split()
                    if len(values) == 3:
                        result[values[0]] = {
                            "cpu": values[1],
                            "mem": values[2]
                        }
                i = i + 1
        except Exception, e:
            self._logger.error("Unable to check process status: %s" % e)
            result = None
        return result
    """

    def gather_sample(self):
        data = self._get_status()
        if data is None:
            self._logger.error("No data returned.")
        else:
            samplesToEmit = {
                "busy_workers": 'apache.workers.active',
                "idle_workers": 'apache.workers.idle',
                "connections_total": 'apache.connections.active',
                "async_connections_writing": 'apache.connections.writing',
                "async_connections_keep_alive": 'apache.connections.idle',
                "async_connections_closing": 'apache.connections.closing'
            }

            statsEmitted = 0
            for key in samplesToEmit:
                if key in data:
                    self._logger.emit_value(samplesToEmit[key], int(data[key]))
                    statsEmitted += 1

            if statsEmitted == 0:
                self._logger.error('Status page did not match expected format.  Check to make sure you included '
                                   'the "?auto" option in the status url')
