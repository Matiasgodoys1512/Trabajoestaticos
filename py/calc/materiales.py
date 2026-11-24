"""Catálogo acotado de materiales. Unidades: MPa, °C. Ver docs/fundamentos.md."""
KSI = 6.894757

def _ksi(tabla):
    return [(t, s * KSI) for t, s in tabla]

def _f2c(f):
    return (f - 32) * 5 / 9

# (temperatura °C, S MPa) — interpolación lineal
MATERIALES = {
    "A106-B": {
        "familia": "tuberia", "nombre": "ASTM A106 Gr. B (sin costura)",
        "ref": "ASME B31.3-2018, Tabla A-1",
        "YS": 35 * KSI, "TS": 60 * KSI, "E": 1.0,
        "S": _ksi([(_f2c(100), 20.0), (_f2c(200), 20.0), (_f2c(300), 20.0), (_f2c(400), 19.9), (_f2c(500), 19.0)]),
    },
    "A53-B": {
        "familia": "tuberia", "nombre": "ASTM A53 Gr. B (sin costura)",
        "ref": "ASME B31.3-2018, Tabla A-1",
        "YS": 35 * KSI, "TS": 60 * KSI, "E": 1.0,
        "S": _ksi([(_f2c(100), 20.0), (_f2c(200), 20.0), (_f2c(300), 20.0), (_f2c(400), 19.9), (_f2c(500), 19.0)]),
    },
    "SA-516-70": {
        "familia": "recipiente", "nombre": "ASME SA-516 Gr. 70",
        "ref": "ASME BPVC II-D 2019, Tabla 1A, línea 33",
        "YS": 38 * KSI, "TS": 70 * KSI, "E": None,
        "S": _ksi([(_f2c(100), 20.0), (_f2c(500), 20.0), (_f2c(600), 19.4), (_f2c(650), 18.8)]),
    },
    "A283-C": {
        "familia": "tanque", "nombre": "ASTM A283 Gr. C",
        "ref": "API 650-2013, Tabla 5.2a",
        "YS": 205.0, "TS": 380.0, "Sd": 137.0, "St": 154.0,
    },
    "A36": {
        "familia": "tanque", "nombre": "ASTM A36",
        "ref": "API 650-2013, Tabla 5.2a",
        "YS": 250.0, "TS": 400.0, "Sd": 160.0, "St": 171.0,
    },
}

def esfuerzo_admisible(codigo, temp_c):
    """S [MPa] interpolado a la temperatura de diseño. Error si está fuera de rango."""
    m = MATERIALES[codigo]
    tabla = m["S"]
    if temp_c <= tabla[0][0]:
        return tabla[0][1]
    for (t1, s1), (t2, s2) in zip(tabla, tabla[1:]):
        if t1 <= temp_c <= t2:
            return s1 + (s2 - s1) * (temp_c - t1) / (t2 - t1)
    raise ValueError(f"Temperatura {temp_c:.0f} °C fuera del rango del catálogo para {codigo} (máx {tabla[-1][0]:.0f} °C)")
