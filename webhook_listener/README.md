# NetBox Webhook Listener: Application Files

This application is *not* designed to demonstrate best practices for Python Flask apps, but to demonstrate that even a simple application can result in useful automation tasks.

Below is a listing of the source files and a description of what they contain and the tasks performed.

## .gitignore
When present, the ```.gitignore``` file is processed by ```git``` and provides instruction on files to exclude from the repository. In this project, the ```.gitignore``` file has a single entry: ```credentials.py```. This allows a templated credential file (with the extension ```.dist```) to be present in the repository, but the copied ```credentials.py``` file will be excluded from any ```git add``` or ```git commit``` operation. More information on ```.gitignore``` can be found at [git scm documentation for gitignore](https://git-scm.com/docs/gitignore). 

## credentials.py(.dist)
This file contains variable definitions for the NetBox URL and API token as well as device credentials for the simulated environment. ```credentials.py.dist``` contains generic examples, and should be copied to a file named ```credentials.py``` which will be read by the main application. The ```credentials.py``` file will never be included in the ```git``` repository due to the ```.gitignore``` contents.

## config.py
Contains configuration settings for the webhook listener. TLS verification settings, HTTP retry settings, and HTTP headers common to the RESTCONF JSON implementation are defined in this file. Some functions are present to prepare the pynetbox API as well as a ```requests.Session()``` object, which will be used when performing RESTCONF operations against the simulated network devices.

## common_functions.py
Functions that may be imported and used by any script are in this file. To import and use functions, you can use an ```import``` statement at the top of your Python script like so:

```python
from common_functions import parse_interface_name
```

After this import statement, the common ```parse_interface_name``` function can be accessed.

## main.py
The initial entrypoint of the Flask application. The ```main.py``` file contains initialization functions to start Flask and set URL endpoints for anticipated incoming webhooks.

## interface_api.py
Webhooks related to interface operations will use functions contained in this file. There is a function which handles incoming data, named ```manage_device_interface```. Data is parsed by this function and supporting functions are called as necessary to configure an interface on the target device.

## ipam_api.py
Webhooks related to IPAM operations will use these functions. The ```manage_interface_ip_address``` function is imported by the Flask app in ```main.py``` and provides data parsing and appropriate routing to configure (or unconfigure) interface IP addresses based on the data received by NetBox.
