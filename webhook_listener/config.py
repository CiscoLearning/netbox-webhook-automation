"""
Docstring.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3 import disable_warnings, Retry
import pynetbox
from credentials import (NETBOX_URL,
                         NETBOX_TOKEN,
                         DEVICE_USERNAME,
                         DEVICE_PASSWORD)

# Boolean - perform TLS validation when consuming remote APIs? For production
# use, this should be set to True!
TLS_VERIFY = False

# Configure a retry/backoff strategy for RESTCONF calls. Sometimes the NETCONF/
# RESTCONF datastore is locked while configuration synchronization is being
# performed, which will result in an HTTP 409 status code being returned.
# Instead of timing out and failing, the Retry configuration will continue
# attempting the API request for (total) retries with an incremental backoff
# specified by (backoff_factor).
# The (status_forcelist) is a list containing status codes which should be
# retried, and (method_whitelist) instructs Python to perform retries for
# the specified HTTP verbs.
RESTCONF_RETRY_CONFIG = Retry(
    total=8,
    status_forcelist=[409],
    method_whitelist=["PATCH", "POST", "PUT"],
    backoff_factor=1
)

# When creating an HTTP session, these are the headers that will be included
# for every request. Code duplication is reduced as these headers will be
# attached to a requests.Session() object, meaning that scripts do not need
# to define headers for every request.
RESTCONF_HEADERS = {
    "Content-Type": "application/yang-data+json",
    "Accept": "application/yang-data+json"
}


def conditionally_disable_tls_warnings():
    """
    If TLS chain validation is disabled, prevent the urllib3 package from
    displaying "Unsafe operation" type of messages.

    The calling script (__main__) should invoke this function only one time.

    :return: None
    """
    if not TLS_VERIFY:
        disable_warnings()


def create_restconf_session():
    """
    Initialize a Python requests.Session() object with "extra" options such
    as HTTP retry / incremental backoff. The Session() object also will
    set default values for authentication and header values such as
    Content-Type or Accept.

    Once the session has been created, perform any normal urllib3/requests
    verbs against the session to take advantage of the configured settings.

    :return: requests.Session() object
    """
    http_adapter = HTTPAdapter(max_retries=RESTCONF_RETRY_CONFIG)
    http_session = requests.Session()
    http_session.mount("https://", http_adapter)
    http_session.mount("http://", http_adapter)
    http_session.auth = (DEVICE_USERNAME, DEVICE_PASSWORD)
    http_session.headers = RESTCONF_HEADERS
    http_session.verify = TLS_VERIFY

    return http_session


def create_netbox_api():
    """
    Initialize a pynetbox API object and attach an HTTP session object to
    specify whether TLS validation should be performed.

    :return: pynetbox API object
    """
    # Initialize the pynetbox API object
    netbox = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)

    # pynetbox does not support TLS validation enable/disable functionality
    # but does accept an optional Session object.  Use this to specify
    # the TLS validation option and attach the Session object to the
    # pynetbox instance.
    api_session = requests.Session()
    api_session.verify = TLS_VERIFY
    netbox.http_session = api_session

    return netbox

# restconf_session and/or netbox_api should be imported by scripts requiring
# access to RESTCONF sessions or the Netbox API.
restconf_session = create_restconf_session()
netbox_api = create_netbox_api()
