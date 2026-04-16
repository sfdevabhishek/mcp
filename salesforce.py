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
            "LastName": last_name,
            "Email": email,
            "Company": company
        }

        response = requests.post(
            url,
            json=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code in [200, 201]:
            return f"✅ Lead created successfully: {response.json()}"
        else:
            return f"❌ Failed to create lead: {response.text}"

    except Exception as e:
        return f"❌ Error creating lead: {str(e)}"


# -------------------------------
# 🔹 ASSIGN PERMISSION SET
# -------------------------------
def assign_permission_set(username, permission_set_name):
    try:
        token = get_access_token()
        base = get_instance_url()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # 1️⃣ Get User Id
        user_query = f"{base}/services/data/v61.0/query?q=SELECT+Id+FROM+User+WHERE+Username='{username}'"
        user_res = requests.get(user_query, headers=headers).json()

        if not user_res.get("records"):
            return "❌ User not found"

        user_id = user_res["records"][0]["Id"]

        # 2️⃣ Get Permission Set Id
        ps_query = f"{base}/services/data/v61.0/query?q=SELECT+Id+FROM+PermissionSet+WHERE+Name='{permission_set_name}'"
        ps_res = requests.get(ps_query, headers=headers).json()

        if not ps_res.get("records"):
            return "❌ Permission Set not found"

        ps_id = ps_res["records"][0]["Id"]

        # 3️⃣ Assign Permission Set
        assign_url = f"{base}/services/data/v61.0/sobjects/PermissionSetAssignment"

        assign_body = {
            "AssigneeId": user_id,
            "PermissionSetId": ps_id
        }

        assign_res = requests.post(assign_url, json=assign_body, headers=headers)

        if assign_res.status_code in [200, 201]:
            return "✅ Permission Set assigned successfully"
        else:
            return f"❌ Failed to assign Permission Set: {assign_res.text}"

    except Exception as e:
        return f"❌ Error assigning Permission Set: {str(e)}"


# -------------------------------
# 🔹 CREATE PERMISSION SET (SOAP)
# -------------------------------
def create_permission_set(api_name, label):
    try:
        token = get_access_token()
        base = get_instance_url()

        # Metadata SOAP endpoint
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
                "Content-Type": "text/xml",
                "SOAPAction": '""'
            }
        )

        if response.status_code in [200, 201]:
            return f"✅ Permission Set created: {response.text}"
        else:
            return f"❌ Failed to create Permission Set: {response.text}"

    except Exception as e:
        return f"❌ Error creating Permission Set: {str(e)}"

        # -------------------------------
# 🔹 CREATE CASE
def create_case(subject, description, priority, origin,jiraissueurl):
    try:
        token = get_access_token()
        base = get_instance_url()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        data = {
            "Subject": subject,
            "Description": description,
            "Priority": priority,
            "Origin": origin,
            "Jira_Issue_URL__c": jiraissueurl
        }

        url = f"{base}/services/data/v61.0/sobjects/Case/"
        response = requests.post(url, json=data, headers=headers)

        if response.status_code in [200, 201]:
            case_id = response.json().get("id")
            return f"✅ Case created successfully. Case ID: {case_id}"
        else:
            return f"❌ Failed to create case: {response.text}"

    except Exception as e:
        return f"❌ Error creating case: {str(e)}"


# -------------------------------
# 🔹 UPDATE CASE STATUS
# -------------------------------
def update_case_status(case_id, status):
    try:
        token = get_access_token()
        base = get_instance_url()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Valid statuses: New, Working, Escalated, Closed
        url = f"{base}/services/data/v61.0/sobjects/Case/{case_id}"
        data = {"Status": status}

        response = requests.patch(url, json=data, headers=headers)

        if response.status_code == 204:
            return f"✅ Case {case_id} status updated to '{status}' successfully"
        else:
            return f"❌ Failed to update case: {response.text}"

    except Exception as e:
        return f"❌ Error updating case: {str(e)}"