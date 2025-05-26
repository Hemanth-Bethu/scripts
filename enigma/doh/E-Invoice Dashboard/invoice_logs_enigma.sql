SELECT
    am.voucher_document_id AS "Voucher Document ID",
    am.invoice_type_e_invoice AS "Invoice Source",
    am.ref AS "Invoice Reference",
    am.invoice_date AS "Invoice Date",
    v.payment_date AS "Due Date",
    rp.name AS "Vendor Name",
    rp.vat AS "Vendor ABN",
    am.amount_total AS "Total Amount",
    rc.name AS "Currency",

    -- PO Number
    po.name AS "PO Number",

    -- Invoice Owner
    ru.name AS "Invoice Owner",

    -- Derived Document Type
    CASE
        WHEN am.move_type IN ('out_invoice', 'in_invoice') THEN 'Invoice'
        WHEN am.move_type IN ('out_refund', 'in_refund') THEN 'CreditNote'
        ELSE 'Other'
    END AS "Document Type",

    -- Enigma → Concur
    am.state AS "Enigma State",
    am.payment_state AS "Payment State",
    am.external_payment_date AS "Concur Payment Date",
    am.erp_state AS "Concur Sync State",
    am.erp_response AS "ERP Response",

    -- Timestamps
    v.create_date AS "Enigma Received On",
    am.create_date AS "Processed On"

FROM account_move am
LEFT JOIN res_partner rp ON rp.id = am.partner_id
LEFT JOIN res_currency rc ON rc.id = am.currency_id
LEFT JOIN invoicescan_voucher v ON v.id = am.voucher_id
LEFT JOIN purchase_order po ON po.id = v.order_number_id
LEFT JOIN res_users ru ON ru.id = am.invoice_owner

WHERE am.company_id = $enigma_company_id
  AND am.invoice_date >= $__timeFrom()::date
  AND am.invoice_date < $__timeTo()::date

  -- Vendor name filter
  AND rp.name IN ($vendor)

  AND am.invoice_type_e_invoice IN ('e-invoice', 'ocr')

  -- Document type filter
  AND (
    ('Invoice' IN ($document_type_filter) AND am.move_type IN ('in_invoice', 'out_invoice')) OR
    ('CreditNote' IN ($document_type_filter) AND am.move_type IN ('in_refund', 'out_refund'))
  )

ORDER BY am.invoice_date DESC;
