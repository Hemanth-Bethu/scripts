## Vendor Automations
# Code for update reference

# Code to check the Contract Owner and send email to manger of invoice owner
```python
# Define the domain
# Define the domain
two_days_ago = (datetime.datetime.now().replace(microsecond=0) - datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
domain = [
    ("company_id", "in", [37]),
    ("state", "in", ["reviewing", "waiting_for_1st_approval"]),
    ("contract_claim_matched", "!=", True),
    ("invoice_owner", "!=", False),
    ("type_of_match", "=", "contract"),
    ("custom_10", "=", False),
    ("next_approver_assigned_date", "<=", two_days_ago)
]

# Fetch the records
records = env['invoicescan.voucher'].search(domain)

if not records:
    log("No matching records found for email notification")

# Process each record
for record in records:
    try:
        owner = record.invoice_owner
        if not owner:
            log("No Invoice Owner – e-mail skipped")
            record.message_post(body="No Invoice Owner – e-mail skipped.")
            record.write({"custom_10": "No Invoice Owner – e-mail skipped"})
            continue

        emp = owner.employee_id
        mgr = emp.parent_id if emp else False
        if not mgr:
            log(f"Owner has no manager – e-mail skipped: {owner}, {owner.employee_id}")
            record.message_post(body=f"Owner has no manager – e-mail skipped: {owner.name}, {owner.employee_id}")
            record.write({"custom_10": "Owner has no manager – e-mail skipped"})
            continue

        # Preferred address: HR Employee’s work_email
        email_to = mgr.work_email.strip() if mgr.work_email else ''

        # Fallback to partner email if no work_email
        if not email_to:
            recipient_prt = mgr.user_id.partner_id if mgr.user_id else mgr.partner_id
            email_to = (recipient_prt.email or '').strip()

        if not email_to:
            log("Manager has no work_email or partner e-mail – skipped")
            record.message_post(body="Manager has no work_email or partner e-mail – skipped.")
            record.write({"custom_10": "Manager has no work_email or partner e-mail – skipped"})
            continue

        # Build the CTA button
        deeplink = record.get_view_record_redirect_url()
        doc_id = record.document_id or 'N/A'
        button_html = f"""
          <a href="{deeplink}"
             style="background:#2f67d0;color:#fff;text-decoration:none;
                    padding:14px 24px;border-radius:6px;display:inline-block;
                    font-weight:600;font-family:Arial,sans-serif;font-size:14px;">
             Open Document {doc_id}
          </a>
        """

        # Queue the email
        Mail = env['mail.mail'].sudo()
        mail = Mail.create({
            'subject': f"Action Required – Claim Not Found for Invoice Matching (Invoice {record.display_name})",
            'email_to': email_to,
            'body_html': f"""
                <p>Dear {mgr.name},</p>

                <p>
                  We would like to inform you that invoice
                  <strong>{record.display_name}</strong> for the total amount of
                  <strong>${record.total_amount_incl_vat:,.2f}</strong>, related to
                  contract <strong>{record.contract_id.external_ref or 'N/A'}</strong>, was
                  processed through Enigma’s OCR, and the auto-matching function
                  <em>failed</em>.
                </p>

                <p>
                  <strong>Reason:</strong> No suitable claim was found for this invoice.
                </p>

                <p>
                  To avoid processing delays, please review the invoice and create the
                  appropriate claim in TechOne as soon as possible.
                </p>

                {button_html}

                <p>Kind regards,<br/>Accounts Payable Bot</p>
            """,
        })
        mail.send()
        log(f"E-mail {mail.id} queued to {email_to} for Invoice {record.display_name}")
        record.message_post(body=f"E-mail queued to {email_to} for Invoice {record.display_name}")
        record.write({"custom_10": "Email sent to manager"})

    except Exception as e:
        log(f"Exception occurred in Sending email {e}")
        record.message_post(body=f"Exception occurred while sending e-mail: {str(e)}")
        record.write({"custom_10": f"Exception occurred: {str(e)}"})

```


## Cron Automations
# Code to send email to create claim to Invoice Owner 
```python
try:
    owner = record.invoice_owner
    if not owner:
        log("No Invoice Owner – e-mail skipped", record=record)

    else:
        # Validate that the owner has a valid partner
        partner = owner.partner_id
        if not partner:
            log(f"Owner {owner.name} has no associated partner – e-mail skipped", record=record)
        else:
            email_to = (partner.email or '').strip()

            if not email_to:
                log(f"Owner {owner.name} has no partner e-mail – skipped", record=record)
            else:
                # Build the CTA button
                deeplink = record.get_view_record_redirect_url()
                doc_id = record.document_id or 'N/A'
                button_html = f"""
                  <a href="{deeplink}"
                     style="background:#2f67d0;color:#fff;text-decoration:none;
                            padding:14px 24px;border-radius:6px;display:inline-block;
                            font-weight:600;font-family:Arial,sans-serif;font-size:14px;">
                     Open Document {doc_id}
                  </a>
                """

                Mail = env['mail.mail'].sudo()
                mail = Mail.create({
                    'subject': (
                        f"Action Required – Claim Not Found for Invoice Matching "
                        f"(Invoice {record.display_name})"
                    ),
                    'email_to': email_to,
                    'res_id': record.id,
                    'model': record._name,
                    'body_html': f"""
                        <p>Dear {owner.name},</p>

                        <p>
                          We would like to inform you that invoice
                          <strong>{record.display_name}</strong> for the total amount of
                          <strong>${record.total_amount_incl_vat:,.2f}</strong>, related to
                          contract <strong>{record.contract_id.external_ref or 'N/A'}</strong>, was
                          processed through Enigma’s OCR, and the auto-matching function
                          <em>failed</em>.
                        </p>

                        <p>
                          <strong>Reason:</strong> No suitable claim was found for this invoice.
                        </p>

                        <p>
                          To avoid processing delays, please review the invoice and create the
                          appropriate claim in TechOne as soon as possible.
                        </p>

                        {button_html}

                        <p>Kind regards,<br/>Accounts Payable Bot</p>
                    """,
                })
                mail.send()
                log(f"E-mail {mail.id} queued to {email_to}", record=record)

except Exception as e:
    log(f"Exception occurred in Sending email: {e}", record=record)
    raise e


```
