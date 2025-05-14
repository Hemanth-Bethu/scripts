--Count of accepted Invoices
SELECT COUNT(*) AS "Accepted Count"
FROM as4_incoming_sbd sbd

LEFT JOIN as4_documents_logs recv
    ON recv.doc_id = sbd.document_id

LEFT JOIN invoice inv
    ON inv.id = sbd.attached_invoice_id

WHERE sbd.legal_entity_id = $company_le_id
  AND sbd.message_state = 'ACCEPTED'
  AND (
    (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
    OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value IN ($vendor_abn))
  )
  AND (
    inv.document_type IS NULL
    OR inv.document_type IN ($document_type_filter)
  )
  AND COALESCE(sbd.offset_date_time, sbd.created_date_time) >= $__timeFrom()::timestamptz
  AND COALESCE(sbd.offset_date_time, sbd.created_date_time) < $__timeTo()::timestamptz;



--Drill down for Accepted Invoices
SELECT
  sbd.created_date_time AS "Created Date",
  sbd.sender_value AS "Sender ID",
  sbd.receiver_value AS "Receiver ID",
  sbd.message_state AS "Message Status",

  -- Vendor & Document Type
  recv.sender_party_name AS "Vendor Name",
  inv.document_type AS "Document Type",

  -- Delivery Info
  del.delivered AS "Delivered (Success?)",
  del.deliverydate AS "Delivery Date",
  del.pushed_to_enigma AS "Pushed to Enigma",
  del.tries AS "Delivery Tries",
  del.enigma_tries AS "Enigma Tries",

  -- Invoice Info
  inv.invoice_number AS "Invoice Number",
  inv.invoice_external_id AS "Invoice External ID",
  inv.access_point_received_date AS "Invoice Received Date",
  inv.amount_without_tax AS "Amount Without Tax",
  inv.tax_amount AS "Tax Amount",
  inv.total_invoice_amount AS "Total Invoice Amount",
  inv.currency_code AS "Currency",
  inv.approved_status AS "Approval Status",
  inv.paid_status AS "Payment Status",
  inv.erp_date_approved AS "ERP Date Approved",
  inv.erp_date_paid AS "ERP Date Paid",
  sbd.document_id AS "Peppol Document ID"

FROM as4_incoming_sbd sbd
LEFT JOIN as4_documents_logs recv ON recv.doc_id = sbd.document_id
LEFT JOIN as4_message_delivery del ON del.document_id = sbd.id
LEFT JOIN invoice inv ON inv.id = sbd.attached_invoice_id

WHERE
  sbd.legal_entity_id = $company_le_id
  AND sbd.message_state = 'ACCEPTED'
  AND (
    (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
    OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value IN ($vendor_abn))
  )
  AND (
    inv.document_type IS NULL
    OR inv.document_type IN ($document_type_filter)
  )
  AND COALESCE(sbd.offset_date_time, sbd.created_date_time) >= $__timeFrom()::timestamptz
  AND COALESCE(sbd.offset_date_time, sbd.created_date_time) < $__timeTo()::timestamptz

ORDER BY "Created Date" DESC;
