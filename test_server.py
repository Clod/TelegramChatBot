"""
This module contains a simple Flask application for testing SSL configuration.

The application has a single route '/' that returns a greeting message. It is designed to run on port 443 with SSL enabled, using the provided certificate and private key files.

Example:
    To run the server, execute this script directly. The server will start listening on 0.0.0.0:443 with SSL enabled.

Attributes:
    app (Flask): The Flask application instance.
"""

from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World! (SSL Test)'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=443, ssl_context=('certs/fullchain.pem', 'certs/privkey.pem'))
