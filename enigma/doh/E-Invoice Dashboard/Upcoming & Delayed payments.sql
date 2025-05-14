


--count query
-- ── SUMMARY: Upcoming & Delayed Payments ───────────────────────────────────
WITH base AS (
    SELECT
        inv.id,
        inv.payment_due_date,
        inv.paid_status,
        inv.access_point_received_date,
        inv.total_invoice_amount,
        inv.erp_date_paid,
        inv.currency_code,
        inv.amount_without_tax,
        inv.invoice_number,
        inv.invoice_external_id,
        sbd.sender_value,
        sbd.created_date_time,
        /* normalised timestamp used for the dashboard range filter */
        COALESCE(
            sbd.offset_date_time AT TIME ZONE 'Australia/ACT',
            sbd.created_date_time AT TIME ZONE 'Australia/ACT'
        ) AS doc_ts
    FROM as4_incoming_sbd       sbd
    LEFT JOIN invoice           inv ON inv.id = sbd.attached_invoice_id
    WHERE sbd.legal_entity_id = $company_le_id
      /* mandatory invoice fields */
      AND inv.paid_status            IS NOT NULL
      AND inv.payment_due_date       IS NOT NULL
      AND inv.access_point_received_date IS NOT NULL
      /* Vendor ABN */
      AND (
           (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
        OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value               IN ($vendor_abn))
      )
      /* Optional document type */
      AND (
           inv.document_type IS NULL
        OR inv.document_type IN ($document_type_filter)
      )
      /* Dashboard time window */
      AND COALESCE(
            sbd.offset_date_time AT TIME ZONE 'Australia/ACT',
            sbd.created_date_time AT TIME ZONE 'Australia/ACT'
          ) >= $__timeFrom()::timestamptz
      AND COALESCE(
            sbd.offset_date_time AT TIME ZONE 'Australia/ACT',
            sbd.created_date_time AT TIME ZONE 'Australia/ACT'
          ) <  $__timeTo()::timestamptz
)

SELECT
    CASE
        WHEN payment_due_date < CURRENT_DATE - INTERVAL '5 days'
             AND paid_status <> 'Paid'  THEN 'Overdue > 5 days'
        WHEN payment_due_date < CURRENT_DATE
             AND paid_status <> 'Paid'  THEN 'Overdue'
        ELSE 'Upcoming / Paid'
    END        AS "Payment Status Category",
    COUNT(*)   AS "Invoice Count"
FROM   base
GROUP  BY 1
ORDER  BY 1;




--Drill down query

SELECT
  -- Categorized status
  CASE
    WHEN inv.payment_due_date < CURRENT_DATE - INTERVAL '5 days'
    AND inv.paid_status != 'Paid' THEN 'Overdue > 5 days'
    WHEN inv.payment_due_date < CURRENT_DATE
    AND inv.paid_status != 'Paid' THEN 'Overdue'
    ELSE 'Upcoming / Paid'
  END AS "Payment Status Category",

  -- Extracted Vendor (Tax ID) Logic
  CASE
    WHEN sbd.sender_value LIKE '%:%' THEN split_part(sbd.sender_value, ':', 2)
    ELSE sbd.sender_value
  END AS "Tax ID",

  inv.invoice_number AS "Invoice Number",
  inv.invoice_external_id AS "Invoice External ID",

  -- Days Late: actual (if paid), estimate (if unpaid & overdue)
  CASE
    WHEN inv.erp_date_paid IS NOT NULL
    AND inv.erp_date_paid > inv.access_point_received_date + INTERVAL '5 days' THEN DATE_PART(
      'day',
      inv.erp_date_paid - inv.access_point_received_date
    ) - 5
    WHEN inv.erp_date_paid IS NULL
    AND CURRENT_DATE > inv.access_point_received_date + INTERVAL '5 days' THEN DATE_PART(
      'day',
      CURRENT_DATE - inv.access_point_received_date
    ) - 5
    ELSE NULL
  END AS "Delay",

  -- Penalty: actual or estimated (using 8% annual $penalty_interest)
  CASE
    WHEN inv.erp_date_paid IS NOT NULL
    AND inv.erp_date_paid > inv.access_point_received_date + INTERVAL '5 days' THEN ROUND(
      (
        inv.total_invoice_amount * ($penalty_interest) / 365 * (
          DATE_PART(
            'day',
            inv.erp_date_paid - inv.access_point_received_date
          ) - 5
        )
      )::numeric,
      2
    )
    WHEN inv.erp_date_paid IS NULL
    AND CURRENT_DATE > inv.access_point_received_date + INTERVAL '5 days' THEN ROUND(
      (
        inv.total_invoice_amount * ($penalty_interest) / 365 * (
          DATE_PART(
            'day',
            CURRENT_DATE - inv.access_point_received_date
          ) - 5
        )
      )::numeric,
      2
    )
    ELSE NULL
  END AS "Estimated Penalty Amount (AUD)",

  inv.access_point_received_date AT TIME ZONE 'Australia/ACT' AS "Invoice Received Date",
  inv.payment_due_date AS "Payment Due Date",
  inv.erp_date_paid AS "Paid Date",
  inv.amount_without_tax AS "Amount Without Tax",
  inv.total_invoice_amount AS "Total Invoice Amount",
  inv.currency_code AS "Currency",
  inv.paid_status AS "Paid Status",
  sbd.created_date_time AT TIME ZONE 'Australia/ACT' AS "SBD Created Date"

FROM as4_incoming_sbd sbd
LEFT JOIN as4_documents_logs recv ON recv.doc_id = sbd.document_id
LEFT JOIN as4_message_delivery del ON del.document_id = sbd.id
LEFT JOIN invoice inv ON inv.id = sbd.attached_invoice_id

WHERE
  sbd.legal_entity_id = $company_le_id
  AND inv.paid_status IS NOT NULL
  AND inv.payment_due_date IS NOT NULL
  AND inv.access_point_received_date IS NOT NULL

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

ORDER BY "Invoice Received Date" DESC;
