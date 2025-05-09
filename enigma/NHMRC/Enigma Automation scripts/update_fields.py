# Available variables:
#  - env: enigma7 environment
#  - model: Model object
#  - record: current record
#  - records: recordset of all records (in multi-mode)
#  - time, datetime, dateutil, timezone: Python standard libraries
#  - float_compare: float comparison utility
#  - b64encode, b64decode: base64 helpers
#  - log: log(message, level='info') to record debug info
#  - _logger: use for server-side logs
#  - UserError: to raise user-facing errors
#  - Command: x2many command helper
# To return an action, assign: action = {...}
for record in records:
    if not record.order_number and record.reference:
        record.write({"order_number":record.reference,"type_of_match":"contract"})



