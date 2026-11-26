"""Comparación independiente: resultados esperados calculados a mano (ver docs/validacion.md)."""
from datetime import date
import pytest
from calc import espesores as es, corrosion as co, inspeccion as ins, rbi
from calc.materiales import esfuerzo_admisible, KSI

IN = 25.4
PSI = 0.006894757


# ---------- Ejercicio del profesor (ppt 05, lámina 15): 8" A53 B, 200 °F, 150 psig ----------
def test_b313_ejercicio_profesor():
    S = esfuerzo_admisible("A53-B", (200 - 32) * 5 / 9)
    assert S == pytest.approx(20.0 * KSI)
    r = es.tuberia_b313(150 * PSI, 8.625 * IN, S)
    # a mano: 150·8,625 / [2(20000 + 0,4·150)] = 0,03225 in
    assert r["valor"] / IN == pytest.approx(0.03225, rel=1e-3)


MED_PROF = [
    {"fecha": "2009-01-01", "espesor_mm": 0.318 * IN},
    {"fecha": "2010-01-01", "espesor_mm": 0.302 * IN},
    {"fecha": "2015-01-01", "espesor_mm": 0.255 * IN},
    {"fecha": "2020-01-01", "espesor_mm": 0.200 * IN},
]


def test_corrosion_ejercicio_profesor():
    v = co.velocidades(MED_PROF)
    assert v["cr_lp"] / IN == pytest.approx(0.118 / 11, rel=2e-3)   # 0,01073 in/año
    assert v["cr_cp"] / IN == pytest.approx(0.055 / 5, rel=2e-3)    # 0,0110 in/año
    assert v["cr"] == v["cr_cp"]


def test_intervalo_api570_clase1():
    # RL = (0,200 − 0,03225)/0,011 = 15,25 años → RL/2 = 7,6 > 5 (Clase 1, HF) → 5 años
    rl = co.vida_remanente(0.200 * IN, 0.03225 * IN, 0.011 * IN)
    assert rl == pytest.approx(15.25, rel=2e-3)
    iv, crit, _ = ins.intervalo("tuberia", rl, clase=1)
    assert iv == 5 and "Clase 1" in crit


# ---------- Recipiente: UG-27 ----------
def test_ug27():
    # P = 1,5 MPa, R = 750 mm, S = 137,9, E = 0,85 → 1,5·750/(137,9·0,85 − 0,9) = 9,673 mm
    r = es.recipiente_ug27(1.5, 750, 137.9, 0.85)
    assert r["valor"] == pytest.approx(1125 / (117.215 - 0.9), rel=1e-6)
    assert r["valor"] == pytest.approx(9.672, abs=1e-3)


# ---------- Tanque: API 650 / 653 ----------
def test_api650_y_653():
    # D = 20 m, H = 12 m, G = 0,9, A283 C
    d = es.tanque_api650_diseno(20, 12, 0.9, 137, CA=1.5)
    assert d["valor"] == pytest.approx(4.9 * 20 * 11.7 * 0.9 / 137 + 1.5)       # 9,032 mm
    t = es.tanque_api653_tmin(20, 12, 0.9, 205, 380, virola=1)
    assert t["S"] == pytest.approx(min(164, 163.02))                           # 163,02 MPa
    assert t["valor"] == pytest.approx(1031.94 / 163.02, rel=1e-4)             # 6,330 mm
    t3 = es.tanque_api653_tmin(20, 4, 0.9, 205, 380, virola=3)
    assert t3["S"] == pytest.approx(min(180.4, 179.36))
    assert es.tanque_api653_tmin(20, 0.5, 0.9, 205, 380, virola=5)["valor"] == 2.54   # mínimo absoluto


# ---------- Validaciones de datos ----------
def test_info_insuficiente():
    v = co.velocidades([{"fecha": "2020-01-01", "espesor_mm": 10}])
    assert v["cr"] is None and any("insuficiente" in p for p in v["problemas"])


def test_cr_negativa():
    v = co.velocidades([{"fecha": "2020-01-01", "espesor_mm": 10}, {"fecha": "2022-01-01", "espesor_mm": 10.2}])
    assert v["cr"] == 0 and any("negativa" in p for p in v["problemas"])


def test_fechas_duplicadas():
    v = co.velocidades([{"fecha": "2020-01-01", "espesor_mm": 10}, {"fecha": "2020-01-01", "espesor_mm": 9.9}])
    assert any("inconsistentes" in p or "duplicadas" in p for p in v["problemas"])


def test_reemplazo_reinicia_serie():
    ms = [{"fecha": "2015-01-01", "espesor_mm": 12}, {"fecha": "2018-01-01", "espesor_mm": 9},
          {"fecha": "2019-01-01", "espesor_mm": 12.7, "evento": "reemplazo"},
          {"fecha": "2023-01-01", "espesor_mm": 12.3}]
    v = co.velocidades(ms)
    assert v["n"] == 2 and v["cr_lp"] == pytest.approx(0.4 / co.anios("2019-01-01", "2023-01-01"))


def test_intervalos_api510_653():
    assert ins.intervalo("recipiente", 30)[0] == 10
    assert ins.intervalo("recipiente", 12)[0] == 6
    assert ins.intervalo("recipiente", 3)[0] == 2
    assert ins.intervalo("tanque", 40)[0] == 15
    assert ins.intervalo("tanque", None, cr_conocida=False)[0] == 5


def test_condiciones():
    eq = {"familia": "recipiente", "material": "SA-516-70",
          "diseno": {"P_diseno_MPa": 1.5, "D_int_mm": 1500, "T_diseno_C": 150, "E": 0.85}}   # t_min ≈ 9,67
    hoy = date(2026, 11, 24)
    def cml(t2, f2="2025-06-01"):
        return {"mediciones": [{"fecha": "2015-06-01", "espesor_mm": 14.0}, {"fecha": f2, "espesor_mm": t2}]}
    assert ins.evaluar_cml(eq, cml(13.5), hoy)["condicion"] == "normal"
    assert ins.evaluar_cml(eq, cml(10.1, "2026-09-01"), hoy)["condicion"] == "alerta"
    assert ins.evaluar_cml(eq, cml(9.5), hoy)["condicion"] == "bajo_minimo"
    assert ins.evaluar_cml(eq, cml(13.5, "2016-06-01"), hoy)["condicion"] == "vencida"
    assert ins.evaluar_cml(eq, {"mediciones": []}, hoy)["condicion"] == "insuficiente"


# ---------- RBI ----------
def test_rbi_sin_daño_df_bajo():
    # Art = 0 → β1 = (1 − SRp)/√(COV_Sf² + SRp²·COV_P²)
    YS, TS = 38 * KSI, 70 * KSI
    r = rbi.df_adelgazamiento(cr=0, edad=10, t_rdi=20, t_min=10, S=137.9, E=1, YS=YS, TS=TS)
    fs = (YS + TS) / 2 * 1.1
    srp = 137.9 * 10 / (fs * 20)
    beta = (1 - srp) / (0.04 + srp ** 2 * 0.0025) ** 0.5
    assert r["pasos"]["beta"][0] == pytest.approx(beta)
    assert r["Df"] == pytest.approx(max(rbi.phi(-beta) / 1.56e-4, 0.1))


def test_rbi_bayes_y_efecto_inspeccion():
    base = dict(cr=0.3, edad=12, t_rdi=14, t_min=9.67, S=137.9, E=0.85, YS=38 * KSI, TS=70 * KSI)
    sin = rbi.df_adelgazamiento(**base)
    con = rbi.df_adelgazamiento(**base, inspecciones={"B": 2})
    # Bayes a mano para 2B, prior baja: I = (0,5·0,7², 0,3·0,2², 0,2·0,1²) = (0,245, 0,012, 0,002)
    assert con["pasos"]["Po"][0] == pytest.approx(0.245 / 0.259)
    assert con["Df"] < sin["Df"]   # la inspección reduce incertidumbre → menor DF


def test_phi():
    assert rbi.phi(-2) == pytest.approx(0.0227501, rel=1e-5)


def test_riesgo_y_matriz():
    r = rbi.riesgo(df=50, C_A_m2=200, C_E=250_000)
    assert r["Pf"] == pytest.approx(3.06e-5 * 50)
    assert r["R_A"] == pytest.approx(3.06e-5 * 50 * 200)
    assert (r["cat_pof"], r["cat_area"], r["cat_fin"]) == ("3", "C", "C")
    assert rbi.f_ms(50) == pytest.approx(1.0)


# ---------- Correcciones de la revisión técnica ----------
def test_ug27_gobierna_mayor_y_longitudinal():
    r = es.recipiente_ug27(1.5, 750, 137.9, 0.85)
    assert r["t_circ"] > r["t_long"] and r["valor"] == r["t_circ"]
    assert r["t_long"] == pytest.approx(1.5 * 750 / (2 * 137.9 * 0.85 + 0.6))


def test_api650_tt_y_minimo_nominal():
    r = es.tanque_api650_diseno(20, 12, 0.85, 137, 1.5, St=154)
    assert r["tt"] == pytest.approx(4.9 * 20 * 11.7 / 154)
    assert r["valor"] == pytest.approx(r["td"]) and "td" in r["gobierna"]
    # tanque chico y bajo: gobierna el mínimo nominal (D < 15 m → 5 mm)
    assert es.tanque_api650_diseno(10, 2, 0.85, 137, 0, St=154)["valor"] == 5.0
    # agua (G = 1) con Sd alto: puede gobernar tt
    assert "tt" in es.tanque_api650_diseno(30, 15, 0.7, 160, 0, St=171)["gobierna"]


def test_una_medicion_bajo_minimo_no_es_insuficiente():
    eq = {"familia": "recipiente", "material": "SA-516-70",
          "diseno": {"P_diseno_MPa": 1.5, "D_int_mm": 1500, "T_diseno_C": 150, "E": 0.85}}
    r = ins.evaluar_cml(eq, {"mediciones": [{"fecha": "2025-01-01", "espesor_mm": 9.0}]}, date(2026, 11, 24))
    assert r["condicion"] == "bajo_minimo"


def test_cr_cero_aplica_intervalo_maximo():
    eq = {"familia": "recipiente", "material": "SA-516-70",
          "diseno": {"P_diseno_MPa": 1.5, "D_int_mm": 1500, "T_diseno_C": 150, "E": 0.85}}
    ms = [{"fecha": "2020-01-01", "espesor_mm": 14.0}, {"fecha": "2025-01-01", "espesor_mm": 14.0}]
    r = ins.evaluar_cml(eq, {"mediciones": ms}, date(2026, 11, 24))
    assert r["intervalo"] == 10 and r["proxima"] == "2035-01-01" and r["condicion"] == "normal"
    assert ins.intervalo("tanque", None, cr_conocida=True)[0] == 15
    assert ins.intervalo("recipiente", None, cr_conocida=False)[0] is None


def test_ug27_presion_excesiva():
    with pytest.raises(ValueError):
        es.recipiente_ug27(200, 750, 137.9, 0.85)


# ---------- Fecha de evaluación global (evaluación «al día») ----------
def test_evaluacion_al_dia_ignora_mediciones_posteriores():
    import json
    import pathlib
    demo = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "demo.json").read_text(encoding="utf8"))
    v201 = demo["equipos"][1]
    c = next(c for c in v201["cmls"] if c["id"] == "CML-201-03")
    hoy = ins.evaluar_cml(v201, c, date(2026, 11, 26))
    antes = ins.evaluar_cml(v201, c, date(2023, 1, 1))   # antes de la lectura de 2025 (9,50 mm)
    assert hoy["condicion"] == "bajo_minimo"
    assert antes["corrosion"]["t_actual"] == pytest.approx(11.40)
    assert antes["condicion"] != "bajo_minimo"
    assert any("posterior" in p for p in antes["corrosion"]["problemas"])


# ---------- RBI del caso demo: V-201 / CML-201-03 al 26-11-2026 ----------
def test_rbi_cml_201_03():
    # Esperado: cálculo independiente (API 581 Parte 2 ec. 2.12–2.20 con math.erf), ver Validación
    v = co.velocidades([{"fecha": "2016-05-01", "espesor_mm": 16.0}, {"fecha": "2019-05-20", "espesor_mm": 13.5},
                        {"fecha": "2022-05-18", "espesor_mm": 11.4}, {"fecha": "2025-05-21", "espesor_mm": 9.5}])
    assert v["cr_lp"] == pytest.approx(0.7179, rel=1e-4)
    r = rbi.df_adelgazamiento(cr=v["cr_lp"], edad=co.anios("2016-05-01", "2026-11-26"), t_rdi=16,
                              t_min=es.recipiente_ug27(1.5, 750, 20 * KSI, 0.85)["valor"], S=20 * KSI, E=0.85,
                              YS=38 * KSI, TS=70 * KSI, confianza="media", inspecciones={"B": 2})
    assert r["Df"] == pytest.approx(205.5932, rel=1e-4)
    rr = rbi.riesgo(r["Df"], 120, 20_000_000)
    assert rr["R_E"] == pytest.approx(125823.05, rel=1e-4)
