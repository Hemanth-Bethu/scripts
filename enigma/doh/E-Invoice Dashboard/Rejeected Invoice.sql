
--Count for rejected Invoices
SELECT COUNT(*) AS "Rejected Count"
FROM as4_incoming_sbd sbd

LEFT JOIN as4_documents_logs recv
    ON recv.doc_id = sbd.document_id

LEFT JOIN as4_message_delivery del
    ON del.document_id = sbd.id

LEFT JOIN invoice inv
    ON inv.id = sbd.attached_invoice_id

WHERE sbd.legal_entity_id = $company_le_id
  AND sbd.message_state = 'REJECTED'
  AND (
    (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
    OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value IN ($vendor_abn))
  )
  AND (
    inv.document_type IS NULL
    OR inv.document_type IN ($document_type_filter)
  )
  AND COALESCE(
        sbd.offset_date_time,
        sbd.created_date_time
      ) >= $__timeFrom()::timestamptz
  AND COALESCE(
        sbd.offset_date_time,
        sbd.created_date_time
      ) < $__timeTo()::timestamptz;






--Drill down for rejected Invoices

SELECT
    sbd.created_date_time AT TIME ZONE 'Australia/ACT' AS "SBD Created Date",
    sbd.sender_value AS "Sender ID",
    sbd.receiver_value AS "Receiver ID",


    recv.sender_party_name AS "Vendor Name",
    sbd.message_state AS "SBD Message Status",  -- Should always be 'REJECTED'
    sbd.rejected_reason AS "Rejected Reason",
    del.pushed_to_enigma AS "Pushed to Enigma"

FROM as4_incoming_sbd sbd

LEFT JOIN as4_documents_logs recv
    ON recv.doc_id = sbd.document_id

LEFT JOIN as4_message_delivery del
    ON del.document_id = sbd.id

WHERE sbd.legal_entity_id = $company_le_id
  AND sbd.message_state = 'REJECTED'

  -- Vendor ABN Filtering
  AND (
    (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
    OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value IN ($vendor_abn))
  )

  -- Document Type Filtering
  AND (
    sbd.type_ IS NULL
    OR sbd.type_ IN ($document_type_filter)
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

