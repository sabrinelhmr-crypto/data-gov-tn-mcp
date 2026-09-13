"""Tests unitaires pour l'outil download_and_parse_resource (C2)."""

import io
import json

from openpyxl import Workbook

from helpers.api_client import DatagovAPIError
from tools.download_and_parse_resource import (
    _detect_format,
    _human_size,
    download_and_parse_resource,
)


def _resource(**overrides):
    values = {
        "id": "res-1",
        "name": "Donnees 2024",
        "format": "CSV",
        "url": "https://example.org/file.csv",
        "size": 2048,
        "downloads_count": 42,
    }
    values.update(overrides)
    return values


def _payload(resource=None):
    return {"success": True, "result": resource if resource is not None else _resource()}


async def test_requete_vide(datagov):
    out = await download_and_parse_resource("  ")
    assert "Veuillez fournir un identifiant de ressource" in out


async def test_ressource_introuvable(datagov):
    async def handler(params):
        raise DatagovAPIError("Not found: res-inconnu")

    datagov.handler = handler
    out = await download_and_parse_resource("res-inconnu")
    assert "Ressource introuvable" in out


async def test_format_non_supporte(datagov):
    async def handler(params):
        return _payload(_resource(format="PDF", url="https://example.org/doc.pdf"))

    datagov.handler = handler
    out = await download_and_parse_resource("res-1")
    assert "format non supporte" in out
    assert "Formats acceptes" in out


async def test_taille_excessive_avant_telechargement(datagov):
    async def handler(params):
        return _payload(_resource(format="CSV", size=200 * 1024 * 1024))

    datagov.handler = handler
    out = await download_and_parse_resource("res-1")
    assert "trop volumineux" in out
    assert "100 Mo" in out


async def test_echec_telechargement(datagov):
    async def handler(params):
        return _payload(_resource(format="CSV"))

    async def download_handler(url):
        raise DatagovAPIError("HTTP 502")

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "Echec du telechargement" in out


async def test_taille_excessive_apres_telechargement(datagov):
    async def handler(params):
        return _payload(_resource(format="CSV", size=None))

    async def download_handler(url):
        return b"x" * (101 * 1024 * 1024)

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "trop volumineux au telechargement" in out


async def test_csv_analyse(datagov):
    captured_url = {}

    async def handler(params):
        return _payload(_resource(format="CSV"))

    async def download_handler(url):
        captured_url["url"] = url
        return b"Date,Miskar\n2010-01,127.62\n2010-02,100.5\n"

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")

    assert captured_url["url"] == "https://example.org/file.csv"
    assert "Ressource : Donnees 2024" in out
    assert "Format : CSV" in out
    assert "Taille : 2.0 Ko" in out
    assert "Lignes analysees : 2" in out
    assert "Schema (2 colonnes) :" in out
    assert "Statistiques descriptives :" in out
    assert "moyenne=" in out
    assert "5 premieres lignes :" in out
    assert "1. Date=2010-01 | Miskar=127.62" in out


async def test_csv_avec_limite(datagov):
    async def handler(params):
        return _payload(_resource(format="CSV"))

    rows = b"Date,Miskar\n" + b"".join(f"2010-0{i},10.5\n".encode() for i in range(1, 6))

    async def download_handler(url):
        return rows

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1", limit=2)
    assert "Lignes analysees : 2 (limite de 2)" in out


async def test_tsv_analyse(datagov):
    async def handler(params):
        return _payload(_resource(format="TSV", url="https://example.org/file.tsv"))

    async def download_handler(url):
        return b"Date\tMiskar\n2010-01\t127.62\n"

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "Format : TSV" in out
    assert "1. Date=2010-01 | Miskar=127.62" in out


async def test_json_analyse(datagov):
    async def handler(params):
        return _payload(_resource(format="JSON", url="https://example.org/data.json"))

    payload = json.dumps([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]).encode()

    async def download_handler(url):
        return payload

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "Format : JSON" in out
    assert "1. a=1 | b=x" in out
    assert "2. a=2 | b=y" in out


async def test_geojson_analyse(datagov):
    async def handler(params):
        return _payload(
            _resource(format="GeoJSON", url="https://example.org/map.geojson", size=None)
        )

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Tunis", "population": 2500000},
                "geometry": {"type": "Point", "coordinates": [10.17, 36.8]},
            }
        ],
    }

    async def download_handler(url):
        return json.dumps(geojson).encode()

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "Format : GEOJSON" in out
    assert "_geometry" in out


async def test_json_records_cle(datagov):
    async def handler(params):
        return _payload(_resource(format="JSON"))

    payload = json.dumps({"records": [{"c": 1}, {"c": 2}]}).encode()

    async def download_handler(url):
        return payload

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "1. c=1" in out
    assert "2. c=2" in out


async def test_json_non_tabulaire(datagov):
    async def handler(params):
        return _payload(_resource(format="JSON"))

    async def download_handler(url):
        return b'{"foo": {"nested": 1}}'

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "impossible d'analyser" in out


async def test_xlsx_analyse(datagov):
    wb = Workbook()
    ws = wb.active
    ws.append(["a", "b"])
    ws.append([1, 2])
    ws.append([3, 4])
    buffer = io.BytesIO()
    wb.save(buffer)

    async def handler(params):
        return _payload(_resource(format="XLSX", url="https://example.org/data.xlsx"))

    async def download_handler(url):
        return buffer.getvalue()

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "Format : XLSX" in out
    assert "Schema (2 colonnes) :" in out
    assert "1. a=1 | b=2" in out


async def test_fichier_vide(datagov):
    async def handler(params):
        return _payload(_resource(format="CSV"))

    async def download_handler(url):
        return b"Date,Miskar\n"

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "Aucune ligne a analyser." in out


def test_detect_format():
    assert _detect_format(_resource(format="CSV")) == "csv"
    assert _detect_format(_resource(format="xlsx", url="https://x/f.dat")) == "xlsx"
    assert _detect_format(_resource(format="", url="https://x/data.json?t=1")) == "json"
    assert _detect_format(_resource(format="application/geo+json")) == "geojson"
    assert _detect_format(_resource(format="", url="https://x/noext")) == ""


def test_human_size():
    assert _human_size(500) == "500 o"
    assert _human_size(2048) == "2.0 Ko"
    assert _human_size(None) is None
    assert _human_size("abc") is None


async def test_csv_encodage_latin1(datagov):
    async def handler(params):
        return _payload(_resource(format="CSV"))

    async def download_handler(url):
        return b"Date,Nom\n2010-01,aut\xe9\n"

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "1. Date=2010-01 | Nom=auté" in out


async def test_json_liste_vide(datagov):
    async def handler(params):
        return _payload(_resource(format="JSON"))

    async def download_handler(url):
        return b"[]"

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "impossible d'analyser" in out


async def test_json_cle_records_vide(datagov):
    async def handler(params):
        return _payload(_resource(format="JSON"))

    async def download_handler(url):
        return b'{"records": []}'

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "impossible d'analyser" in out


async def test_json_objet_scalaire(datagov):
    async def handler(params):
        return _payload(_resource(format="JSON"))

    async def download_handler(url):
        return b'{"a": 1, "b": "x"}'

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert "1. a=1 | b=x" in out


async def test_nom_long_tronque(datagov):
    long_name = "X" * 100

    async def handler(params):
        return _payload(_resource(name=long_name, format="CSV"))

    async def download_handler(url):
        return b"Date,Miskar\n2010-01,1\n"

    datagov.handler = handler
    datagov.download_handler = download_handler

    out = await download_and_parse_resource("res-1")
    assert long_name[:77] + "..." in out
