"""Validación/saneamiento del archivo de proyecto (seguridad e integridad de datos)."""
import copy
import json
import pathlib

import pytest

from proyecto import ErrorProyecto, validar_campo_diseno, validar_proyecto

DEMO = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "demo.json").read_text(encoding="utf8"))


def test_demo_es_valido():
    out = validar_proyecto(DEMO)
    assert len(out["equipos"]) == 3
    assert sum(len(e["cmls"]) for e in out["equipos"]) == 10


def test_rechaza_no_proyecto():
    with pytest.raises(ErrorProyecto):
        validar_proyecto({"hola": 1})
    with pytest.raises(ErrorProyecto):
        validar_proyecto([1, 2])


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://malo.example/x.png", "data:text/html;base64,PHNjcmlwdD4="])
def test_rechaza_imagen_insegura(url):
    d = copy.deepcopy(DEMO)
    d["equipos"][0]["imagen"] = url
    with pytest.raises(ErrorProyecto, match="imagen"):
        validar_proyecto(d)


def test_rechaza_adjunto_no_pdf():
    d = copy.deepcopy(DEMO)
    d["equipos"][0]["adjuntos"] = [{"nombre": "x", "url": "javascript:alert(1)"}]
    with pytest.raises(ErrorProyecto, match="adjunto"):
        validar_proyecto(d)


def test_sanea_coordenadas_y_textos():
    d = copy.deepcopy(DEMO)
    c = d["equipos"][0]["cmls"][0]
    c["x"], c["y"] = "50%;background:url(x)", 250
    d["equipos"][0]["descripcion"] = "x" * 1000
    out = validar_proyecto(d)
    c2 = out["equipos"][0]["cmls"][0]
    assert c2["x"] == 50.0 and c2["y"] == 100.0
    assert len(out["equipos"][0]["descripcion"]) == 200


def test_rechaza_valores_fisicos_absurdos():
    d = copy.deepcopy(DEMO)
    d["equipos"][1]["diseno"]["E"] = 1.5
    d["equipos"][1]["cmls"][0]["mediciones"][0]["espesor_mm"] = -3
    with pytest.raises(ErrorProyecto) as e:
        validar_proyecto(d)
    assert len(e.value.errores) == 2


def test_rechaza_material_de_otra_familia_e_ids_duplicados():
    d = copy.deepcopy(DEMO)
    d["equipos"][1]["material"] = "A106-B"
    d["equipos"][2]["id"] = d["equipos"][0]["id"]
    with pytest.raises(ErrorProyecto) as e:
        validar_proyecto(d)
    assert any("familia" in x for x in e.value.errores) and any("duplicado" in x for x in e.value.errores)


def test_rbi_saneado():
    d = copy.deepcopy(DEMO)
    d["equipos"][1]["rbi"]["inspecciones"]["B"] = 999
    d["equipos"][1]["rbi"]["cml"] = "NO-EXISTE"
    r = validar_proyecto(d)["equipos"][1]["rbi"]
    assert r["inspecciones"]["B"] == 20 and r["cml"] in {c["id"] for c in d["equipos"][1]["cmls"]}


@pytest.mark.parametrize("campo,valor,ok", [("P_diseno_MPa", "1,5", True), ("P_diseno_MPa", 0, False),
                                            ("E", 1.0, True), ("E", 0, False), ("H_m", 0.3, False),
                                            ("T_diseno_C", "abc", False), ("CA_mm", 0, True)])
def test_validar_campo_diseno(campo, valor, ok):
    x, msg = validar_campo_diseno(campo, valor)
    assert (msg is None) == ok


def test_fecha_evaluacion_saneada():
    d = copy.deepcopy(DEMO)
    assert validar_proyecto(d)["fecha_evaluacion"] == "2026-11-26"
    d["fecha_evaluacion"] = "<script>"
    assert validar_proyecto(d)["fecha_evaluacion"] == ""
    del d["fecha_evaluacion"]
    assert validar_proyecto(d)["fecha_evaluacion"] == ""
