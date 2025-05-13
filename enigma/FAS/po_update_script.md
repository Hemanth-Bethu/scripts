# Script yo update po custom_1 from vendor
```
for record in records:
    value = record.partner_id.custom_1 if record.partner_id else ''
    record.write({'custom_1': value})
```

# Validation script for  checking component parent child selection
```
lines = record.order_line

[//]: # (# Validate parent component links)
result = any(
    (line.component_1 != line.component_2.parent_id) 
    for line in lines
)
```