"""
Functions used when a Webhook request is received for Netbox interface objects
"""
# ipaddress is needed to parse incoming IP data
import ipaddress

# "g" represents a Flask app global variable which can be used throughout the
#   applicaiton.
# "request" represents the Flask received data
# "Response" is an object that we can use to return an HTTP status code to the
#   NetBox calling webhook.
from flask import g, request, Response

# Import the configured NetBox API object and the RESTCONF session object from
#   config.py
from config import netbox_api, restconf_session

# ... And, import the function to parse an interface name into a type and ID
from common_functions import parse_interface_name


def set_interface_status(netbox_interface_object):
    """
    Given a pynetbox interface object, determine if this interface should be
    shutdown or not. Generate the appropriate RESTCONF payload and send as
    a patch.

    Per the YANG model, enabling an interface should require a DELETE request
    to the interface reference. Disabling (shutdown) an interface requires
    a "shutdown" payload as a list with no data.

    If an interface is already enabled and the DELETE payload is sent, a
    404 will be returned, indicating that there is nothing to delete.

    :param netbox_interface_object: pynetbox interface object reference
    :return: None
    """
    interface_status = netbox_interface_object.enabled

    url = f"{g.baseurl}/shutdown"

    if interface_status:
        url = f"{url}"
        print(f"\tEnabling interface.\n\tTarget URL: {url}")
        response = restconf_session.delete(url=url)
        if response.status_code == 404:
            print(f"\tInterface {netbox_interface_object.name} is already enabled!")
    else:
        payload = {
            "shutdown": [
                None
            ]
        }
        print(f"\tDISabling interface.\n\tTarget URL: {url}\n\tPayload:\n\t{payload}")
        response = restconf_session.put(url=url, json=payload)
    print(f"\tResponse: {response.status_code} ({response.reason})\n")


def update_interface_description(netbox_interface_object):
    """
    Change or remove the interface description, depending on what the desired
    state is from NetBox.

    If an interface description is defined, use an HTTP PUT to create or
    replace the description with what NetBox says it should be.

    If the interface description was removed (set to a null string), send
    an HTTP DELETE command to remove.

    :param netbox_interface_object: pynetbox interface object reference
    :return: None
    """
    url = f"{g.baseurl}/description"

    if interface_description := netbox_interface_object.description:
        payload = {
            "description": interface_description
        }
        print(f"\tSetting interface description to '{interface_description}'\n"
              f"\tURL: {url}\n\tPayload:\n\t{payload}")
        response = restconf_session.put(url=url, json=payload)
    else:
        print(f"\tRemoving interface description.\n\tURL: {url}")
        response = restconf_session.delete(url=url)
    print(f"\tResponse: {response.status_code} ({response.reason})\n")


def update_interface_mtu(netbox_interface_object):
    """
    Set the interface MTU (note: not a TCP MSS or an IP MTU, the actual MTU
    allowed by the interface!).

    If an MTU is defined, replace is using an HTTP PUT. If no interface MTU
    is specified, set it to a default value - generally 1500 unless it's IPv6
    which is not covered here; a 1280-byte payload will be fine with an
    interface MTU of 1500 :-)

    :param netbox_interface_object: pynetbox interface object reference
    :return: None
    """
    url = f"{g.baseurl}/mtu"

    default_mtu = 1500

    if desired_mtu := netbox_interface_object.mtu:
        mtu_payload = desired_mtu
    else:
        mtu_payload = default_mtu

    payload = {
        "mtu": mtu_payload
    }
    print(f"\tSetting interface MTU to '{mtu_payload}'\n\tURL: {url}\n\tPayload:\n\t{payload}")
    response = restconf_session.put(url=url, json=payload)

    print(f"\tResponse: {response.status_code} ({response.reason})\n")


def manage_device_interface():
    """
    Function for the Webhook listener at the interface configuration path.

    When an interface webhook is received from NetBox, parse the incoming
    request and perform the following:
     - Set the interface status (shutdown | no shutdown)
     - Set the interface description
     - Set the interface MTU

    Each task will call a function which performs a RESTCONF operation to
    configure the interface on a device.

    :return: A generic HTTP 204 response - the webhook listener doesn't care
        if this succeeds or not, it's just sending data!
    """

    # Get all the interface data from NetBox.
    interface_data = netbox_api.dcim.interfaces.get(request.json["data"]["id"])

    # Split out the interface type and ID for RESTCONF operations. The YANG
    # model is expecting a list reference to identify the interface for
    # configuration in the format <interface_type>=<interface_id>. Call the
    # common function to parse the interface into separate type/id for use in
    # subsequent tasks.
    interface_type, interface_id = parse_interface_name(interface_data.name)

    # Get the "primary_ip" of the device to configure. This is where RESTCONF
    # requests will be send.
    mgmt_ip = format(ipaddress.IPv4Interface(interface_data.device.primary_ip).ip)

    # The variable "g" is imported by Flask and represents a global variable which
    # is accessible by any during the request. Every function in this module
    # will use the same base URL, which includes the interface identifier.
    g.baseurl = f"https://{mgmt_ip}/restconf/data/Cisco-IOS-XE-native:native/interface/" \
                f"{interface_type}={interface_id}"

    print(f"Configuring interface '{interface_data.name}' on device"
          f" '{interface_data.device.name}'...")

    # If this is the management interface, don't change it! Nothing worse than
    # killing your session because you moved the management interface in the
    # middle of a configuration task :-)
    if interface_data.mgmt_only:
        print("\tManagement interface, no changes will be performed...")
    else:
        # Magic happens here - set the status, description, and MTU.
        set_interface_status(netbox_interface_object=interface_data)
        update_interface_description(netbox_interface_object=interface_data)
        update_interface_mtu(netbox_interface_object=interface_data)

    # Return a generic 204 response to the NetBox webhook
    return Response(status=204)
