from . import resources

routes = [
    ("/health", resources.HealthResource),

    ("/context", resources.ProjectContextResource),

    ("/columns", resources.ColumnsResource),
    ("/columns/<column_id>", resources.ColumnResource),

    ("/groups/episodes", resources.EpisodeGroupsResource),
    ("/groups/sequences", resources.SequenceGroupsResource),
    ("/groups/asset-types", resources.AssetTypeGroupsResource),

    ("/rows/episodes", resources.EpisodeRowsResource),
    ("/rows/sequences", resources.SequenceRowsResource),
    ("/rows/shots", resources.ShotRowsResource),
    ("/rows/assets", resources.AssetRowsResource),

    ("/cell", resources.CellResource),
    ("/bulk-set", resources.BulkSetResource),

    ("/asset-types", resources.AssetTypesResource),

    ("/export/json", resources.ExportJsonResource),
    ("/export/csv", resources.ExportCsvResource),
]
