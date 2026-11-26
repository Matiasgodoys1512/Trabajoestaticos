"""Espesores requeridos por familia. Unidades: mm, MPa, m. Cada función devuelve un dict trazable."""
from .materiales import MATERIALES, esfuerzo_admisible


def _res(valor, ecuacion, ref, entradas, **extra):
    d = {"valor": valor, "unidad": "mm", "ecuacion": ecuacion, "ref": ref, "entradas": entradas}
    d.update(extra)
    return d


def tuberia_b313(P, D, S, E=1.0, W=1.0, Y=0.4):
    """ASME B31.3 §304.1.2 ec. (3a). P [MPa], D diámetro exterior [mm], S [MPa]."""
    t = P * D / (2 * (S * E * W + P * Y))
    avisos = []
    if t >= D / 6:
        avisos.append("t ≥ D/6: requiere consideración especial (§304.1.2(b))")
    if P / (S * E) > 0.385:
        avisos.append("P/SE > 0,385: fuera de alcance de ec. (3a)")
    return _res(t, "t = P·D / [2(S·E·W + P·Y)]", "ASME B31.3-2018 §304.1.2 ec. (3a)",
                {"P [MPa]": P, "D [mm]": D, "S [MPa]": S, "E": E, "W": W, "Y": Y}, avisos=avisos)


def recipiente_ug27(P, R, S, E):
    """ASME VIII-1 UG-27(c). P [MPa], R radio interior [mm], S [MPa], E eficiencia de junta.
    Gobierna el mayor entre (c)(1) esfuerzo circunferencial y (c)(2) esfuerzo longitudinal."""
    if S * E - 0.6 * P <= 0:
        raise ValueError("UG-27: S·E − 0,6·P ≤ 0 (presión excesiva para el material)")
    t1 = P * R / (S * E - 0.6 * P)
    t2 = P * R / (2 * S * E + 0.4 * P)
    avisos = []
    if P > 0.385 * S * E or t1 > R / 2:
        avisos.append("P > 0,385·S·E o t > R/2: fuera de alcance de UG-27(c)(1) (ver App. 1)")
    return _res(max(t1, t2), "t = máx[P·R / (S·E − 0,6·P) ; P·R / (2·S·E + 0,4·P)]", "ASME BPVC VIII-1 2019, UG-27(c)(1) y (c)(2)",
                {"P [MPa]": P, "R [mm]": R, "S [MPa]": S, "E": E}, avisos=avisos, t_circ=t1, t_long=t2,
                gobierna="circunferencial (c)(1)" if t1 >= t2 else "longitudinal (c)(2)")


def t_min_nominal_api650(D):
    """API 650 §5.6.1.1: espesor nominal mínimo del manto según diámetro [m] → [mm]."""
    if D < 15:
        return 5.0
    if D <= 36:
        return 6.0
    if D <= 60:
        return 8.0
    return 10.0


def tanque_api650_diseno(D, H, G, Sd, CA=0.0, St=None):
    """API 650 §5.6.3.2 (1 pie, SI). D [m], H [m] desde el fondo de la virola, Sd/St [MPa], CA [mm].
    Espesor requerido = máx(td, tt, mínimo nominal §5.6.1.1)."""
    if H <= 0.3:
        raise ValueError("API 650: H debe ser mayor que 0,3 m")
    td = 4.9 * D * (H - 0.3) * G / Sd + CA
    tt = 4.9 * D * (H - 0.3) / St if St else 0.0
    tmin_nom = t_min_nominal_api650(D)
    t = max(td, tt, tmin_nom)
    gob = "td (producto)" if t == td else ("tt (prueba hidrostática)" if t == tt else "mínimo nominal §5.6.1.1")
    return _res(t, "t = máx[td = 4,9·D·(H − 0,3)·G/Sd + CA ; tt = 4,9·D·(H − 0,3)/St ; t_nom mín]", "API 650-2013 §5.6.3.2 y §5.6.1.1",
                {"D [m]": D, "H [m]": H, "G": G, "Sd [MPa]": Sd, "St [MPa]": St or "—", "CA [mm]": CA},
                td=td, tt=tt, t_nom_min=tmin_nom, gobierna=gob)


def tanque_api653_tmin(D, H, G, YS, TS, E=1.0, virola=1):
    """API 653 §4.3.3.1 (SI). S según virola: 1–2 → mín(0,80Y; 0,429T); demás → mín(0,88Y; 0,472T)."""
    if virola <= 2:
        S = min(0.80 * YS, 0.429 * TS)
        regla = "S = mín(0,80·Y; 0,429·T) (virolas 1 y 2)"
    else:
        S = min(0.88 * YS, 0.472 * TS)
        regla = "S = mín(0,88·Y; 0,472·T) (virolas superiores)"
    if H <= 0.3:
        raise ValueError("API 653: H debe ser mayor que 0,3 m")
    t_calc = 4.9 * D * (H - 0.3) * G / (S * E)
    t = max(t_calc, 2.54)
    return _res(t, "t_min = 4,9·D·(H − 0,3)·G / (S·E), ≥ 2,54 mm (0,1 in)", "API 653 §4.3.3.1 (edición a declarar)",
                {"D [m]": D, "H [m]": H, "G": G, "Y [MPa]": YS, "T [MPa]": TS, "E": E, "virola": virola},
                S=S, regla_S=regla, t_calc=t_calc)


def espesor_alerta(t_min, cr, plazo_intervencion=2.0):
    """t_alerta = t_min + CR·T_int (margen por pérdida prevista durante el plazo de intervención)."""
    cr = max(cr or 0.0, 0.0)
    return _res(t_min + cr * plazo_intervencion, "t_alerta = t_min + CR·T_int", "Criterio del grupo",
                {"t_min [mm]": t_min, "CR [mm/año]": cr, "T_int [años]": plazo_intervencion})


def evaluar_equipo(eq, cml=None):
    """Calcula t_calc y t_min de un equipo. Un CML puede sobrescribir datos locales (p. ej. virola y H en tanques)."""
    fam = eq["familia"]
    d = dict(eq["diseno"])
    if cml and cml.get("diseno_local"):
        d.update(cml["diseno_local"])
    mat = MATERIALES[eq["material"]]
    if fam == "tuberia":
        S = esfuerzo_admisible(eq["material"], d["T_diseno_C"])
        r = tuberia_b313(d["P_diseno_MPa"], d["D_ext_mm"], S, d.get("E", mat["E"]), d.get("W", 1.0), d.get("Y", 0.4))
        t_min = max(r["valor"], d.get("t_estructural_mm", 0.0))
    elif fam == "recipiente":
        S = esfuerzo_admisible(eq["material"], d["T_diseno_C"])
        r = recipiente_ug27(d["P_diseno_MPa"], d["D_int_mm"] / 2, S, d["E"])
        t_min = r["valor"]
    elif fam == "tanque":
        r = tanque_api653_tmin(d["D_m"], d["H_m"], d["G"], mat["YS"], mat["TS"], d.get("E", 1.0), d.get("virola", 1))
        t_min = r["valor"]
    else:
        raise ValueError(f"Familia desconocida: {fam}")
    r["t_min"] = t_min
    return r


def espesor_diseno(eq, cml=None):
    """Espesor de diseño/compra según código de construcción (incluye CA y tolerancia de fabricación en tubería)."""
    fam = eq["familia"]
    d = dict(eq["diseno"])
    if cml and cml.get("diseno_local"):
        d.update(cml["diseno_local"])
    CA = d.get("CA_mm", 0.0)
    if fam == "tanque":
        mat = MATERIALES[eq["material"]]
        r = tanque_api650_diseno(d["D_m"], d["H_m"], d["G"], mat["Sd"], CA, mat["St"])
        r["t_calc"] = r["td"] - CA
        return r
    base = evaluar_equipo(eq, cml)
    t = base["valor"]
    r = dict(base)
    if fam == "tuberia":
        tol = d.get("tol_fab", 0.125)
        r.update(valor=(t + CA) / (1 - tol), t_calc=t, ecuacion="t_m = t + c ; t_compra ≥ t_m / (1 − tol)",
                 ref="ASME B31.3-2018 §304.1.1 (t_m) y tolerancia de fabricación ASTM A106/A53 (−12,5 %)",
                 entradas={"t [mm]": t, "c = CA [mm]": CA, "tol": tol})
    else:
        r.update(valor=t + CA, t_calc=t, ecuacion="t_diseño = t_UG-27 + CA", ref="ASME VIII-1 UG-25 / UG-16",
                 entradas={"t [mm]": t, "CA [mm]": CA})
    return r
