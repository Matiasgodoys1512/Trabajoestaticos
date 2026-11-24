"""Próxima inspección de espesores y condición del CML."""
from datetime import date, timedelta
from .corrosion import velocidades, vida_remanente
from .espesores import evaluar_equipo, espesor_alerta

MAX_API570 = {1: 5, 2: 10, 3: 10, 4: None}


def intervalo(familia, rl, clase=None, cr_conocida=True):
    """Devuelve (intervalo_años, criterio_gobernante, referencia)."""
    if familia == "recipiente":
        ref = "API 510 §7.1.1 (edición a declarar)"
        if rl is None:
            return 10.0 if cr_conocida else None, "CR no determinable: usar juicio del inspector", ref
        if rl < 4:
            return min(rl, 2.0), "RL < 4 años: mín(RL; 2 años)", ref
        return (rl / 2, "RL/2 gobierna", ref) if rl / 2 < 10 else (10.0, "Máximo 10 años gobierna", ref)
    if familia == "tuberia":
        ref = "API 570 §6.3.3, tabla de intervalos máximos"
        mx = MAX_API570.get(clase or 2)
        if rl is None:
            return mx, f"CR no determinable: máximo Clase {clase}", ref
        if rl < 4:
            return min(rl, 2.0), "RL < 4 años: mín(RL; 2 años)", ref
        if mx is None or rl / 2 < mx:
            return rl / 2, "RL/2 gobierna", ref
        return float(mx), f"Máximo Clase {clase} ({mx} años) gobierna", ref
    if familia == "tanque":
        ref = "API 653 §6.3.3.2 – UT externo del manto (edición a declarar)"
        if rl is None or not cr_conocida:
            return 5.0, "CR desconocida: máximo 5 años", ref
        return (rl / 2, "RCA/(2N) = RL/2 gobierna", ref) if rl / 2 < 15 else (15.0, "Máximo 15 años gobierna", ref)
    raise ValueError(familia)


def evaluar_cml(eq, cml, hoy=None, plazo_intervencion=2.0):
    """Evaluación completa de un CML: t_min, CR, RL, alerta, intervalo, próxima fecha y condición."""
    hoy = hoy or date.today()
    esp = evaluar_equipo(eq, cml)
    t_min = esp["t_min"]
    v = velocidades(cml.get("mediciones", []))
    rl = vida_remanente(v["t_actual"], t_min, v["cr"])
    alerta = espesor_alerta(t_min, v["cr"], plazo_intervencion)
    iv, criterio, ref = intervalo(eq["familia"], rl, eq.get("clase"), cr_conocida=bool(v["cr"]))
    prox = None
    if iv is not None and v["fecha_actual"]:
        prox = date.fromisoformat(v["fecha_actual"]) + timedelta(days=round(iv * 365.25))

    if v["t_actual"] is None or v["n"] < 2:
        cond = "insuficiente"
    elif v["t_actual"] < t_min:
        cond = "bajo_minimo"
    elif prox and hoy > prox:
        cond = "vencida"
    elif v["t_actual"] < alerta["valor"]:
        cond = "alerta"
    else:
        cond = "normal"
    return {"espesores": esp, "t_min": t_min, "t_alerta": alerta["valor"], "alerta": alerta,
            "corrosion": v, "rl": rl, "intervalo": iv, "criterio": criterio, "ref_intervalo": ref,
            "proxima": prox.isoformat() if prox else None, "condicion": cond}


PRIORIDAD = {"bajo_minimo": 0, "vencida": 1, "alerta": 2, "insuficiente": 3, "normal": 4}


def condicion_equipo(resultados_cml):
    """La peor condición de sus CML gobierna."""
    if not resultados_cml:
        return "insuficiente"
    return min((r["condicion"] for r in resultados_cml), key=PRIORIDAD.get)
