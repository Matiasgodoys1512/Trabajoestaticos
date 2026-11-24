"""Genera data/demo.json: caso demostrativo con datos ficticios (3 familias, 3+ CML, 3 campañas)."""
import json

IN = 25.4


def med(fecha, t, tecnica="UT haz recto", obs="", evento=None, unidad="mm"):
    m = {"fecha": fecha, "espesor_mm": round(t, 3), "unidad": unidad, "tecnica": tecnica, "observaciones": obs}
    if evento:
        m["evento"] = evento
    return m


tuberia = {
    "id": "L-101", "tag": "8\"-HF-101", "familia": "tuberia",
    "descripcion": "Línea de descarga P-101 a separador V-201",
    "servicio": "Ácido fluorhídrico (unidad de alquilación)", "fluido": "HF / hidrocarburo",
    "ubicacion": {"planta": "Refinería Demo", "area": "Área 100 - Alquilación", "sistema": "Sistema HF"},
    "circuito": "CI-HF-01", "clase": 1, "material": "A106-B",
    "codigo_diseno": "ASME B31.3-2018", "codigo_servicio": "API 570",
    "t_nom_mm": 8.18, "fecha_servicio": "2009-06-01",
    "diseno": {"P_diseno_MPa": 1.03, "T_diseno_C": 93, "D_ext_mm": 219.1, "E": 1.0, "W": 1.0, "Y": 0.4,
               "CA_mm": 1.5, "tol_fab": 0.125, "t_estructural_mm": 2.8},
    "operacion": {"P_MPa": 0.9, "T_C": 80},
    "imagen": "data/img/tuberia_L101.png", "adjuntos": [],
    "cmls": [
        {"id": "CML-101-01", "componente": "Tramo recto descarga bomba", "ubicacion": "Aguas abajo brida P-101, 0°",
         "x": 19, "y": 70, "t_nom_mm": 8.18,
         "mediciones": [med("2019-03-15", 8.05), med("2022-03-10", 7.90), med("2025-03-12", 7.76)]},
        {"id": "CML-101-02", "componente": "Tramo recto horizontal superior", "ubicacion": "Rack, 6 h (fondo)",
         "x": 40, "y": 35, "t_nom_mm": 8.18,
         "mediciones": [med("2021-10-20", 7.00), med("2023-10-18", 5.60), med("2025-10-20", 3.90, obs="Pérdida localizada en fondo")]},
        {"id": "CML-101-03", "componente": "Tramo recto vertical", "ubicacion": "Bajada a V-201, 3 h",
         "x": 75, "y": 48, "t_nom_mm": 8.18,
         "mediciones": [med("2019-03-15", 6.20), med("2022-03-10", 5.10),
                        med("2024-06-05", 8.20, obs="Spool reemplazado (OT 24-118)", evento="reemplazo")]},
        {"id": "CML-101-04", "componente": "Tramo recto horizontal superior", "ubicacion": "Caso ejercicio clase 05 (UT en pulgadas)",
         "x": 63, "y": 35, "t_nom_mm": 8.18,
         "mediciones": [med("2009-06-01", 0.318 * IN, unidad="in"), med("2010-06-01", 0.302 * IN, unidad="in"),
                        med("2015-06-01", 0.255 * IN, unidad="in"), med("2020-06-01", 0.200 * IN, unidad="in")]},
    ],
}

recipiente = {
    "id": "V-201", "tag": "V-201", "familia": "recipiente",
    "descripcion": "Separador vertical de HF", "servicio": "Separación HF / hidrocarburo", "fluido": "HF / hidrocarburo",
    "ubicacion": {"planta": "Refinería Demo", "area": "Área 100 - Alquilación", "sistema": "Sistema HF"},
    "circuito": "", "clase": None, "material": "SA-516-70",
    "codigo_diseno": "ASME BPVC VIII-1 2019", "codigo_servicio": "API 510",
    "t_nom_mm": 16.0, "fecha_servicio": "2016-05-01",
    "diseno": {"P_diseno_MPa": 1.5, "T_diseno_C": 150, "D_int_mm": 1500, "E": 0.85, "CA_mm": 3.0},
    "operacion": {"P_MPa": 1.2, "T_C": 120},
    "imagen": "data/img/recipiente_V201.png", "adjuntos": [],
    "cmls": [
        {"id": "CML-201-01", "componente": "Envolvente - virola 1", "ubicacion": "Virola superior, 0°",
         "x": 50, "y": 24, "t_nom_mm": 16.0,
         "mediciones": [med("2016-05-01", 16.0, obs="Línea base fabricación"), med("2019-05-20", 15.6), med("2022-05-18", 15.3), med("2025-05-21", 15.0)]},
        {"id": "CML-201-02", "componente": "Envolvente - virola 2", "ubicacion": "Virola media, 90°",
         "x": 50, "y": 45, "t_nom_mm": 16.0,
         "mediciones": [med("2016-05-01", 16.0, obs="Línea base fabricación"), med("2019-05-20", 15.0), med("2022-05-18", 14.1), med("2025-05-21", 13.0)]},
        {"id": "CML-201-03", "componente": "Envolvente - virola 3", "ubicacion": "Virola inferior, zona interfase, 180°",
         "x": 50, "y": 66, "t_nom_mm": 16.0,
         "mediciones": [med("2016-05-01", 16.0, obs="Línea base fabricación"), med("2019-05-20", 13.5), med("2022-05-18", 11.4), med("2025-05-21", 9.5, obs="Requiere evaluación FFS (API 579)")]},
    ],
    "rbi": {"cml": "CML-201-02", "confianza": "media", "inspecciones": {"A": 0, "B": 2, "C": 0, "D": 0, "E": 0},
            "pscore": 50, "f_om": 1.0, "C_A_m2": 120.0, "C_E": 450000.0, "moneda": "USD",
            "base_valoracion": "Reparación + producción diferida, USD 2026",
            "escenario": "Fuga por adelgazamiento generalizado de la envolvente; consecuencia ponderada por tamaño de agujero"},
}

tanque = {
    "id": "TK-301", "tag": "TK-301", "familia": "tanque",
    "descripcion": "Tanque de almacenamiento de diésel, techo cónico", "servicio": "Almacenamiento diésel", "fluido": "Diésel",
    "ubicacion": {"planta": "Refinería Demo", "area": "Área 300 - Almacenamiento", "sistema": "Patio de tanques"},
    "circuito": "", "clase": None, "material": "A283-C",
    "codigo_diseno": "API 650 12ª ed. 2013", "codigo_servicio": "API 653",
    "t_nom_mm": 10.0, "fecha_servicio": "2015-09-01",
    "diseno": {"D_m": 20.0, "H_m": 12.0, "G": 0.85, "E": 1.0, "CA_mm": 1.5, "virola": 1},
    "operacion": {"P_MPa": 0.0, "T_C": 30},
    "imagen": "data/img/tanque_TK301.png", "adjuntos": [],
    "cmls": [
        {"id": "CML-301-01", "componente": "Manto - virola 1", "ubicacion": "0,3 m sobre fondo, 0°",
         "x": 50, "y": 76, "t_nom_mm": 10.0, "diseno_local": {"virola": 1, "H_m": 12.0},
         "mediciones": [med("2015-09-01", 10.0, obs="Línea base"), med("2018-09-10", 9.6), med("2021-09-08", 9.0), med("2024-09-11", 8.1)]},
        {"id": "CML-301-02", "componente": "Manto - virola 2", "ubicacion": "0,3 m sobre soldadura V1-V2, 90°",
         "x": 50, "y": 64, "t_nom_mm": 8.0, "diseno_local": {"virola": 2, "H_m": 9.6},
         "mediciones": [med("2015-09-01", 8.0, obs="Línea base"), med("2018-09-10", 7.8), med("2021-09-08", 7.65), med("2024-09-11", 7.5)]},
        {"id": "CML-301-03", "componente": "Manto - virola 3", "ubicacion": "Punto nuevo 2024, 180°",
         "x": 50, "y": 52, "t_nom_mm": 6.0, "diseno_local": {"virola": 3, "H_m": 7.2},
         "mediciones": [med("2024-09-11", 5.85, obs="CML incorporado en 2024: sin historial")]},
    ],
}

demo = {"version": 1, "proyecto": "Caso demostrativo MAN040-B", "plazo_intervencion_anios": 2.0,
        "equipos": [tuberia, recipiente, tanque]}

with open("data/demo.json", "w", encoding="utf-8") as f:
    json.dump(demo, f, ensure_ascii=False, indent=1)
print("ok")
