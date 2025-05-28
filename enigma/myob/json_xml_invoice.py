from flask import Flask, request, jsonify
from zeep import Client
from zeep.transports import Transport
from zeep.helpers import serialize_object
import requests
import logging
import os

app = Flask(__name__)

# ----------------------------------------------------------------
# Configuration (replace these with your actual credentials)
# ----------------------------------------------------------------
WSDL_URL = "https://impl-services1.wd105.myworkday.com/ccx/service/myob2/Resource_Management/v44.0?wsdl"

# OAuth2 settings
WORKDAY_TENANT_NAME = "myob2"
WORKDAY_HOSTNAME = "impl-services1.wd105.myworkday.com"

CLIENT_ID = "OGRiMjI1MWEtZjY2Ny00NzI0LWIzZTUtMzdjMGE1M2E3MWI1"
CLIENT_SECRET = "q5vwak4oq1ih01499i0f9laj2d245zv6vx76regwteig5oatculceg25fh7hzr4bodvkop3s0ebi57n1t3jpzyhzjv5nol3sc9g"
REFRESH_TOKEN = "domi45vw8wt675g3nagu6chfwxpsoy5wqic0kjm0dtfxb0nuh6q01rx1szmi6uyp7a9eocu9i9v0lzyi89buu8drwhmgbiqc8py"

WORKDAY_OAUTH_TOKEN_URL = (
    f"https://{WORKDAY_HOSTNAME}/ccx/oauth2/{WORKDAY_TENANT_NAME}/token"
)

# Enable detailed logging
logging.basicConfig(level=logging.INFO)


# ----------------------------------------------------------------
# Helper function to get a fresh Bearer token
# ----------------------------------------------------------------


def get_bearer_token():
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(WORKDAY_OAUTH_TOKEN_URL,
                             data=payload, headers=headers)
    response.raise_for_status()
    token_data = response.json()
    return token_data.get("access_token")


# ----------------------------------------------------------------
# Route to submit supplier invoice
# ----------------------------------------------------------------


@app.route('/api/submit-supplier-invoice', methods=['POST'])
def submit_supplier_invoice():
    try:
        # Get request payload
        data = request.get_json() or {}

        # Step 1: Get Bearer token
        bearer_token = get_bearer_token()
        logging.info("Bearer token retrieved successfully.")

        # Step 2: Create session with Authorization header
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {bearer_token}"})

        # Step 3: Create Zeep client with custom transport
        transport = Transport(session=session, operation_timeout=30)
        client = Client(wsdl=WSDL_URL, transport=transport)

        # Step 4: Prepare SOAP request parameters
        request_data = {
            'version': 'v44.0',
            'Add_Only': data.get('addOnly', True),
            'Supplier_Invoice_Reference': data.get('supplierInvoiceReference'),
            'Business_Process_Parameters': data.get('businessProcessParameters'),
            'Supplier_Invoice_Data': data.get('supplierInvoiceData')
        }

        # Step 5: Call the SOAP API method
        response = client.service.Submit_Supplier_Invoice(
            _soapheaders=None, **request_data)

        # Convert the Zeep response to a JSON-serializable Python dict
        response_data = serialize_object(response)

        # Step 6: Format and return response
        return jsonify({
            'status': 'success',
            'rawResponse': response_data  # <-- Full raw SOAP response inside JSON
        })

    except Exception as e:
        logging.exception("Error while submitting supplier invoice")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/submit-supplier-invoice-adjustment', methods=['POST'])
def submit_supplier_invoice_adjustment():
    try:
        # Get request payload
        data = request.get_json() or {}

        # Step 1: Get Bearer token
        bearer_token = get_bearer_token()
        logging.info("Bearer token retrieved successfully.")

        # Step 2: Create session with Authorization header
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {bearer_token}"})

        # Step 3: Create Zeep client with custom transport
        transport = Transport(session=session, operation_timeout=30)
        client = Client(wsdl=WSDL_URL, transport=transport)

        # Step 4: Prepare SOAP request parameters
        request_data = {
            'version': 'v44.0',
            'Add_Only': data.get('addOnly', True),
            'Supplier_Invoice_Adjustment_Reference': data.get('supplierInvoiceAdjustmentReference'),
            'Business_Process_Parameters': data.get('businessProcessParameters'),
            'Supplier_Invoice_Adjustment_Data': data.get('supplierInvoiceAdjustmentData')
        }

        # Step 5: Call the SOAP API method
        response = client.service.Submit_Supplier_Invoice_Adjustment(
            _soapheaders=None, **request_data)

        # Convert the Zeep response to a JSON-serializable Python dict
        response_data = serialize_object(response)

        # Step 6: Format and return response
        return jsonify({
            'status': 'success',
            'rawResponse': response_data  # <-- Full raw SOAP response inside JSON
        })

    except Exception as e:
        logging.exception("Error while submitting supplier invoice")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ----------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)