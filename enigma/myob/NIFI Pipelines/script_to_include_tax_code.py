from datetime import datetime
import json
import java.io
from org.apache.commons.io import IOUtils
from java.nio.charset import StandardCharsets
from org.apache.nifi.processor.io import StreamCallback

global documentId, posting_date

class ModJSON(StreamCallback):
    def __init__(self):
        pass

    def get_tax_code(self, percent):
		return "{}% GST".format(percent)

    def normalize_percent(self, percent):
        try:
            return str(int(round(float(percent))))
        except Exception:
            return "0"  # Default fallback if invalid

    def map_tax_code_id(self, percent_str, country_code):
        mapping = {
            "AU": {
                "10": "AUS_GST_10",
                "0": "AUS_GST_0"
            },
            "NZ": {
                "15": "NZL_GST_15",
                "0": "NZL_GST_0"
            }
        }
        return mapping.get(country_code, {}).get(percent_str, "UNKNOWN")

    def safe_get_percent(self, data):
        try:
            tax_total = data.get("voucher_id_ocr_data_scan_response", {}).get("Invoice", {}).get("TaxTotal", {})
            tax_subtotal = tax_total.get("TaxSubtotal", {})
            if isinstance(tax_subtotal, list) and len(tax_subtotal) > 0:
                tax_subtotal = tax_subtotal[0]
            tax_category = tax_subtotal.get("TaxCategory", {})
            percent = tax_category.get("Percent")
            return self.normalize_percent(percent)
        except Exception:
            pass  # Continue to fallback

        # Fallback: Derive from known totals
        try:
            subtotal = float(data.get("voucher_id_new_subtotal", "0"))
            tax = float(data.get("voucher_id_new_tax", "0"))
            if subtotal > 0:
                derived_percent = (tax / subtotal) * 100
                return self.normalize_percent(derived_percent)
        except Exception:
            pass

        return "0"  # Default fallback

    def process(self, inputStream, outputStream):
        text = IOUtils.toString(inputStream, StandardCharsets.UTF_8)
        try:
            data = json.loads(text)

            invoice = data.get("voucher_id_ocr_data_scan_response", {}).get("Invoice", {})

            # Extract country code from AccountingCustomerParty
            country_code = invoice.get("AccountingCustomerParty", {}) \
                                  .get("Party", {}) \
                                  .get("PostalAddress", {}) \
                                  .get("Country", {}) \
                                  .get("IdentificationCode", "AU")  # Default to AU if missing

            # Header tax code (structured or derived)
            header_tax_percent = self.safe_get_percent(data)
            data["header_tax_code"] = self.map_tax_code_id(header_tax_percent, country_code)
            data["header_country_code"] = country_code
            data["header_tax_percent"] = header_tax_percent

            # Line item tax codes
            for item in data.get("line_items", []):
                raw_percent = item.get("tax_percent")
                normalized_percent = self.normalize_percent(raw_percent)
                item["line_tax_code"] = self.map_tax_code_id(normalized_percent, country_code)
                item["line_tax_percent"] = normalized_percent

            # Output enriched JSON
            outputStream.write(bytearray(json.dumps(data, indent=4).encode('utf-8')))

        except Exception as e:
            error_payload = {
                "error": "Failed to process input JSON",
                "exception": str(e),
                "original_data": text
            }
            outputStream.write(bytearray(json.dumps(error_payload, indent=4).encode('utf-8')))


# Begin NiFi flowfile processing
flowFile = session.get()
if flowFile is not None:
    documentId = flowFile.getAttribute("document_id")
    posting_date = flowFile.getAttribute("posting_date")
    flowFile = session.write(flowFile, ModJSON())
    session.transfer(flowFile, REL_SUCCESS)
    session.commit()