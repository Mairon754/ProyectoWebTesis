"""Extensiones de Flask inicializadas sin acoplarse a una app concreta.

FASE 1 — Arquitectura
---------------------
Se usa el patrón Application Factory. Por eso SQLAlchemy y Flask-Migrate se
crean aquí y se conectan a la aplicación dentro de `create_app()`.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


# SQLAlchemy será la única puerta de acceso ORM a PostgreSQL.
db = SQLAlchemy()

# Flask-Migrate/Alembic administrará la evolución controlada del esquema.
migrate = Migrate()
