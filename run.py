"""Punto de entrada de la aplicación RIASEC.

Permite ejecutar el proyecto tanto con:
    flask --app run.py run
como, para desarrollo local, con:
    python run.py
"""

from app import create_app


# Flask y servidores WSGI pueden importar directamente esta variable.
app = create_app()


if __name__ == "__main__":
    # app.run() se usa solo para desarrollo. En producción se utilizará un
    # servidor WSGI apropiado cuando lleguemos a la fase de despliegue.
    app.run()
