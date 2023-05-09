# Importing the external libraries.
from flask import Flask, request, jsonify
import threading
import requests
import time
import re

# Importing all needed modules.
from config import ConfigManager
from cerber import SecurityManager
from schemas import MessageSchema

# Creation of the config manager.
config = ConfigManager("config.ini")

# Creation of the Security Manager.
security_manager = SecurityManager(config.security.secret_key)

# Creation of the message schema.
message_schema = MessageSchema()

# Setting up the Flask dependencies.
app = Flask(__name__)
app.secret_key = config.security.secret_key

# Creating the security manager for the service discovery.
service_discovery_security_manager = SecurityManager(config.service_discovery.secret_key)

# Computing the HMAC for Service Discovery registration.
SERVICE_DISCOVERY_HMAC = service_discovery_security_manager._SecurityManager__encode_hmac(
    config.generate_info_for_service_discovery()
)

DIALOG_MANAGER_DATA = {}

def send_heartbeats():
    '''
        This function sends heartbeat requests to the service discovery.
    '''
    # Getting the Service discovery hmac for message.
    service_discovery_hmac = service_discovery_security_manager._SecurityManager__encode_hmac({"status_code" : 200})
    while True:
        # Senting the request.
        response = requests.post(
            f"http://{config.service_discovery.host}:{config.service_discovery.port}/heartbeat/{config.general.name}",
            json = {"status_code" : 200},
            headers = {"Token" : service_discovery_hmac}
        )
        # Making a pause of 30 seconds before sending the next request.
        status_code = response.status_code
        time.sleep(30)

# Registering to the Service discovery.
while True:
    # Sending the request to the service discovery.
    resp = requests.post(
        f"http://{config.service_discovery.host}:{config.service_discovery.port}/{config.service_discovery.register_endpoint}",
        json = config.generate_info_for_service_discovery(),
        headers={"Token" : SERVICE_DISCOVERY_HMAC}
    )

    # If the request is successful then we are going to request the credentials of the needed services.
    if resp.status_code == 200:
        while True:
            time.sleep(3)
            # Calculating the service discovery HMAC.
            service_discovery_hmac = SecurityManager(config.service_discovery.secret_key)._SecurityManager__encode_hmac(
                {"service_names" : ["dialog-manager"]}
            )
            # Getting the dialog manager credentials.
            res = requests.get(
                f"http://{config.service_discovery.host}:{config.service_discovery.port}/get_services",
                json = {"service_names" : ["dialog-manager"]},
                headers={"Token" : service_discovery_hmac}
            )
            if res.status_code == 200:
                # Starting the process of sending heartbeats.
                time.sleep(5)
                threading.Thread(target=send_heartbeats).start()
                res_json = res.json()

                # Extracting the Dialog Manager credentials from response.
                DIALOG_MANAGER_DATA = {
                    "host" : res_json["dialog-manager"]["general"]["host"],
                    "port" : res_json["dialog-manager"]["general"]["port"],
                    "security_manager" : SecurityManager(
                        res_json["dialog-manager"]["security"]["secret_key"]
                    )
                }
                break
        break
    else:
        time.sleep(10)

@app.route("/msg", methods=["POST"])
def msg():
    # Checking the access token.
    check_response = security_manager.check_request(request)
    if check_response != "OK":
        return check_response, check_response["code"]
    else:
        status_code = 200

        result = message_schema.validate_json(request.json)
        if status_code != 200:
            # If the request body didn't passed the json validation a error is returned.
            return result, status_code
        else:
            # Checking if the message is from a bot.
            if result["is_bot"]:
                return {
                    "text" : "Unfortunately I'm not allowed to chat with bots!",
                    "chat_id" : result["chat_id"]
                }, 200
            # Checking if the message was sent privately to the chatbot.
            if result["chat_type"] != "private":
                return {
                    "text" : "Unfortunately I work only in private chats!",
                    "chat_id" : result["chat_id"]
                }
            # Creation of the request body to the Dialog Manager.
            dialog_manager_request = {
                "text" : result["text"],
                "telegram_user_id" : result["telegram_user_id"],
                "chat_id" : result["chat_id"],
                "first_name" : result["first_name"],
                "last_name" : result["last_name"],
                "username" : result["username"]
            }

            # Computing the HMAC of the message for the Dialog Manager.
            service_hmac = DIALOG_MANAGER_DATA["security_manager"]._SecurityManager__encode_hmac(
                dialog_manager_request
            )
            # Checking is the message is an registration key.
            if bool(re.match(config.matcher.re, result["text"])):
                # Sending the request to the /user endpoint of the Dialog Manager to register him.
                response = requests.post(
                    f"http://{DIALOG_MANAGER_DATA['host']}:{DIALOG_MANAGER_DATA['port']}/user",
                    json = dialog_manager_request,
                    headers = {"Token" : service_hmac}
                )
            else:
                # Sending the request to the /message endpoint.
                response = requests.post(
                    f"http://{DIALOG_MANAGER_DATA['host']}:{DIALOG_MANAGER_DATA['port']}/message",
                    json = dialog_manager_request,
                    headers = {"Token" : service_hmac}
                )
            return {
                "message" : "OK"
            }, 200

# Running the flask application.
app.run(
    port = config.general.port,
    host = config.general.host
)