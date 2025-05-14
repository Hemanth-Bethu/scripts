

--Count query
SELECT COUNT(*) AS "Delivery Failed Count"
FROM as4_incoming_sbd sbd

LEFT JOIN as4_documents_logs recv
    ON recv.doc_id = sbd.document_id

LEFT JOIN as4_message_delivery del
    ON del.document_id = sbd.id

LEFT JOIN invoice inv
    ON inv.id = sbd.attached_invoice_id

WHERE sbd.legal_entity_id = $company_le_id
  AND del.delivered = FALSE

  -- Vendor ABN Filtering
  AND (
    (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
    OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value IN ($vendor_abn))
  )

  -- Document Type Filtering
  AND (
    inv.document_type IS NULL
    OR inv.document_type IN ($document_type_filter)
  )

  -- Date Range Filtering
  AND COALESCE(
        sbd.offset_date_time,
        sbd.created_date_time
      ) >= $__timeFrom()::timestamptz
  AND COALESCE(
        sbd.offset_date_time,
        sbd.created_date_time
      ) < $__timeTo()::timestamptz;



--Drill down query

SELECT
    sbd.created_date_time AT TIME ZONE 'Australia/ACT' AS "SBD Created Date",
    recv.sender_party_name AS "Vendor Name",
    inv.invoice_number AS "Invoice Number",
    log.response AS "Delivery Response",
    del.delivered AS "Delivered (Success?)",
    inv.document_type AS "Document Type",
    del.deliverydate AT TIME ZONE 'Australia/ACT' AS "Delivery Date",
    del.pushed_to_enigma AS "Pushed to Enigma",
    del.tries AS "Delivery Tries",
    del.enigma_tries AS "Enigma Tries",
    sbd.sender_value AS "Sender ID",
    sbd.receiver_value AS "Receiver ID",
    del.updated_date_time AT TIME ZONE 'Australia/ACT' AS "Last Attempted On",
    del.processed AS "Marked Processed"

FROM as4_incoming_sbd sbd

LEFT JOIN as4_documents_logs recv
    ON recv.doc_id = sbd.document_id

LEFT JOIN as4_message_delivery del
    ON del.document_id = sbd.id

LEFT JOIN invoice inv
    ON inv.id = sbd.attached_invoice_id

-- Join latest response per delivery message
LEFT JOIN (
    SELECT DISTINCT ON (l1.id_message_del)
        l1.id_message_del,
        l1.response
    FROM document_delivery_logs l1
    ORDER BY l1.id_message_del, l1.id DESC
) log ON log.id_message_del = del.id

WHERE sbd.legal_entity_id = $company_le_id
  AND del.delivered = FALSE

  -- Vendor ABN Filtering
  AND (
    (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
    OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value IN ($vendor_abn))
  )

  -- Document Type Filtering
  AND (
    inv.document_type IS NULL
    OR inv.document_type IN ($document_type_filter)
  )

  -- Date Range Filtering
  AND COALESCE(
        sbd.offset_date_time AT TIME ZONE 'Australia/ACT',
        sbd.created_date_time AT TIME ZONE 'Australia/ACT'
      ) >= $__timeFrom()::timestamptz
  AND COALESCE(
        sbd.offset_date_time AT TIME ZONE 'Australia/ACT',
        sbd.created_date_time AT TIME ZONE 'Australia/ACT'
      ) < $__timeTo()::timestamptz

ORDER BY "SBD Created Date" DESC;

