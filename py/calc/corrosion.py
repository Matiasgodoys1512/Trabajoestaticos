"""Velocidad de corrosión y vida remanente (API 510/570, método punto a punto). mm, años."""
from datetime import date

EVENTOS_REINICIO = {"reemplazo", "reparacion", "cambio_punto"}


def _fecha(x):
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def anios(f1, f2):
    return (_fecha(f2) - _fecha(f1)).days / 365.25


def serie_comparable(mediciones):
    """Ordena por fecha, valida y corta la serie en el último evento de reinicio (reemplazo/reparación/cambio de punto).
    Devuelve (serie, problemas)."""
    problemas = []
    ms = []
    for m in mediciones:
        try:
            f = _fecha(m["fecha"])
        except (ValueError, KeyError):
            problemas.append(f"Fecha inválida: {m.get('fecha')!r}")
            continue
        t = m.get("espesor_mm")
        if t is None or t <= 0:
            problemas.append(f"Espesor inválido el {f}")
            continue
        ms.append({**m, "_f": f})
    ms.sort(key=lambda m: m["_f"])
    if any(m["_f"] > date.today() for m in ms):
        problemas.append("Hay mediciones con fecha futura")
    for a, b in zip(ms, ms[1:]):
        if a["_f"] == b["_f"]:
            problemas.append(f"Fechas duplicadas: {a['_f']}")
    inicio = 0
    for i, m in enumerate(ms):
        if m.get("evento") in EVENTOS_REINICIO:
            inicio = i
    if inicio > 0:
        problemas.append(f"Serie reiniciada el {ms[inicio]['_f']} por '{ms[inicio]['evento']}': mediciones previas no comparables")
    return ms[inicio:], problemas


def velocidades(mediciones):
    """CR largo plazo, corto plazo y adoptada (máxima, criterio conservador)."""
    serie, problemas = serie_comparable(mediciones)
    r = {"cr_lp": None, "cr_cp": None, "cr": None, "criterio": None, "problemas": problemas,
         "n": len(serie), "t_actual": None, "fecha_actual": None, "t_inicial": None, "t_previo": None}
    if serie:
        r["t_actual"] = serie[-1]["espesor_mm"]
        r["fecha_actual"] = serie[-1]["_f"].isoformat()
    if len(serie) < 2:
        r["problemas"] = problemas + ["Información insuficiente: se requieren ≥ 2 mediciones comparables"]
        return r
    ini, prev, act = serie[0], serie[-2], serie[-1]
    dt_lp = anios(ini["_f"], act["_f"])
    dt_cp = anios(prev["_f"], act["_f"])
    if dt_lp <= 0 or dt_cp <= 0:
        r["problemas"] = problemas + ["Fechas inconsistentes (Δt ≤ 0)"]
        return r
    r["t_inicial"], r["t_previo"] = ini["espesor_mm"], prev["espesor_mm"]
    r["cr_lp"] = (ini["espesor_mm"] - act["espesor_mm"]) / dt_lp
    r["cr_cp"] = (prev["espesor_mm"] - act["espesor_mm"]) / dt_cp
    r["dt_lp"], r["dt_cp"] = dt_lp, dt_cp
    if len(serie) == 2:
        r["criterio"] = "Solo 2 mediciones: CR_LP = CR_CP"
    cr = max(r["cr_lp"], r["cr_cp"])
    if cr <= 0:
        r["problemas"].append("Velocidad de corrosión nula o negativa: revisar mediciones (posible error de lectura o cambio de punto)")
        r["cr"] = 0.0
    else:
        r["cr"] = cr
        r["criterio"] = r["criterio"] or ("CR_CP gobierna (mayor)" if r["cr_cp"] >= r["cr_lp"] else "CR_LP gobierna (mayor)")
    return r


def vida_remanente(t_actual, t_min, cr):
    """RL = (t_actual − t_min)/CR. None si CR ≤ 0 (no determinable)."""
    if t_actual is None:
        return None
    if t_actual <= t_min:
        return 0.0
    if not cr or cr <= 0:
        return None
    return (t_actual - t_min) / cr
