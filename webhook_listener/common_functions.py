"""
Common (generic) functions that can be imported by any script/module.
"""
import re


def parse_interface_name(interface_name):
    """
    Given an interface name, split the string into the type of interface
    and the interface ID.  Use for generating RESTCONF URLs requiring an
    interface specifier.

    :param interface_name: String - name of the interface to parse
    :return: Tuple of (interface type, interface ID)
    """
    interface_pattern = r"^(\D+)(\d+.*)$"
    interface_regex = re.compile(interface_pattern)

    interface_type, interface_id = interface_regex.match(str(interface_name)).groups()

    return interface_type, interface_id
