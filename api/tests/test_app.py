from fastapi.testclient import TestClient

from astrolabio_api.main import crear_app
from astrolabio_api.modelos import Galaxia


def test_galaxia_responde_con_el_contrato():
    respuesta = TestClient(crear_app(desarrollo=False)).get("/api/galaxia")
    assert respuesta.status_code == 200
    Galaxia.model_validate(respuesta.json())


def test_docs_apagadas_en_produccion():
    cliente = TestClient(crear_app(desarrollo=False))
    for ruta in ("/docs", "/redoc", "/openapi.json"):
        assert cliente.get(ruta).status_code == 404


def test_solo_lectura():
    app = crear_app(desarrollo=True)
    metodos = {m for ruta in app.routes for m in getattr(ruta, "methods", set())}
    assert metodos <= {"GET", "HEAD"}
