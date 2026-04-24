import requests
from auth import get_access_token, get_instance_url


# -------------------------------
# 🔹 CREATE LEAD
# -------------------------------
def create_lead(first_name, last_name, email, company):
    try:
        token = get_access_token()
        base_url = get_instance_url()

        url = f"{base_url}/services/data/v57.0/sobjects/Lead/"

        data = {
            "FirstName": first_name,
            "LastName":  last_name,
            "Email":     email,
            "Company":   company
        }

        response = requests.post(
            url,
            json=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json"
            }
        )

        if response.status_code in [200, 201]:
            lead_id = response.json().get("id")
            return {
                "status":  "success",
                "lead_id": lead_id,
                "message": f"Lead created successfully. Lead ID: {lead_id}"
            }
        else:
            return {
                "status":  "error",
                "lead_id": None,
                "message": f"Failed to create lead: {response.text}"
            }

    except Exception as e:
        return {
            "status":  "error",
            "lead_id": None,
            "message": f"Error creating lead: {str(e)}"
        }


# -------------------------------
# 🔹 CREATE PERMISSION SET (SOAP)
# -------------------------------
def create_permission_set(api_name, label):
    try:
        token = get_access_token()
        base  = get_instance_url()

        url = f"{base}/services/Soap/m/64.0"

        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
  <env:Header>
    <urn:SessionHeader xmlns:urn="http://soap.sforce.com/2006/04/metadata">
      <urn:sessionId>{token}</urn:sessionId>
    </urn:SessionHeader>
  </env:Header>
  <env:Body>
    <createMetadata xmlns="http://soap.sforce.com/2006/04/metadata">
      <metadata xsi:type="PermissionSet" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <fullName>{api_name}</fullName>
        <label>{label}</label>
        <userPermissions>
          <enabled>true</enabled>
          <name>ApiEnabled</name>
        </userPermissions>
      </metadata>
    </createMetadata>
  </env:Body>
</env:Envelope>"""

        response = requests.post(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "text/xml",
                "SOAPAction":    '""'
            }
        )

        if response.status_code in [200, 201]:
            return {
                "status":            "success",
                "permission_set_id": api_name,   # SOAP doesn't return ID — use api_name as reference
                "message":           f"Permission Set '{label}' created successfully."
            }
        else:
            return {
                "status":            "error",
                "permission_set_id": None,
                "message":           f"Failed to create Permission Set: {response.text}"
            }

    except Exception as e:
        return {
            "status":            "error",
            "permission_set_id": None,
            "message":           f"Error creating Permission Set: {str(e)}"
        }


# -------------------------------
# 🔹 ASSIGN PERMISSION SET
# -------------------------------
def assign_permission_set(username, permission_set_name):
    try:
        token = get_access_token()
        base  = get_instance_url()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json"
        }

        # 1️⃣ Get User Id
        user_query = f"{base}/services/data/v61.0/query?q=SELECT+Id+FROM+User+WHERE+Username='{username}'"
        user_res   = requests.get(user_query, headers=headers).json()

        if not user_res.get("records"):
            return {
                "status":        "error",
                "assignment_id": None,
                "message":       f"User '{username}' not found."
            }

        user_id = user_res["records"][0]["Id"]

        # 2️⃣ Get Permission Set Id
        ps_query = f"{base}/services/data/v61.0/query?q=SELECT+Id+FROM+PermissionSet+WHERE+Name='{permission_set_name}'"
        ps_res   = requests.get(ps_query, headers=headers).json()

        if not ps_res.get("records"):
            return {
                "status":        "error",
                "assignment_id": None,
                "message":       f"Permission Set '{permission_set_name}' not found."
            }

        ps_id = ps_res["records"][0]["Id"]

        # 3️⃣ Assign Permission Set
        assign_url  = f"{base}/services/data/v61.0/sobjects/PermissionSetAssignment"
        assign_body = {
            "AssigneeId":      user_id,
            "PermissionSetId": ps_id
        }

        assign_res = requests.post(assign_url, json=assign_body, headers=headers)

        if assign_res.status_code in [200, 201]:
            assignment_id = assign_res.json().get("id")
            return {
                "status":        "success",
                "assignment_id": assignment_id,
                "message":       f"Permission Set '{permission_set_name}' assigned to '{username}' successfully."
            }
        else:
            return {
                "status":        "error",
                "assignment_id": None,
                "message":       f"Failed to assign Permission Set: {assign_res.text}"
            }

    except Exception as e:
        return {
            "status":        "error",
            "assignment_id": None,
            "message":       f"Error assigning Permission Set: {str(e)}"
        }


# -------------------------------
# 🔹 CREATE CASE
# -------------------------------
def create_case(subject, description, priority, origin):
    try:
        token = get_access_token()
        base  = get_instance_url()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json"
        }

        data = {
            "Subject":     subject,
            "Description": description,
            "Priority":    priority,
            "Origin":      origin
        }

        url      = f"{base}/services/data/v61.0/sobjects/Case/"
        response = requests.post(url, json=data, headers=headers)

        if response.status_code in [200, 201]:
            case_id = response.json().get("id")
            return {
                "status":   "success",
                "case_id":  case_id,
                "case_url": f"{base}/{case_id}",
                "message":  f"Case created successfully. Case ID: {case_id}"
            }
        else:
            return {
                "status":   "error",
                "case_id":  None,
                "case_url": None,
                "message":  f"Failed to create case: {response.text}"
            }

    except Exception as e:
        return {
            "status":   "error",
            "case_id":  None,
            "case_url": None,
            "message":  f"Error creating case: {str(e)}"
        }


# -------------------------------
# 🔹 UPDATE JIRA URL ON CASE
# -------------------------------
def update_jiraurl(case_id, jiraissueurl):
    try:
        token = get_access_token()
        base  = get_instance_url()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json"
        }

        url      = f"{base}/services/data/v61.0/sobjects/Case/{case_id}"
        data     = {"Jira_Issue_URL__C": jiraissueurl}
        response = requests.patch(url, json=data, headers=headers)

        if response.status_code == 204:
            return {
                "status":  "success",
                "case_id": case_id,
                "message": f"Jira URL attached to Case {case_id} successfully."
            }
        else:
            return {
                "status":  "error",
                "case_id": case_id,
                "message": f"Failed to attach Jira URL: {response.text}"
            }

    except Exception as e:
        return {
            "status":  "error",
            "case_id": case_id,
            "message": f"Error attaching Jira URL: {str(e)}"
        }


# -------------------------------
# 🔹 GET SALESFORCE USERS
# -------------------------------
def get_salesforce_users():
    try:
        access_token = get_access_token()
        base         = get_instance_url()

        soql = "SELECT Id, Name, Email, Username FROM User WHERE IsActive = true ORDER BY Name ASC"
        url  = f"{base}/services/data/v60.0/query"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json"
        }

        response = requests.get(url, headers=headers, params={"q": soql})
        response.raise_for_status()

        records = response.json().get("records", [])

        users = [
            {
                "id":       rec["Id"],
                "name":     rec["Name"],
                "email":    rec["Email"],
                "username": rec["Username"]
            }
            for rec in records
        ]

        return {
            "status": "success",
            "total":  len(users),
            "users":  users
        }

    except Exception as e:
        return {
            "status": "error",
            "total":  0,
            "users":  [],
            "message": f"Error fetching users: {str(e)}"
        }


# -------------------------------
# 🔹 UPDATE CASE STATUS
# -------------------------------
def update_case_status(case_id: str, status: str) -> dict:
    try:
        access_token = get_access_token()
        base         = get_instance_url()

        url = f"{base}/services/data/v60.0/sobjects/Case/{case_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json"
        }

        response = requests.patch(url, headers=headers, json={"Status": status})
        response.raise_for_status()

        return {
            "status":  "success",
            "case_id": case_id,
            "message": f"Case {case_id} status updated to '{status}' successfully."
        }

    except Exception as e:
        return {
            "status":  "error",
            "case_id": case_id,
            "message": f"Error updating case status: {str(e)}"
        }