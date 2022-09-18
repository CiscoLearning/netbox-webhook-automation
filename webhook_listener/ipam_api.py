"""
Functions used when a Webhook request is received for Netbox IPAM (IP Address
Management) objects
"""
# ipaddress is needed to parse incoming IP data
import ipaddress

# "g" represents a Flask app global variable which can be used throughout the
#   application.
# "request" represents the Flask received data
# "Response" is an object that we can use to return an HTTP status code to the
#   NetBox calling webhook.
from flask import g, request, Response

# Import the configured NetBox API object and the RESTCONF session object from
#   config.py
from config import netbox_api, restconf_session

# ... And, import the function to parse an interface name into a type and ID
from common_functions import parse_interface_name


def configure_interface_ipv4_address(ip_address):
    """
    Configure an interface's primary IPv4 address.

    :param ip_address: IPv4 address in CIDR notation (IP/Prefix)
    :return: Flask HTTP/204 Response object
    """

    # Convert the CIDR notation into an IPv4Interface object, allowing easy
    # parsing of the address components
    ip4_address = format(ipaddress.IPv4Interface(ip_address).ip)
    ip4_netmask = format(ipaddress.IPv4Interface(ip_address).netmask)

    # Build the target URL from the Flask "g" global variable containing the
    # base URL of the device and interface to be modified
    url = f"{g.base_url}/ip/address/primary"

    payload = {
        "primary": {
            "address": ip4_address,
            "mask": ip4_netmask
        }
    }

    print(f"Sending payload:\n\t{payload}\nTo URL:\n\t{url}")
    response = restconf_session.patch(url=url, json=payload)
    print(f"\tResponse: {response.status_code} ({response.reason})")


def configure_interface_ipv6_address(ip_address):
    """
    Because an interface may have multiple IPv6 addresses assigned, add the
    desired IPv6 address to the list of addresses on the target interface.

    :param ip_address: IPv6 address with prefix
    :return: Flask HTTP/204 Response object
    """
    url = f"{g.base_url}/ipv6/address/prefix-list"

    payload = {
        "prefix-list": [
            {
                "prefix": ip_address
            }
        ]
    }
    print(f"Sending payload:\n\t{payload}\nTo URL:\n\t{url}")
    response = restconf_session.patch(url=url, json=payload)
    print(f"\tResponse: {response.status_code} ({response.reason})")


def configure_ip_address(netbox_interface_object, ip_address, address_family):
    """
    Main function to be called if an IP address will be configured on an
    interface. The address family (4/6) will be used to determine which
    function must be called to perform the actual configuration. Almost
    all other relevant details such as the device management IP can be
    gleaned from the NetBox interface object reference.

    :param netbox_interface_object: pynetbox interface object reference
    :param ip_address: string - IPv4 or IPv6 address
    :param address_family: int - 4 or 6 to match the IP family
    :return: None
    """

    # Parse the interface type and ID for RESTCONF URL generation
    interface_type, interface_id = parse_interface_name(netbox_interface_object.name)

    # Grab the management IP from the pynetbox interface object. Note that this
    # is targeting the IPv4 primary IP address, so will be wrapped into an
    # ipaddress.IPv4Interface object for easy extraction of the address
    # component
    mgmt_ip = format(ipaddress.IPv4Interface(netbox_interface_object.device.primary_ip).ip)

    # Generate the base URL for RESTCONF requests against the desired interface
    # Note that the Flask "g" global variable is used here to store the URL.
    g.base_url = f"https://{mgmt_ip}/restconf/data/Cisco-IOS-XE-native:native/interface/" \
                 f"{interface_type}={interface_id}"

    print(f"Assigning address {ip_address} "
          f"to interface '{netbox_interface_object.name}' "
          f"on device '{netbox_interface_object.device.name}'...")

    # Configure the address using the matching AF function
    if address_family == 6:
        configure_interface_ipv6_address(ip_address)
    else:
        configure_interface_ipv4_address(ip_address)


def unconfigure_interface_ipv4_address():
    """
    Delete the primary IPv4 address from an interface. No parameters are needed
    as an HTTP DELETE is performed against the primary address RESTCONF
    endpoint for the device interface

    :return: None
    """
    url = f"{g.base_url}/ip/address/primary"

    response = restconf_session.delete(url=url)
    print(f"\tResponse: {response.status_code} ({response.reason})")


def unconfigure_interface_ipv6_address(ip_address):
    """
    Remove the provided IPv6 address from the list of IPv6 prefixes on an
    interface.

    :param ip_address: string - IPv6 address to remove from the interface
    :return: None
    """
    # Convert the "/" in the IPv6 address representation to a URL-friendly
    # "%2F" to avoid it being interpreted as part of the RESTCONF target
    # URL.
    formatted_address = format(ip_address).replace("/", "%2F")
    url = f"{g.base_url}/ipv6/address/prefix-list={formatted_address}"
    response = restconf_session.delete(url=url)

    print(f"\tResponse: {response.status_code} ({response.reason})")


def unconfigure_ip_address(netbox_interface_object, ip_address, address_family):
    """
    Primary function to remove an address from an interface. Depending on the
    address family, call the appropriate function to unconfigure the
    v4 or v6 address.

    :param netbox_interface_object: pynetbox interface object reference
    :param ip_address: string - IP address in CIDR notation
    :param address_family: int - IP address family (4|6)
    :return: None
    """

    interface_type, interface_id = parse_interface_name(netbox_interface_object.name)
    mgmt_ip = format(ipaddress.IPv4Interface(netbox_interface_object.device.primary_ip).ip)

    g.base_url = f"https://{mgmt_ip}/restconf/data/Cisco-IOS-XE-native:native/interface/" \
                 f"{interface_type}={interface_id}"

    print(f"Removing address {ip_address} "
          f"from interface '{netbox_interface_object.name}' "
          f"on device '{netbox_interface_object.device.name}'...")

    if address_family == 6:
        unconfigure_interface_ipv6_address(ip_address)
    else:
        unconfigure_interface_ipv4_address()


def update_ip_address(netbox_interface_object, snapshot_json, ip_address, address_family):
    """
    If an IPAM webhook is received indicating the address has been updated and
    there is a snapshot key in the webhook payload, it's possible that the
    address was previously configured on a different interface and/or a
    different device.

    Parse the snapshot payload, check if the target interface/device matches
    the "prechange" snapshot. If so, only configure the address on the target
    interface.

    If the presnapshot data differs from the target interface, unconfigure the
    previously-configured interface before configuring the address on the
    target.

    :param netbox_interface_object: pynetbox interface object reference
    :param snapshot_json: Contents of the webhook "snapshot" payload
    :param ip_address: string - IP address in CIDR notation
    :param address_family: int - IP address family (4|6)
    :return: None
    """
    print("Updating IP address...")

    # If the snapshot_json is not None, the snapshot must be compared to the
    # webhook data contained in the pynetbox interface object reference.
    if snapshot_json:
        try:
            old_interface_id = snapshot_json["prechange"]["assigned_object_id"]

            if old_interface_id != netbox_interface_object.id:
                # Old assignment is on a different interface. Unconfigure
                # before configuring the new device.
                old_interface_data = netbox_api.dcim.interfaces.get(old_interface_id)
                if not old_interface_data.mgmt_only:
                    unconfigure_ip_address(netbox_interface_object=old_interface_data,
                                           ip_address=ip_address,
                                           address_family=address_family)
        except AttributeError:
            print("Address not previously assigned")
        except ValueError:
            print("Address not previously assigned")

    # Regardless of the previous address assignment, it is time to configure
    # the address on the target interface...
    configure_ip_address(netbox_interface_object=netbox_interface_object,
                         ip_address=ip_address,
                         address_family=address_family)


def manage_interface_ip_address():
    """
    Function for the Webhook listener at the IPAM configuration path.

    When an IPAM webhook is received, obtain the IP address and address
    family from the payload data. If there is an assigned interface for the
    IP address, determine if it's a new address, an existing address to be
    deleted, or an existing address to be updated and call the appropriate
    function to handle the requested task.

    Note: if the address is assigned to the designated device management
    interface, no action will be performed.

    :return: A generic HTTP 204 response via Flask Response object
    """

    ip_address = request.json["data"]["address"]
    address_family = request.json["data"]["family"]["value"]

    if assigned_interface := request.json["data"].get("assigned_object_id"):
        # There is an interface assigned to this object. Get the interface details
        # and determine what type of request this is (created, updated, deleted)
        # to perform the expected action.

        assigned_interface_details = netbox_api.dcim.interfaces.get(assigned_interface)

        if assigned_interface_details.mgmt_only:
            print("\tManagement interface, no changes will be performed...")
        else:

            if request.json["event"] == "deleted":
                # The IP address has been deleted from NetBox. Unconfigure it from the
                # currently-assigned interface.

                unconfigure_ip_address(netbox_interface_object=assigned_interface_details,
                                       ip_address=ip_address,
                                       address_family=address_family)

            elif request.json["event"] == "created":
                # This is a newly-created IP address. Configure it on the assigned
                # interface.
                configure_ip_address(netbox_interface_object=assigned_interface_details,
                                     ip_address=ip_address,
                                     address_family=address_family)

            elif request.json["event"] == "updated":
                # Details of the IP have changed.  Determine if it was previously
                # assigned to a different device / interface. If so, unconfigure
                # that interface first and configure on the new one.
                update_ip_address(netbox_interface_object=assigned_interface_details,
                                  snapshot_json=request.json.get("snapshots"),
                                  ip_address=ip_address,
                                  address_family=address_family)

    return Response(status=204)
