import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("SALESFORCE_BASE_URL")
CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID")
CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET")
USERNAME = os.getenv("SALESFORCE_USERNAME")
PASSWORD = os.getenv("SALESFORCE_PASSWORD")
N7USERNAME= os.getenv("NEURON7_USERNAME")
N7PASSWORD = os.getenv("NEURON7_PASSWORD")
N7URL = os.getenv("NEURON7_URL")

access_token = None
instance_url = None

def authenticate():
    global access_token, instance_url
    auth_url = f"{BASE_URL}/services/oauth2/token"
    response = requests.post(
        auth_url,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USERNAME,
            "password": PASSWORD
        }
    ).json()

    if "access_token" not in response:
        raise Exception(f"Auth failed: {response}")

    access_token = response["access_token"]
    instance_url = response["instance_url"]

def get_access_token():
    authenticate()      # ✅ Always fetch fresh token
    return access_token

def get_instance_url():
    authenticate()      # ✅ Always fetch fresh token
    return instance_url

def n7_auth_token() -> str:
    n7authurl = N7URL+"security/user/authenticate"
    payload = {
        "userName": N7USERNAME,
        "password": N7PASSWORD
    }

    response = requests.post(
        n7authurl,
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    response.raise_for_status()

    token = response.headers.get("Authorization")

    if not token:
        raise ValueError("Authorization token not found in response headers.")

    return token