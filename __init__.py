from . import resources

routes = [
    ("/health", resources.HealthResource),
]
