


--Count Query

SELECT
    COUNT(DISTINCT rp.id) AS abn_not_active_count
FROM public.res_partner rp
JOIN public.res_partner_res_partner_category_rel rel ON rel.partner_id = rp.id
JOIN public.res_partner_category tag ON tag.id = rel.category_id
WHERE COALESCE(tag.name ->> 'en_US', tag.name ->> 'en_AU') = 'ABN Not Active' and rp.company_id = $enigma_company_id and rp.sanitized_vat IN ($vendor_abn)
  AND rp.name IN ($vendor);



--Drill Down

SELECT
    rp.name                                   AS "Vendor",
    rp.vat                                    AS "Tax ID",
    rp.email                                  AS "Email",
    rp.phone                                  AS "Phone",
    COALESCE(tag.name ->> 'en_US',
             tag.name ->> 'en_AU')            AS "Tag",

    /* Country name (fallback to multiple locales if stored as JSONB) */
    COALESCE(rc.name ->> 'en_US',
             rc.name ->> 'en_AU',
             rc.name ->> 'en_GB',
             rc.name ->> 'en')                AS "Country"

FROM   public.res_partner                         rp
JOIN   public.res_partner_res_partner_category_rel rel
       ON rel.partner_id = rp.id
JOIN   public.res_partner_category                tag
       ON tag.id = rel.category_id
LEFT  JOIN public.res_country                     rc
       ON rc.id = rp.country_id

WHERE  COALESCE(tag.name ->> 'en_US', tag.name ->> 'en_AU') = 'ABN Not Active'
  AND  rp.company_id   = $enigma_company_id
  AND  rp.sanitized_vat IN ($vendor_abn)

ORDER  BY rp.name, "Tag";
