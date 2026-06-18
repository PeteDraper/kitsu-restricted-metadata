from . import resources

routes = [
    ("/health", resources.HealthResource),

    ("/context", resources.ProjectContextResource),
    ("/episodes", resources.EpisodesResource),
    ("/sequences", resources.SequencesResource),
    ("/shots", resources.ShotsResource),
    ("/assets", resources.AssetsResource),
    ("/asset-types", resources.AssetTypesResource),

    ("/fields", resources.FieldsResource),
    ("/fields/<field_id>", resources.FieldResource),

    ("/values", resources.ValuesResource),

    ("/bulk-set", resources.BulkSetResource),

    ("/export/json", resources.ExportJsonResource),
    ("/export/csv", resources.ExportCsvResource),
]
