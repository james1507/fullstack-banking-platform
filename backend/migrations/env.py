from alembic import context

from app.db import engine


def run(connection):
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


if connection := context.config.attributes.get("connection"):
    run(connection)
else:
    with engine.connect() as connection:
        run(connection)
