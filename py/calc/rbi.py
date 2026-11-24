"""RBI simplificado — API RP 581 (3ª ed. 2016 + Add. 2 2020), Parte 2 §4: DF por adelgazamiento generalizado.
Modelo académico: un mecanismo, sin cladding, consecuencias ingresadas por el usuario."""
import math

PRIOR = {"baja": (0.5, 0.3, 0.2), "media": (0.7, 0.2, 0.1), "alta": (0.8, 0.15, 0.05)}  # Tabla 4.5
COND = {  # Tabla 4.6: (Co1, Co2, Co3)
    "E": (0.33, 0.33, 0.33), "D": (0.4, 0.33, 0.27), "C": (0.5, 0.3, 0.2),
    "B": (0.7, 0.2, 0.1), "A": (0.9, 0.09, 0.01),
}
DS = (1, 2, 4)
COV_DT, COV_SF, COV_P = 0.20, 0.20, 0.05
GFF_RECIPIENTE = 3.06e-5  # Tabla 3.1, falla/año

# Parte 1, Tablas 4.1M y 4.2 (límites superiores)
LIM_POF = [3.06e-5, 3.06e-4, 3.06e-3, 3.06e-2]
LIM_CA_M2 = [9.29, 92.9, 929, 9290]
LIM_CE_USD = [1e4, 1e5, 1e6, 1e7]


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def f_ms(pscore):
    """Ec. 2.10: F_MS = 10^(−0,02·pscore + 1), pscore en %."""
    return 10 ** (-0.02 * pscore + 1)


def df_adelgazamiento(cr, edad, t_rdi, t_min, S, E, YS, TS, confianza="baja", inspecciones=None,
                      f_om=1.0, f_ip=1.0, f_dl=1.0, t_c=0.0):
    """Factor de daño por adelgazamiento. cr [mm/año], edad [años], espesores [mm], esfuerzos [MPa].
    inspecciones: dict {"A": n, "B": n, ...} realizadas en el periodo evaluado."""
    insp = {k: int(v) for k, v in (inspecciones or {}).items() if v}
    pasos = {}
    art = max(cr * edad / t_rdi, 0.0)                         # ec. 2.12
    fs = (YS + TS) / 2 * E * 1.1                              # ec. 2.13
    srp = S * E * max(t_min, t_c) / (fs * t_rdi)              # ec. 2.14
    pr = PRIOR[confianza]
    I = []
    for k in range(3):                                         # ec. 2.16
        v = pr[k]
        for cat, n in insp.items():
            v *= COND[cat][k] ** n
        I.append(v)
    po = [x / sum(I) for x in I]                               # ec. 2.17
    betas = []
    for k in range(3):                                         # ec. 2.18
        a = DS[k] * art
        num = 1 - a - srp
        den = math.sqrt(a ** 2 * COV_DT ** 2 + (1 - a) ** 2 * COV_SF ** 2 + srp ** 2 * COV_P ** 2)
        betas.append(num / den)
    dfb = sum(po[k] * phi(-betas[k]) for k in range(3)) / 1.56e-4   # ec. 2.19
    df = max(dfb * f_ip * f_dl / f_om, 0.1)                          # ec. 2.20
    pasos.update(Art=art, FS=fs, SRp=srp, prior=pr, I=I, Po=po, beta=betas, DfB=dfb)
    return {"Df": df, "pasos": pasos,
            "ref": "API RP 581-2016 Add.2, Parte 2, §4.5.7 ec. (2.12)–(2.20)"}


def categoria(valor, limites, etiquetas):
    for lim, et in zip(limites, etiquetas):
        if valor <= lim:
            return et
    return etiquetas[-1]


def riesgo(df, C_A_m2, C_E, moneda="USD", gff=GFF_RECIPIENTE, fms=1.0):
    """P_f = gff·F_MS·D_f [1/año]; R_A = P_f·C_A [m²/año]; R_E = P_f·C_E [moneda/año]."""
    pf = gff * fms * df
    cat_p = categoria(pf, LIM_POF, "12345")
    cat_a = categoria(C_A_m2, LIM_CA_M2, "ABCDE")
    cat_e = categoria(C_E, LIM_CE_USD, "ABCDE")
    n_a = nivel_riesgo(int(cat_p), cat_a)
    n_e = nivel_riesgo(int(cat_p), cat_e)
    peor = max(n_a, n_e, key=_NIVELES.index)
    return {"Pf": pf, "R_A": pf * C_A_m2, "R_E": pf * C_E, "moneda": moneda,
            "cat_pof": cat_p, "cat_area": cat_a, "cat_fin": cat_e,
            "nivel_area": n_a, "nivel_fin": n_e, "nivel": peor,
            "prioridad": 4 - _NIVELES.index(peor), "accion": ACCION[peor]}


ACCION = {
    "Alto": "Prioridad 1: inspección inmediata (UT de barrido / evaluación FFS) y medidas de mitigación",
    "Medio-alto": "Prioridad 2: inspección en el próximo plan anual con técnica B o superior",
    "Medio": "Prioridad 3: mantener el plan de inspección; reevaluar al actualizar mediciones",
    "Bajo": "Prioridad 4: inspección según intervalo normativo",
}


# Matriz 5x5 (criterio académico inspirado en API 581 Parte 1, Fig. 4.2): filas POF 1–5, columnas COF A–E
_NIVELES = ["Bajo", "Medio", "Medio-alto", "Alto"]


def nivel_riesgo(cat_pof, cat_cof):
    fila = {5: "12333", 4: "11233", 3: "01123", 2: "00122", 1: "00112"}[cat_pof]
    return _NIVELES[int(fila["ABCDE".index(cat_cof)])]
