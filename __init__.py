from . import resources

routes = [
    ("/health", resources.HealthResource),
    ("/fields", resources.FieldsResource),
    ("/fields/<field_id>", resources.FieldResource),
    ("/values", resources.ValuesResource),
    ("/bulk-set", resources.BulkSetResource),
]
