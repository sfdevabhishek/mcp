import requests
from auth import n7_auth_token

N7URL = os.getenv("NEURON7_URL")

sessionId = None
def get_session_id():
    token = n7_auth_token()  # Salesforce access token
    N7Chaturl = N7URL+"api/v1/chat-session"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "userName": "Jhon"
    }
    response = requests.post(
        N7Chaturl,
        json=payload,
        headers=headers
    )
    response.raise_for_status()
    data = response.json()
    session_id = data.get("sessionId")
    sessionId = session_id
    return session_id


def get_messages():
    sId = "15062c58-52e5-4cdd-b369-72ecd4907ce9"
    token = n7_auth_token()  # Salesforce access token
    # Salesforce access token
    N7MessageUrl = N7URL+"api/v2/intelligent-search"
    headers = {
        "Authorization": f"Bearer {token}",
        "N7-Chat-Session-Id": sId,
        "Content-Type": "application/json"
    }
    payload = {
        "query": "Hello",
        "userName": "Jhon"
    }
    response = requests.post(
        N7MessageUrl,
        json=payload,
        headers=headers
    )
    response.raise_for_status()
    fullResponse = response.json()
    mainData = fullResponse.get("data", {})
    message = mainData.get("response")
    return message



