


--count query
/* SUMMARY: Upcoming & Delayed Payments – invoice count per bucket */
WITH base AS (
    SELECT
        inv.id,
        inv.payment_due_date,
        inv.paid_status,
        inv.access_point_received_date,
        inv.total_invoice_amount,           -- kept for symmetry
        sbd.sender_value,
        COALESCE(
            sbd.offset_date_time AT TIME ZONE 'Australia/ACT',
            sbd.created_date_time AT TIME ZONE 'Australia/ACT'
        ) AS doc_ts
    FROM as4_incoming_sbd sbd
    LEFT JOIN invoice     inv ON inv.id = sbd.attached_invoice_id
    WHERE sbd.legal_entity_id           = $company_le_id
      AND inv.paid_status               IS NOT NULL
      AND inv.payment_due_date          IS NOT NULL
      AND inv.access_point_received_date IS NOT NULL
      AND (
           (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
        OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value               IN ($vendor_abn))
      )
      AND (
           inv.document_type IS NULL
        OR inv.document_type IN ($document_type_filter)
      )
)

SELECT
    CASE
        WHEN payment_due_date < CURRENT_DATE - INTERVAL '5 days'
             AND paid_status <> 'Paid' THEN 'Overdue > 5 days'
        WHEN payment_due_date < CURRENT_DATE
             AND paid_status <> 'Paid' THEN 'Overdue'
        ELSE 'Upcoming / Paid'
    END                          AS "Payment Status Category",
    COUNT(*)                     AS "Invoice Count"
FROM   base
WHERE  doc_ts >= $__timeFrom()::timestamptz
  AND  doc_ts <  $__timeTo()::timestamptz
GROUP  BY 1
ORDER  BY 1;





--Drill down query

/* DRILL-DOWN: Invoice-level detail */
WITH base AS (
    SELECT
        inv.id,
        inv.invoice_number,
        inv.invoice_external_id,
        inv.payment_due_date,
        inv.paid_status,
        inv.access_point_received_date,
        inv.total_invoice_amount,
        inv.erp_date_paid,
        inv.currency_code,
        inv.amount_without_tax,
        sbd.sender_value,
        sbd.created_date_time AT TIME ZONE 'Australia/ACT'  AS sbd_created_date,
        COALESCE(
            sbd.offset_date_time AT TIME ZONE 'Australia/ACT',
            sbd.created_date_time AT TIME ZONE 'Australia/ACT'
        ) AS doc_ts
    FROM as4_incoming_sbd sbd
    LEFT JOIN invoice     inv ON inv.id = sbd.attached_invoice_id
    WHERE sbd.legal_entity_id           = $company_le_id
      AND inv.paid_status               IS NOT NULL
      AND inv.payment_due_date          IS NOT NULL
      AND inv.access_point_received_date IS NOT NULL
      AND (
           (sbd.sender_value LIKE '%:%' AND split_part(sbd.sender_value, ':', 2) IN ($vendor_abn))
        OR (sbd.sender_value NOT LIKE '%:%' AND sbd.sender_value               IN ($vendor_abn))
      )
      AND (
           inv.document_type IS NULL
        OR inv.document_type IN ($document_type_filter)
      )
)

SELECT
    /* bucket */
    CASE
        WHEN payment_due_date < CURRENT_DATE - INTERVAL '5 days'
             AND paid_status <> 'Paid' THEN 'Overdue > 5 days'
        WHEN payment_due_date < CURRENT_DATE
             AND paid_status <> 'Paid' THEN 'Overdue'
        ELSE 'Upcoming / Paid'
    END                                                       AS "Payment Status Category",

    /* Vendor Tax-ID */
    CASE
        WHEN sender_value LIKE '%:%' THEN split_part(sender_value, ':', 2)
        ELSE sender_value
    END                                                       AS "Tax ID",

    invoice_number                                            AS "Invoice Number",
    invoice_external_id                                       AS "Invoice External ID",

    /* Days late */
    CASE
        WHEN erp_date_paid IS NOT NULL
             AND erp_date_paid > access_point_received_date + INTERVAL '5 days'
        THEN DATE_PART('day', erp_date_paid - access_point_received_date) - 5
        WHEN erp_date_paid IS NULL
             AND CURRENT_DATE   > access_point_received_date + INTERVAL '5 days'
        THEN DATE_PART('day', CURRENT_DATE - access_point_received_date) - 5
        ELSE NULL
    END                                                       AS "Delay (days)",

    /* Penalty – numeric before ROUND() */
    CASE
        WHEN erp_date_paid IS NOT NULL
             AND erp_date_paid > access_point_received_date + INTERVAL '5 days'
        THEN ROUND(
               (
                 total_invoice_amount::numeric
                 * ($penalty_interest)::numeric / 365
                 * (DATE_PART('day', erp_date_paid - access_point_received_date) - 5)::numeric
               ), 2
             )

        WHEN erp_date_paid IS NULL
             AND CURRENT_DATE   > access_point_received_date + INTERVAL '5 days'
        THEN ROUND(
               (
                 total_invoice_amount::numeric
                 * ($penalty_interest)::numeric / 365
                 * (DATE_PART('day', CURRENT_DATE - access_point_received_date) - 5)::numeric
               ), 2
             )

        ELSE NULL
    END                                                       AS "Estimated Penalty Amount (AUD)",

    access_point_received_date AT TIME ZONE 'Australia/ACT'   AS "Invoice Received Date",
    payment_due_date                                           AS "Payment Due Date",
    erp_date_paid                                              AS "Paid Date",
    amount_without_tax                                         AS "Amount Without Tax",
    total_invoice_amount                                       AS "Total Invoice Amount",
    currency_code                                              AS "Currency",
    paid_status                                                AS "Paid Status",
    sbd_created_date                                           AS "SBD Created Date"

FROM   base
WHERE  doc_ts >= $__timeFrom()::timestamptz
  AND  doc_ts <  $__timeTo()::timestamptz
ORDER  BY "Invoice Received Date" DESC;
