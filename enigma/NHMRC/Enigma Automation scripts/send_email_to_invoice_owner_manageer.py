try:
    owner = record.invoice_owner
    if not owner:
        log("No Invoice Owner – e-mail skipped", record=record)

    else:
        emp = owner.employee_id
        mgr = emp.parent_id if emp else False
        if not mgr:
            log(f"Owner has no manager – e-mail skipped: {owner}, {owner.employee_id}", record=record)

        else:
            # 1️⃣  Preferred address: HR Employee’s work_email
            email_to = mgr.work_email.strip() if mgr.work_email else ''

            # 2️⃣  Fallback: manager’s user partner or HR partner e-mail
            if not email_to:
                recipient_prt = (
                    mgr.user_id.partner_id
                    if mgr.user_id
                    else mgr.partner_id
                )
                email_to = (recipient_prt.email or '').strip()

            if not email_to:
                log("Manager has no work_email or partner e-mail – skipped", record=record)
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
                    # ───────────────────────────────────────────────────────────────── subject
                    'subject': (
                        f"Action Required – Claim Not Found for Invoice Matching "
                        f"(Invoice {record.display_name})"
                    ),

                    # ───────────────────────────────────────────────────────────────── address
                    'email_to': email_to,

                    # ─────────────────────────────────────────────────────────────────  body
                    'body_html': f"""
                        <p>Dear {mgr.name},</p>

                        <p>
                          We would like to inform you that invoice
                          <strong>{record.display_name}</strong> for the total amount of
                          <strong>${record.total_amount_incl_vat:,.2f}</strong>, related to
                          contract <strong>{record.contract_id.name or 'N/A'}</strong>, was
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
    log(f"Exception occurred in Sending email {e}", record=record)
    raise e