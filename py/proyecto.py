"""Validación y saneamiento del archivo de proyecto (JSON importado o recuperado del navegador).

Todo dato externo pasa por aquí antes de llegar al motor de cálculo o a la interfaz:
tipos, rangos físicos, fechas, referencias cruzadas y URLs de adjuntos (solo data: o rutas locales).
Python puro (stdlib) → se prueba con pytest.
"""
import re
from datetime import date

from calc.materiales import MATERIALES
from calc.rbi import COND, PRIOR

VERSION = 1
FAMILIAS = ("tuberia", "recipiente", "tanque")
EVENTOS = ("reemplazo", "reparacion", "cambio_punto")
UNIDADES = ("mm", "in")
MAX_EQUIPOS, MAX_CML, MAX_MED, MAX_ADJ = 200, 100, 200, 10

# Rangos físicos admisibles por campo de diseño: (mín, máx, incluye_mín)
RANGOS = {
    "P_diseno_MPa": (0.0, 50.0, False, "Presión de diseño [MPa]"),
    "T_diseno_C": (-29.0, 260.0, True, "Temperatura de diseño [°C]"),
    "D_ext_mm": (10.0, 3000.0, False, "Diámetro exterior [mm]"),
    "D_int_mm": (50.0, 10000.0, False, "Diámetro interior [mm]"),
    "E": (0.0, 1.0, False, "Eficiencia de junta E"),
    "W": (0.0, 1.0, False, "Factor W"),
    "Y": (0.0, 0.7, True, "Coeficiente Y"),
    "CA_mm": (0.0, 20.0, True, "Sobreespesor CA [mm]"),
    "tol_fab": (0.0, 0.3, True, "Tolerancia de fabricación"),
    "t_estructural_mm": (0.0, 50.0, True, "Espesor estructural [mm]"),
    "D_m": (1.0, 100.0, False, "Diámetro del tanque [m]"),
    "H_m": (0.3, 40.0, False, "Nivel de diseño H [m]"),
    "G": (0.3, 2.5, False, "Gravedad específica G"),
    "virola": (1.0, 20.0, True, "N° de virola"),
}
REQUERIDOS = {
    "tuberia": ("P_diseno_MPa", "T_diseno_C", "D_ext_mm", "E"),
    "recipiente": ("P_diseno_MPa", "T_diseno_C", "D_int_mm", "E"),
    "tanque": ("D_m", "H_m", "G"),
}
RE_IMG_LOCAL = re.compile(r"^data/img/[\w.-]+\.(png|jpe?g)$", re.I)
RE_IMG_DATA = re.compile(r"^data:image/(png|jpeg);base64,[A-Za-z0-9+/=\s]+$")
RE_PDF_DATA = re.compile(r"^data:application/pdf;base64,[A-Za-z0-9+/=\s]+$")


class ErrorProyecto(ValueError):
    """Error de validación con la lista de problemas encontrados."""

    def __init__(self, errores):
        self.errores = errores
        super().__init__("; ".join(errores[:5]) + (" …" if len(errores) > 5 else ""))


def texto(v, maximo=120):
    if v is None:
        return ""
    return str(v).strip()[:maximo]


def numero(v):
    if isinstance(v, bool) or v is None or v == "":
        return None
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def validar_campo_diseno(campo, valor):
    """Devuelve (valor_float, None) o (None, mensaje_de_error)."""
    x = numero(valor)
    if campo not in RANGOS:
        return (x, None) if x is not None else (None, f"{campo}: valor no numérico")
    lo, hi, incl, nombre = RANGOS[campo]
    if x is None:
        return None, f"{nombre}: valor no numérico"
    if x > hi or x < lo or (x == lo and not incl):
        signo = "≥" if incl else ">"
        return None, f"{nombre}: debe estar entre {signo} {lo:g} y ≤ {hi:g}"
    return x, None


def fecha_valida(v):
    try:
        f = date.fromisoformat(str(v)[:10])
    except ValueError:
        return None
    return f.isoformat() if 1950 <= f.year <= 2100 else None


def url_imagen(v):
    v = texto(v, 20_000_000)
    return v if (not v or RE_IMG_LOCAL.match(v) or RE_IMG_DATA.match(v)) else None


def validar_proyecto(data):
    """Valida y devuelve una copia saneada del proyecto. Lanza ErrorProyecto si hay errores bloqueantes."""
    err = []
    if not isinstance(data, dict) or not isinstance(data.get("equipos"), list):
        raise ErrorProyecto(["El archivo no es un proyecto válido (falta la lista 'equipos')"])
    if len(data["equipos"]) > MAX_EQUIPOS:
        raise ErrorProyecto([f"Demasiados equipos (máx. {MAX_EQUIPOS})"])
    plazo = numero(data.get("plazo_intervencion_anios"))
    out = {"version": VERSION, "proyecto": texto(data.get("proyecto"), 120) or "Proyecto",
           "plazo_intervencion_anios": plazo if plazo is not None and 0 < plazo <= 10 else 2.0, "equipos": []}
    ids = set()
    for i, eq in enumerate(data["equipos"]):
        pref = f"Equipo #{i + 1}"
        if not isinstance(eq, dict):
            err.append(f"{pref}: formato inválido")
            continue
        e = _equipo(eq, pref, err)
        if e is None:
            continue
        if e["id"] in ids:
            err.append(f"{pref}: ID duplicado '{e['id']}'")
        ids.add(e["id"])
        out["equipos"].append(e)
    if err:
        raise ErrorProyecto(err)
    return out


def _equipo(eq, pref, err):
    eid = texto(eq.get("id") or eq.get("tag"), 60)
    tag = texto(eq.get("tag") or eid, 60)
    if not eid:
        err.append(f"{pref}: falta ID/TAG")
        return None
    pref = f"{tag}"
    fam = eq.get("familia")
    if fam not in FAMILIAS:
        err.append(f"{pref}: familia desconocida '{texto(fam, 20)}'")
        return None
    mat = eq.get("material")
    if mat not in MATERIALES:
        err.append(f"{pref}: material no incluido en el catálogo '{texto(mat, 30)}'")
        return None
    if MATERIALES[mat]["familia"] != fam:
        err.append(f"{pref}: el material {mat} no corresponde a la familia {fam}")
    u = eq.get("ubicacion") if isinstance(eq.get("ubicacion"), dict) else {}
    op = eq.get("operacion") if isinstance(eq.get("operacion"), dict) else {}
    t_nom = numero(eq.get("t_nom_mm"))
    if t_nom is None or not 0 < t_nom <= 300:
        err.append(f"{pref}: espesor nominal inválido")
    clase = numero(eq.get("clase"))
    e = {
        "id": eid, "tag": tag, "familia": fam, "material": mat,
        "descripcion": texto(eq.get("descripcion"), 200), "servicio": texto(eq.get("servicio")),
        "fluido": texto(eq.get("fluido")), "circuito": texto(eq.get("circuito"), 60),
        "clase": int(clase) if clase in (1, 2, 3, 4) else (2 if fam == "tuberia" else None),
        "codigo_diseno": texto(eq.get("codigo_diseno"), 80), "codigo_servicio": texto(eq.get("codigo_servicio"), 80),
        "t_nom_mm": t_nom or 0.0, "fecha_servicio": fecha_valida(eq.get("fecha_servicio")) or "",
        "ubicacion": {"planta": texto(u.get("planta"), 80) or "Planta", "area": texto(u.get("area"), 80) or "Sin área",
                      "sistema": texto(u.get("sistema"), 80) or "Sin sistema"},
        "operacion": {"P_MPa": numero(op.get("P_MPa")) or 0.0, "T_C": numero(op.get("T_C")) or 20.0},
        "imagen": "", "adjuntos": [], "cmls": [], "diseno": {},
    }
    img = url_imagen(eq.get("imagen"))
    if img is None:
        err.append(f"{pref}: imagen con formato no permitido (solo PNG/JPG)")
    e["imagen"] = img or ""
    for a in (eq.get("adjuntos") or [])[:MAX_ADJ]:
        if isinstance(a, dict) and RE_PDF_DATA.match(texto(a.get("url"), 30_000_000)):
            e["adjuntos"].append({"nombre": texto(a.get("nombre"), 120) or "adjunto.pdf", "url": a["url"].strip()})
        else:
            err.append(f"{pref}: adjunto no permitido (solo PDF embebido)")
    d = eq.get("diseno") if isinstance(eq.get("diseno"), dict) else {}
    for campo in REQUERIDOS[fam]:
        if campo not in d:
            err.append(f"{pref}: falta el dato de diseño '{campo}'")
    for campo, valor in d.items():
        if campo not in RANGOS:
            continue
        x, msg = validar_campo_diseno(campo, valor)
        if msg:
            err.append(f"{pref}: {msg}")
        else:
            e["diseno"][campo] = int(x) if campo == "virola" else x
    if e["fecha_servicio"] == "":
        err.append(f"{pref}: fecha de puesta en servicio inválida")
    cids = set()
    for j, c in enumerate((eq.get("cmls") or [])[:MAX_CML]):
        cc = _cml(c, f"{pref} / CML #{j + 1}", err)
        if cc:
            if cc["id"] in cids:
                err.append(f"{pref}: CML duplicado '{cc['id']}'")
            cids.add(cc["id"])
            e["cmls"].append(cc)
    if isinstance(eq.get("rbi"), dict):
        e["rbi"] = _rbi(eq["rbi"], cids, pref, err)
    return e


def _cml(c, pref, err):
    if not isinstance(c, dict) or not texto(c.get("id"), 40):
        err.append(f"{pref}: falta el ID")
        return None
    x, y = numero(c.get("x")), numero(c.get("y"))
    t_nom = numero(c.get("t_nom_mm"))
    cc = {"id": texto(c["id"], 40), "componente": texto(c.get("componente")), "ubicacion": texto(c.get("ubicacion")),
          "x": min(max(x if x is not None else 50.0, 0.0), 100.0), "y": min(max(y if y is not None else 50.0, 0.0), 100.0),
          "t_nom_mm": t_nom if t_nom and 0 < t_nom <= 300 else None, "mediciones": []}
    if isinstance(c.get("diseno_local"), dict):
        dl = {}
        for campo, valor in c["diseno_local"].items():
            v, msg = validar_campo_diseno(campo, valor)
            if msg:
                err.append(f"{pref}: {msg}")
            elif campo in RANGOS:
                dl[campo] = int(v) if campo == "virola" else v
        cc["diseno_local"] = dl
    for m in (c.get("mediciones") or [])[:MAX_MED]:
        if not isinstance(m, dict):
            continue
        f = fecha_valida(m.get("fecha"))
        t = numero(m.get("espesor_mm"))
        if f is None or t is None or not 0 < t <= 300:
            err.append(f"{pref}: medición inválida ({texto(m.get('fecha'), 12)}, {texto(m.get('espesor_mm'), 12)})")
            continue
        mm = {"fecha": f, "espesor_mm": round(t, 4), "unidad": m.get("unidad") if m.get("unidad") in UNIDADES else "mm",
              "tecnica": texto(m.get("tecnica"), 40), "observaciones": texto(m.get("observaciones"), 300)}
        if m.get("evento") in EVENTOS:
            mm["evento"] = m["evento"]
        cc["mediciones"].append(mm)
    return cc


def _rbi(r, cids, pref, err):
    insp = r.get("inspecciones") if isinstance(r.get("inspecciones"), dict) else {}
    out = {
        "cml": r.get("cml") if r.get("cml") in cids else (sorted(cids)[0] if cids else ""),
        "confianza": r.get("confianza") if r.get("confianza") in PRIOR else "baja",
        "inspecciones": {k: int(min(max(numero(insp.get(k)) or 0, 0), 20)) for k in COND},
        "pscore": min(max(numero(r.get("pscore")) or 50.0, 0.0), 100.0),
        "f_om": numero(r.get("f_om")) or 1.0,
        "C_A_m2": numero(r.get("C_A_m2")), "C_E": numero(r.get("C_E")),
        "moneda": texto(r.get("moneda"), 8) or "USD",
        "base_valoracion": texto(r.get("base_valoracion"), 200), "escenario": texto(r.get("escenario"), 300),
        "fecha_eval": fecha_valida(r.get("fecha_eval")) or "",
    }
    if out["f_om"] <= 0 or out["f_om"] > 10:
        err.append(f"{pref}: F_OM fuera de rango (0–10]")
    for k in ("C_A_m2", "C_E"):
        if out[k] is None or out[k] < 0:
            err.append(f"{pref}: consecuencia {k} inválida")
    return out
