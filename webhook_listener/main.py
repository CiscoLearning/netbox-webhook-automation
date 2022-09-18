"""
Main webhook listener entrypoint. Initialize the Flask app which will listen
for incoming Netbox webhooks and add URL rules to process webhook data sent
to specific URL endpoints
"""
# Import Flask to act as the main webhook listener
from flask import Flask

# Include the conditional "urllib3" TLS warning disable function
from config import conditionally_disable_tls_warnings

# There will be two API endpoints created for interfaces and IPAM. Import
# the needed functions from separate Python files which will handle request
# data:
from interface_api import manage_device_interface
from ipam_api import manage_interface_ip_address

# Disable "insecure HTTPS" messages if no validation is to be performed
conditionally_disable_tls_warnings()

# Create the initial Flask app
app = Flask(__name__)

# URLs to be included. "add_url_rule" is a Flask method to specify the target
# API endpoint, the allowed methods, and which function will process incoming
# data.
app.add_url_rule("/api/update-interface",
                 methods=["POST"],
                 view_func=manage_device_interface)

app.add_url_rule("/api/update-address",
                 methods=["POST"],
                 view_func=manage_interface_ip_address)

if __name__ == "__main__":
    # If this script is called from the command line, instruct Flask to enable
    # debugging for the app and listen on every IP address on the specified
    # port.
    app.debug = True
    app.run(host="0.0.0.0", port=19703)
