from alembic import context
from zou.app import db
from models import RestrictedMetadataField, RestrictedMetadataValue

config = context.config
target_metadata = db.metadata

def run_migrations_online():
    connectable = db.engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
