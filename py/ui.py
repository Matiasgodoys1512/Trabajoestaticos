"""Generación de HTML para cada vista. No toca el DOM: recibe datos y devuelve texto HTML."""
import base64
import html
import io
from datetime import date

from calc import corrosion as co
from calc import espesores as es
from calc import inspeccion as ins
from calc import rbi
from calc.materiales import MATERIALES, esfuerzo_admisible

FAMILIAS = {"tuberia": "Tubería de proceso", "recipiente": "Recipiente a presión", "tanque": "Tanque atmosférico"}
CONDICION = {"normal": "Normal", "alerta": "Alerta", "bajo_minimo": "Bajo el mínimo",
             "vencida": "Inspección vencida", "insuficiente": "Información insuficiente", "error": "Error de datos"}
COLOR = {"normal": "#2e7d32", "alerta": "#e0a100", "bajo_minimo": "#c62828", "vencida": "#7b1fa2",
         "insuficiente": "#607d8b", "error": "#000"}
TECNICAS = ["UT haz recto", "UT A-scan", "UT B-scan", "RT de perfil", "Otro"]
EVENTOS = {"": "Ninguno", "reemplazo": "Reemplazo", "reparacion": "Reparación", "cambio_punto": "Cambio de punto"}
IN = 25.4

CAMPOS_DISENO = {
    "tuberia": [("P_diseno_MPa", "Presión de diseño P [MPa]"), ("T_diseno_C", "Temperatura de diseño [°C]"),
                ("D_ext_mm", "Diámetro exterior D [mm]"), ("E", "Factor de calidad E"), ("W", "Factor W"),
                ("Y", "Coeficiente Y"), ("CA_mm", "Sobreespesor de corrosión c [mm]"),
                ("tol_fab", "Tolerancia de fabricación (fracción)"), ("t_estructural_mm", "Espesor estructural mín. [mm]")],
    "recipiente": [("P_diseno_MPa", "Presión de diseño P [MPa]"), ("T_diseno_C", "Temperatura de diseño [°C]"),
                   ("D_int_mm", "Diámetro interior [mm]"), ("E", "Eficiencia de junta E (UW-12)"),
                   ("CA_mm", "Sobreespesor de corrosión CA [mm]")],
    "tanque": [("D_m", "Diámetro nominal D [m]"), ("H_m", "Nivel de diseño H [m] (virola 1)"),
               ("G", "Gravedad específica G"), ("E", "Eficiencia de junta E"), ("CA_mm", "Sobreespesor CA [mm]")],
}
DISENO_BASE = {
    "tuberia": {"P_diseno_MPa": 1.0, "T_diseno_C": 100, "D_ext_mm": 168.3, "E": 1.0, "W": 1.0, "Y": 0.4,
                "CA_mm": 1.5, "tol_fab": 0.125, "t_estructural_mm": 2.5},
    "recipiente": {"P_diseno_MPa": 1.0, "T_diseno_C": 100, "D_int_mm": 1000, "E": 0.85, "CA_mm": 3.0},
    "tanque": {"D_m": 15.0, "H_m": 10.0, "G": 1.0, "E": 1.0, "CA_mm": 1.5, "virola": 1},
}


def esc(x):
    return html.escape("" if x is None else str(x))


def f(x, n=2, unidad=""):
    if x is None:
        return "—"
    if isinstance(x, float) and (abs(x) >= 1e5 or (0 < abs(x) < 1e-3)):
        s = f"{x:.3e}"
    else:
        s = f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} {unidad}".strip()


def badge(cond):
    return f'<span class="badge b-{cond}">{CONDICION.get(cond, cond)}</span>'


def fecha_cl(iso):
    if not iso:
        return "—"
    a, m, d = iso[:10].split("-")
    return f"{d}-{m}-{a}"


# ------------------------------------------------------------------ evaluación global
def evaluar_todo(data, hoy=None):
    hoy = hoy or date.today()
    plazo = data.get("plazo_intervencion_anios", 2.0)
    res = {}
    for eq in data["equipos"]:
        r = {"cmls": {}, "error": None}
        try:
            for c in eq["cmls"]:
                r["cmls"][c["id"]] = ins.evaluar_cml(eq, c, hoy, plazo)
            r["cond"] = ins.condicion_equipo(list(r["cmls"].values()))
        except (ValueError, KeyError, ZeroDivisionError) as e:
            r["error"] = str(e)
            r["cond"] = "error"
        res[eq["id"]] = r
    return res


# ------------------------------------------------------------------ barra lateral
def sidebar(data, res, sel_id, filtros):
    areas = sorted({e["ubicacion"]["area"] for e in data["equipos"]})

    def opts(valores, actual, todos="Todos"):
        o = [f'<option value="">{todos}</option>']
        for v, t in valores:
            o.append(f'<option value="{esc(v)}" {"selected" if v == actual else ""}>{esc(t)}</option>')
        return "".join(o)

    h = ['<h3>Filtros</h3>',
         f'<select data-act="filtro" data-campo="area">{opts([(a, a) for a in areas], filtros.get("area"), "Todas las áreas")}</select>',
         f'<select data-act="filtro" data-campo="familia">{opts(FAMILIAS.items(), filtros.get("familia"), "Todas las familias")}</select>',
         f'<select data-act="filtro" data-campo="cond">{opts(CONDICION.items(), filtros.get("cond"), "Todas las condiciones")}</select>',
         '<h3>Estructura de planta</h3>']
    arbol = {}
    for e in filtrar(data, res, filtros):
        u = e["ubicacion"]
        arbol.setdefault(u["planta"], {}).setdefault(u["area"], {}).setdefault(u["sistema"], []).append(e)
    h.append('<ul class="arbol">')
    for planta, areas_ in arbol.items():
        h.append(f'<li><div class="nodo">🏭 {esc(planta)}</div><ul>')
        for area, sistemas in areas_.items():
            h.append(f'<li><div class="nodo">{esc(area)}</div><ul>')
            for sist, eqs in sistemas.items():
                h.append(f'<li><div class="nodo">{esc(sist)}</div><ul>')
                for e in eqs:
                    cond = res[e["id"]]["cond"]
                    act = "activo" if e["id"] == sel_id else ""
                    h.append(f'<li class="eq-item {act}" data-act="sel_eq" data-id="{esc(e["id"])}">'
                             f'<span class="punto" style="background:{COLOR[cond]}"></span>'
                             f'{esc(e["tag"])} <small class="muted">{FAMILIAS[e["familia"]].split()[0]}</small></li>')
                h.append('</ul></li>')
            h.append('</ul></li>')
        h.append('</ul></li>')
    h.append('</ul>')
    h.append('<div style="margin-top:14px"><button data-act="nuevo_eq" class="chico">+ Nuevo equipo</button></div>')
    return "".join(h)


def filtrar(data, res, filtros):
    out = []
    for e in data["equipos"]:
        if filtros.get("area") and e["ubicacion"]["area"] != filtros["area"]:
            continue
        if filtros.get("familia") and e["familia"] != filtros["familia"]:
            continue
        if filtros.get("cond"):
            conds = {r["condicion"] for r in res[e["id"]]["cmls"].values()} | {res[e["id"]]["cond"]}
            if filtros["cond"] not in conds:
                continue
        out.append(e)
    return out


# ------------------------------------------------------------------ panel
def filas_panel(data, res, filtros):
    filas = []
    for e in filtrar(data, res, filtros):
        r = res[e["id"]]
        if r["error"]:
            filas.append({"Equipo": e["tag"], "Familia": FAMILIAS[e["familia"]], "Área": e["ubicacion"]["area"],
                          "CML": "—", "Condición": "error", "_eq": e["id"], "_cml": None})
            continue
        for c in e["cmls"]:
            x = r["cmls"][c["id"]]
            if filtros.get("cond") and x["condicion"] != filtros["cond"]:
                continue
            v = x["corrosion"]
            filas.append({"Equipo": e["tag"], "Familia": FAMILIAS[e["familia"]], "Área": e["ubicacion"]["area"],
                          "CML": c["id"], "Componente": c["componente"], "t_actual [mm]": v["t_actual"],
                          "t_min [mm]": x["t_min"], "t_alerta [mm]": x["t_alerta"], "CR [mm/año]": v["cr"],
                          "RL [años]": x["rl"], "Próxima inspección": x["proxima"], "Condición": x["condicion"],
                          "_eq": e["id"], "_cml": c["id"]})
    return filas


def panel(data, res, filtros):
    filas = filas_panel(data, res, filtros)
    cuenta = {k: 0 for k in ["normal", "alerta", "bajo_minimo", "vencida", "insuficiente"]}
    for fl in filas:
        if fl["Condición"] in cuenta:
            cuenta[fl["Condición"]] += 1
    h = ['<div class="kpis">']
    for k, n in cuenta.items():
        h.append(f'<div class="kpi" style="border-left-color:{COLOR[k]}"><div class="v">{n}</div>'
                 f'<div class="l">CML · {CONDICION[k]}</div></div>')
    h.append('</div><div class="card"><h2>Resumen de CML/TML</h2>'
             '<p class="muted">Clic en una fila para abrir el equipo. La condición del equipo la gobierna su peor CML.</p>'
             '<table><tr><th>Equipo</th><th>Familia</th><th>CML</th><th>Componente</th><th class="num">t actual</th>'
             '<th class="num">t mín</th><th class="num">t alerta</th><th class="num">CR [mm/año]</th>'
             '<th class="num">RL [años]</th><th>Próx. inspección</th><th>Condición</th></tr>')
    for fl in filas:
        h.append(f'<tr class="click" data-act="sel_eq" data-id="{esc(fl["_eq"])}" data-cml="{esc(fl["_cml"] or "")}">'
                 f'<td>{esc(fl["Equipo"])}</td><td>{esc(fl["Familia"])}</td><td>{esc(fl["CML"])}</td>'
                 f'<td>{esc(fl.get("Componente", ""))}</td><td class="num">{f(fl.get("t_actual [mm]"))}</td>'
                 f'<td class="num">{f(fl.get("t_min [mm]"))}</td><td class="num">{f(fl.get("t_alerta [mm]"))}</td>'
                 f'<td class="num">{f(fl.get("CR [mm/año]"), 3)}</td><td class="num">{f(fl.get("RL [años]"), 1)}</td>'
                 f'<td>{fecha_cl(fl.get("Próxima inspección"))}</td><td>{badge(fl["Condición"])}</td></tr>')
    h.append('</table></div>')
    return "".join(h)


# ------------------------------------------------------------------ tarjetas de cálculo
def tarjeta(titulo, r, unidad="mm", n=2):
    ent = " · ".join(f"{esc(k)} = {f(v, 3) if isinstance(v, (int, float)) else esc(v)}" for k, v in r.get("entradas", {}).items())
    avisos = "".join(f'<div class="aviso">{esc(a)}</div>' for a in r.get("avisos", []))
    return (f'<div class="calc"><div><strong>{esc(titulo)}</strong></div>'
            f'<div class="ec">{esc(r["ecuacion"])}</div><div class="muted">Entradas: {ent}</div>'
            f'<div class="res">Resultado: {f(r["valor"], n, unidad)}</div><div class="ref">Referencia: {esc(r["ref"])}</div>{avisos}</div>')


def tarjetas_cml(eq, c, x):
    v = x["corrosion"]
    h = [tarjeta("Espesor mínimo admisible en servicio (t_min)", {**x["espesores"], "valor": x["t_min"]})]
    if eq["familia"] == "tuberia" and eq["diseno"].get("t_estructural_mm"):
        h.append(f'<p class="muted">t_min = máx(t presión = {f(x["espesores"]["valor"], 3)} mm; '
                 f't estructural = {f(eq["diseno"]["t_estructural_mm"])} mm) — t estructural según API 574 (dato ingresado).</p>')
    if v["cr_lp"] is not None:
        h.append(f'<div class="calc"><strong>Velocidad de corrosión (método punto a punto)</strong>'
                 f'<div class="ec">CR_LP = (t_inicial − t_actual) / Δt = ({f(v["t_inicial"])} − {f(v["t_actual"])}) / {f(v["dt_lp"])} = {f(v["cr_lp"], 3)} mm/año</div>'
                 f'<div class="ec">CR_CP = (t_previo − t_actual) / Δt = ({f(v["t_previo"])} − {f(v["t_actual"])}) / {f(v["dt_cp"])} = {f(v["cr_cp"], 3)} mm/año</div>'
                 f'<div class="res">CR adoptada = {f(v["cr"], 3)} mm/año ({esc(v["criterio"])})</div>'
                 f'<div class="ref">Referencia: API 570 §7.1.1 / API 510 §7.1.1; criterio conservador: mayor CR (clase 05)</div></div>')
    h.append(f'<div class="calc"><strong>Vida remanente</strong><div class="ec">RL = (t_actual − t_min) / CR</div>'
             f'<div class="res">RL = {f(x["rl"], 2, "años")}</div><div class="ref">Referencia: API 570 §7.1.1 / API 510 §7.1.1</div></div>')
    h.append(tarjeta("Espesor de alerta", x["alerta"]))
    h.append(f'<div class="calc"><strong>Próxima inspección (medición de espesores)</strong>'
             f'<div class="ec">Intervalo = {f(x["intervalo"], 2, "años")} → {esc(x["criterio"])}</div>'
             f'<div class="res">Fecha de referencia: {fecha_cl(v["fecha_actual"])} · Próxima: {fecha_cl(x["proxima"])}</div>'
             f'<div class="ref">Referencia: {esc(x["ref_intervalo"])}</div></div>')
    if eq["familia"] == "tanque":
        h.append('<div class="aviso">Alcance API 653: solo medición de espesores del manto. Inspección externa visual, '
                 'inspección interna y fondo del tanque: <strong>datos pendientes</strong> (fuera del alcance del prototipo).</div>')
    for p in v["problemas"]:
        h.append(f'<div class="error">{esc(p)}</div>')
    return "".join(h)


# ------------------------------------------------------------------ gráfico
def grafico(eq, c, x):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np

    ms = sorted(c.get("mediciones", []), key=lambda m: m["fecha"])
    serie, _ = co.serie_comparable(ms)
    ids_serie = {id(m) for m in ms if any(m["fecha"] == s["fecha"] and m["espesor_mm"] == s["espesor_mm"] for s in serie)}
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=100)
    if ms:
        fx = [date.fromisoformat(m["fecha"][:10]) for m in ms]
        ty = [m["espesor_mm"] for m in ms]
        ax.plot(fx, ty, color="#b0b8c1", lw=1, zorder=1)
        cs = ["#2b5d8a" if id(m) in ids_serie else "#b0b8c1" for m in ms]
        ax.scatter(fx, ty, c=cs, zorder=3, s=36, label="Mediciones UT")
        for m, xx, yy in zip(ms, fx, ty):
            if m.get("evento"):
                ax.annotate(EVENTOS[m["evento"]], (xx, yy), textcoords="offset points", xytext=(4, 8), fontsize=8, color="#c62828")
    ax.axhline(x["t_min"], color="#c62828", lw=1.5, label=f"t_min = {x['t_min']:.2f} mm")
    ax.axhline(x["t_alerta"], color="#e0a100", lw=1.2, ls="--", label=f"t_alerta = {x['t_alerta']:.2f} mm")
    if c.get("t_nom_mm"):
        ax.axhline(c["t_nom_mm"], color="#888", lw=1, ls=":", label=f"t_nom = {c['t_nom_mm']:.2f} mm")
    v = x["corrosion"]
    if v["cr"] and v["fecha_actual"] and x["rl"]:
        f0 = date.fromisoformat(v["fecha_actual"])
        anios = np.linspace(0, x["rl"], 20)
        ax.plot([date.fromordinal(f0.toordinal() + int(a * 365.25)) for a in anios], v["t_actual"] - v["cr"] * anios,
                color="#2b5d8a", ls="--", lw=1, label="Proyección (CR adoptada)")
    if x["proxima"]:
        ax.axvline(date.fromisoformat(x["proxima"]), color="#7b1fa2", lw=1, ls="-.", label="Próxima inspección")
    ax.axvline(date.today(), color="#333", lw=0.8, alpha=.5)
    ax.set_ylabel("Espesor [mm]")
    ax.set_title(f"{eq['tag']} · {c['id']}: espesor vs tiempo", fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(alpha=.3)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return f'<img alt="Gráfico espesor vs tiempo" src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}">'


# ------------------------------------------------------------------ vista equipo
def ficha(eq):
    u = eq["ubicacion"]
    mat = MATERIALES.get(eq["material"], {})
    filas = [("TAG", eq["tag"]), ("Familia", FAMILIAS[eq["familia"]]), ("Descripción", eq["descripcion"]),
             ("Ubicación técnica", f'{u["planta"]} › {u["area"]} › {u["sistema"]} › {eq["tag"]}'),
             ("Servicio / fluido", f'{eq["servicio"]} / {eq["fluido"]}'), ("Material", mat.get("nombre", eq["material"])),
             ("Código de diseño", eq["codigo_diseno"]), ("Código en servicio", eq["codigo_servicio"]),
             ("Espesor nominal", f(eq["t_nom_mm"], 2, "mm")), ("Puesta en servicio", fecha_cl(eq.get("fecha_servicio"))),
             ("Operación", f'P = {f(eq["operacion"]["P_MPa"])} MPa · T = {f(eq["operacion"]["T_C"], 0)} °C')]
    if eq["familia"] == "tuberia":
        filas += [("Circuito de inspección", eq.get("circuito")), ("Clase de tubería (API 570)", eq.get("clase"))]
    return "<table>" + "".join(f"<tr><th>{esc(a)}</th><td>{esc(b)}</td></tr>" for a, b in filas) + "</table>"


def esquema(eq, res_eq, cml_sel):
    if not eq.get("imagen"):
        return '<p class="muted">Sin esquema asociado. Cárgalo abajo (PNG o JPG).</p>'
    h = [f'<div class="esquema"><img src="{esc(eq["imagen"])}" alt="Esquema {esc(eq["tag"])}">']
    for c in eq["cmls"]:
        cond = res_eq["cmls"].get(c["id"], {}).get("condicion", "insuficiente")
        sel = "sel" if c["id"] == cml_sel else ""
        h.append(f'<div class="marcador {sel}" data-act="sel_cml" data-id="{esc(c["id"])}" title="{esc(c["id"])}" '
                 f'style="left:{c["x"]}%;top:{c["y"]}%;background:{COLOR[cond]}"><span>{esc(c["id"].split("-")[-1])}</span></div>')
    h.append('</div><p class="muted">Convención: CML = Condition Monitoring Location (API 510/570); coordenadas (x, y) en % '
             'del ancho y alto del esquema, origen en la esquina superior izquierda. Número = correlativo del CML en el equipo.</p>')
    return "".join(h)


def form_medicion(c):
    hoy = date.today().isoformat()
    tec = "".join(f"<option>{t}</option>" for t in TECNICAS)
    ev = "".join(f'<option value="{k}">{v}</option>' for k, v in EVENTOS.items())
    return (f'<form class="f" id="form_med" onsubmit="return false">'
            f'<label>Fecha<input type="date" name="fecha" value="{hoy}" required></label>'
            f'<label>Espesor<input type="number" step="0.001" name="espesor" required></label>'
            f'<label>Unidad<select name="unidad"><option>mm</option><option>in</option></select></label>'
            f'<label>Técnica<select name="tecnica">{tec}</select></label>'
            f'<label>Evento<select name="evento">{ev}</select></label>'
            f'<label>Observaciones<input name="observaciones"></label>'
            f'<button data-act="add_med">Agregar medición y recalcular</button></form>')


def vista_equipo(data, res, eq, cml_sel):
    r = res[eq["id"]]
    h = [f'<div class="card"><h2>{esc(eq["tag"])} — {esc(eq["descripcion"])} {badge(r["cond"])}</h2>']
    if r["error"]:
        h.append(f'<div class="error">No se pudo evaluar el equipo: {esc(r["error"])}</div>')
    h.append(f'<div class="grid2"><div>{ficha(eq)}<div class="acciones-form">'
             f'<button class="chico" data-act="editar_eq">Editar equipo</button>'
             f'<button class="chico peligro" data-act="borrar_eq">Eliminar equipo</button></div></div>'
             f'<div>{esquema(eq, r, cml_sel)}</div></div></div>')

    h.append('<div class="card"><h2>CML / TML del equipo</h2><table><tr><th>CML</th><th>Componente</th><th>Ubicación</th>'
             '<th class="num">x, y [%]</th><th class="num">N° med.</th><th class="num">t actual</th><th>Condición</th></tr>')
    for c in eq["cmls"]:
        x = r["cmls"].get(c["id"])
        sel = "sel" if c["id"] == cml_sel else ""
        h.append(f'<tr class="click {sel}" data-act="sel_cml" data-id="{esc(c["id"])}"><td>{esc(c["id"])}</td>'
                 f'<td>{esc(c["componente"])}</td><td>{esc(c["ubicacion"])}</td><td class="num">{c["x"]}, {c["y"]}</td>'
                 f'<td class="num">{len(c.get("mediciones", []))}</td>'
                 f'<td class="num">{f(x["corrosion"]["t_actual"]) if x else "—"}</td>'
                 f'<td>{badge(x["condicion"]) if x else "—"}</td></tr>')
    h.append('</table><h3>Agregar CML</h3>'
             '<form class="f" id="form_cml" onsubmit="return false">'
             '<label>ID CML<input name="id" placeholder="CML-xxx-05" required></label>'
             '<label>Componente<input name="componente"></label><label>Ubicación<input name="ubicacion"></label>'
             '<label>x [%]<input type="number" name="x" min="0" max="100" value="50"></label>'
             '<label>y [%]<input type="number" name="y" min="0" max="100" value="50"></label>'
             '<label>t nominal [mm]<input type="number" step="0.01" name="t_nom_mm"></label>')
    if eq["familia"] == "tanque":
        h.append('<label>Virola N°<input type="number" name="virola" value="1" min="1"></label>'
                 '<label>H desde fondo de virola [m]<input type="number" step="0.01" name="H_m"></label>')
    h.append('<button data-act="add_cml">Agregar CML</button></form></div>')

    c = next((c for c in eq["cmls"] if c["id"] == cml_sel), None)
    if c and r["cmls"].get(c["id"]):
        x = r["cmls"][c["id"]]
        h.append(f'<div class="card"><h2>{esc(c["id"])} · {esc(c["componente"])} {badge(x["condicion"])}</h2>'
                 f'<div class="grid2"><div class="grafico">{grafico(eq, c, x)}</div><div>{tarjetas_cml(eq, c, x)}</div></div>'
                 '<h3>Historial de mediciones</h3><table><tr><th>Fecha</th><th class="num">Espesor [mm]</th><th>Unidad original</th>'
                 '<th>Técnica</th><th>Evento</th><th>Observaciones</th><th></th></tr>')
        for i, m in sorted(enumerate(c.get("mediciones", [])), key=lambda t: t[1]["fecha"]):
            orig = f'{m["espesor_mm"] / IN:.3f} in' if m.get("unidad") == "in" else "mm"
            h.append(f'<tr><td>{fecha_cl(m["fecha"])}</td><td class="num">{f(m["espesor_mm"], 2)}</td><td>{orig}</td>'
                     f'<td>{esc(m.get("tecnica"))}</td><td>{EVENTOS.get(m.get("evento") or "", "")}</td>'
                     f'<td>{esc(m.get("observaciones"))}</td>'
                     f'<td><button class="chico secundario" data-act="del_med" data-i="{i}">Eliminar</button></td></tr>')
        h.append(f'</table><h3>Nueva medición</h3>{form_medicion(c)}'
                 '<h3>Editar posición del marcador</h3><form class="f" id="form_xy" onsubmit="return false">'
                 f'<label>x [%]<input type="number" name="x" value="{c["x"]}" min="0" max="100"></label>'
                 f'<label>y [%]<input type="number" name="y" value="{c["y"]}" min="0" max="100"></label>'
                 '<button data-act="mover_cml" class="chico">Actualizar posición</button>'
                 '<button data-act="borrar_cml" class="chico peligro">Eliminar CML</button></form></div>')
    elif eq["cmls"]:
        h.append('<p class="muted">Selecciona un CML en el esquema o en la tabla para ver su historial y cálculos.</p>')

    h.append('<div class="card"><h2>Documentación técnica</h2>'
             '<form class="f" onsubmit="return false"><label>Esquema / isométrico / foto (PNG o JPG)'
             '<input type="file" accept="image/png,image/jpeg" data-act="subir_img"></label>'
             '<label>Adjuntar PDF (solo consulta)<input type="file" accept="application/pdf" data-act="subir_pdf"></label></form>')
    if eq.get("adjuntos"):
        h.append("<ul>" + "".join(f'<li><a href="{esc(a["url"])}" target="_blank" download="{esc(a["nombre"])}">{esc(a["nombre"])}</a> '
                                   f'<button class="chico secundario" data-act="del_adj" data-i="{i}">Quitar</button></li>'
                                   for i, a in enumerate(eq["adjuntos"])) + "</ul>")
    else:
        h.append('<p class="muted">Sin PDF adjuntos.</p>')
    h.append('</div>')
    return "".join(h)


# ------------------------------------------------------------------ formulario de equipo
def form_equipo(eq=None):
    nuevo = eq is None
    eq = eq or {"id": "", "tag": "", "familia": "tuberia", "descripcion": "", "servicio": "", "fluido": "",
                "ubicacion": {"planta": "Refinería Demo", "area": "", "sistema": ""}, "circuito": "", "clase": 2,
                "material": "A106-B", "codigo_diseno": "", "codigo_servicio": "", "t_nom_mm": 0,
                "fecha_servicio": date.today().isoformat(), "operacion": {"P_MPa": 0, "T_C": 20}}
    fam_opts = "".join(f'<option value="{k}" {"selected" if k == eq["familia"] else ""}>{v}</option>' for k, v in FAMILIAS.items())
    mat_opts = "".join(f'<option value="{k}" {"selected" if k == eq["material"] else ""}>{v["nombre"]} ({FAMILIAS[v["familia"]]})</option>'
                       for k, v in MATERIALES.items())
    u = eq["ubicacion"]

    def inp(name, label, val, tipo="text", extra=""):
        return f'<label>{label}<input type="{tipo}" name="{name}" value="{esc(val)}" {extra}></label>'

    return (f'<div class="card"><h2>{"Nuevo equipo" if nuevo else "Editar " + esc(eq["tag"])}</h2>'
            '<form class="f" id="form_eq" onsubmit="return false">'
            + inp("tag", "TAG", eq["tag"], extra="required")
            + f'<label>Familia<select name="familia" {"" if nuevo else "disabled"}>{fam_opts}</select></label>'
            + inp("descripcion", "Descripción", eq["descripcion"]) + inp("servicio", "Servicio", eq["servicio"])
            + inp("fluido", "Fluido", eq["fluido"]) + inp("planta", "Planta", u["planta"])
            + inp("area", "Área", u["area"]) + inp("sistema", "Sistema / línea", u["sistema"])
            + inp("circuito", "Circuito de inspección (tubería)", eq.get("circuito") or "")
            + inp("clase", "Clase API 570 (1–4)", eq.get("clase") or "", "number", 'min="1" max="4"')
            + f'<label>Material<select name="material">{mat_opts}</select></label>'
            + inp("codigo_diseno", "Código de diseño", eq["codigo_diseno"])
            + inp("codigo_servicio", "Código en servicio", eq["codigo_servicio"])
            + inp("t_nom_mm", "Espesor nominal [mm]", eq["t_nom_mm"], "number", 'step="0.01"')
            + inp("fecha_servicio", "Puesta en servicio", eq.get("fecha_servicio", ""), "date")
            + inp("P_op", "P operación [MPa]", eq["operacion"]["P_MPa"], "number", 'step="0.01"')
            + inp("T_op", "T operación [°C]", eq["operacion"]["T_C"], "number", 'step="1"')
            + '</form><div class="acciones-form">'
            f'<button data-act="guardar_eq" data-nuevo="{1 if nuevo else 0}">Guardar equipo</button>'
            '<button class="secundario" data-act="tab" data-tab="equipo">Cancelar</button></div>'
            '<p class="muted">Los datos de diseño (P, T, dimensiones, E, CA) se editan en la pestaña “Diseño y espesores”.</p></div>')


# ------------------------------------------------------------------ diseño
def vista_diseno(eq, res_eq):
    fam = eq["familia"]
    d = eq["diseno"]
    mat = MATERIALES[eq["material"]]
    h = [f'<div class="card"><h2>Condiciones de diseño — {esc(eq["tag"])} ({FAMILIAS[fam]})</h2>'
         '<p class="muted">Modifica un valor y presiona Tab/Enter: se recalculan espesores, vida remanente, condición y fecha.</p>'
         '<form class="f" onsubmit="return false">']
    for k, label in CAMPOS_DISENO[fam]:
        h.append(f'<label>{label}<input type="number" step="any" value="{d.get(k, "")}" data-act="diseno" data-campo="{k}"></label>')
    h.append('</form>')
    if res_eq["error"]:
        h.append(f'<div class="error">{esc(res_eq["error"])}</div>')
    h.append('</div>')

    h.append('<div class="card"><h2>Material y esfuerzo admisible</h2>')
    if fam == "tanque":
        h.append(f'<p>{esc(mat["nombre"])} — Y = {f(mat["YS"], 0)} MPa, T = {f(mat["TS"], 0)} MPa, '
                 f'Sd = {f(mat["Sd"], 0)} MPa, St = {f(mat["St"], 0)} MPa. <span class="ref muted">({esc(mat["ref"])})</span></p>')
    else:
        try:
            S = esfuerzo_admisible(eq["material"], d["T_diseno_C"])
            h.append(f'<p>{esc(mat["nombre"])} — S a {f(d["T_diseno_C"], 0)} °C = <strong>{f(S, 1)} MPa</strong> '
                     f'({f(S / 6.894757, 1)} ksi), interpolado linealmente. <span class="muted">({esc(mat["ref"])})</span></p>')
        except ValueError as e:
            h.append(f'<div class="error">{esc(e)}</div>')
        tabla = "".join(f"<tr><td class='num'>{f(t, 0)}</td><td class='num'>{f(s, 1)}</td></tr>" for t, s in mat["S"])
        h.append(f'<table style="max-width:300px"><tr><th class="num">T [°C]</th><th class="num">S [MPa]</th></tr>{tabla}</table>')
    h.append('</div>')

    if res_eq["error"]:
        return "".join(h)
    h.append('<div class="card"><h2>Espesores de evaluación</h2>')
    cmls = eq["cmls"] if fam == "tanque" else eq["cmls"][:1]
    for c in cmls:
        x = res_eq["cmls"][c["id"]]
        dis = es.espesor_diseno(eq, c)
        if fam == "tanque":
            h.append(f'<h3>{esc(c["id"])} — {esc(c["componente"])}</h3>')
        h.append('<div class="grid2"><div>')
        h.append(tarjeta("Espesor requerido por cálculo (t_calc)", {**dis, "valor": dis["t_calc"], "ecuacion": x["espesores"]["ecuacion"] if fam != "tanque" else "td − CA = 4,9·D·(H − 0,3)·G / Sd",
                                                                      "entradas": x["espesores"]["entradas"] if fam != "tanque" else dis["entradas"]}, n=3))
        h.append(tarjeta("Espesor de diseño / compra", dis, n=3))
        h.append('</div><div>')
        h.append(tarjeta("Espesor mínimo admisible en servicio (t_min)", {**x["espesores"], "valor": x["t_min"]}, n=3))
        if fam == "tanque":
            h.append(f'<p class="muted">{esc(x["espesores"]["regla_S"])} → S = {f(x["espesores"]["S"], 1)} MPa</p>')
        tn = c.get("t_nom_mm") or eq["t_nom_mm"]
        h.append(f'<table><tr><th>Espesor</th><th class="num">mm</th></tr>'
                 f'<tr><td>Nominal</td><td class="num">{f(tn)}</td></tr>'
                 f'<tr><td>Requerido por cálculo</td><td class="num">{f(dis["t_calc"], 3)}</td></tr>'
                 f'<tr><td>Diseño (incl. CA{" y tolerancia" if fam == "tuberia" else ""})</td><td class="num">{f(dis["valor"], 3)}</td></tr>'
                 f'<tr><td>Mínimo admisible en servicio</td><td class="num">{f(x["t_min"], 3)}</td></tr>'
                 f'<tr><td>Alerta</td><td class="num">{f(x["t_alerta"], 3)}</td></tr>'
                 f'<tr><td>Medido (último)</td><td class="num">{f(x["corrosion"]["t_actual"])}</td></tr></table>')
        if dis["valor"] > tn:
            h.append(f'<div class="error">El espesor nominal ({f(tn)} mm) es menor que el de diseño ({f(dis["valor"], 2)} mm).</div>')
        h.append('</div></div>')
    h.append('<div class="calc"><strong>Notas</strong><ul>'
             '<li><b>CA (sobreespesor por corrosión)</b>: metal adicional que se agrega en el diseño para consumirse durante la vida útil. '
             'No forma parte del t_min de servicio.</li>'
             '<li><b>Tolerancia de fabricación</b>: el tubo sin costura puede venir hasta 12,5 % más delgado que el nominal; '
             'por eso el espesor de compra se divide por (1 − 0,125).</li>'
             '<li><b>Espesor de alerta</b>: t_min + CR·T_int, con T_int = plazo de intervención (gestión de la OT, repuestos y parada).</li></ul></div>')
    h.append('</div>')
    return "".join(h)


# ------------------------------------------------------------------ RBI
def matriz(cat_p, cat_c, titulo):
    h = [f'<div><h3>{titulo}</h3><div class="matriz">']
    for p in "54321":
        h.append(f'<div class="eje">{p}</div>')
        for c in "ABCDE":
            n = rbi.nivel_riesgo(int(p), c)
            aqui = "aqui" if (p == cat_p and c == cat_c) else ""
            h.append(f'<div class="m-{n} {aqui}">{"●" if aqui else ""}</div>')
    h.append('<div></div>' + "".join(f'<div class="eje">{c}</div>' for c in "ABCDE"))
    h.append('</div><p class="muted">Filas: categoría de POF · Columnas: categoría de consecuencia</p></div>')
    return "".join(h)


def calcular_rbi(eq, res_eq):
    cfg = eq["rbi"]
    c = next(c for c in eq["cmls"] if c["id"] == cfg["cml"])
    x = res_eq["cmls"][c["id"]]
    v = x["corrosion"]
    mat = MATERIALES[eq["material"]]
    S = esfuerzo_admisible(eq["material"], eq["diseno"]["T_diseno_C"])
    f_eval = cfg.get("fecha_eval") or date.today().isoformat()
    edad = co.anios(eq["fecha_servicio"], f_eval)
    cr = v["cr_lp"] if v["cr_lp"] and v["cr_lp"] > 0 else (v["cr"] or 0.0)
    ent = dict(cr=cr, edad=edad, t_rdi=c.get("t_nom_mm") or eq["t_nom_mm"], t_min=x["t_min"], S=S,
               E=eq["diseno"]["E"], YS=mat["YS"], TS=mat["TS"], confianza=cfg["confianza"], f_om=cfg.get("f_om", 1.0))
    con = rbi.df_adelgazamiento(**ent, inspecciones=cfg["inspecciones"])
    sin = rbi.df_adelgazamiento(**ent, inspecciones={})
    fms = rbi.f_ms(cfg.get("pscore", 50))
    rr = rbi.riesgo(con["Df"], cfg["C_A_m2"], cfg["C_E"], cfg.get("moneda", "USD"), fms=fms)
    rs = rbi.riesgo(sin["Df"], cfg["C_A_m2"], cfg["C_E"], cfg.get("moneda", "USD"), fms=fms)
    return {"ent": ent, "con": con, "sin": sin, "fms": fms, "r": rr, "r_sin": rs, "f_eval": f_eval, "cml": c}


def vista_rbi(data, res):
    eq = next((e for e in data["equipos"] if e.get("rbi") and e["familia"] == "recipiente"), None)
    if not eq:
        return '<div class="card"><p>No hay un recipiente con caso RBI definido.</p></div>'
    if res[eq["id"]]["error"]:
        return f'<div class="error">{esc(res[eq["id"]]["error"])}</div>'
    cfg = eq["rbi"]
    R = calcular_rbi(eq, res[eq["id"]])
    p = R["con"]["pasos"]
    e = R["ent"]
    r = R["r"]
    cml_opts = "".join(f'<option {"selected" if c["id"] == cfg["cml"] else ""}>{esc(c["id"])}</option>' for c in eq["cmls"])
    conf_opts = "".join(f'<option {"selected" if k == cfg["confianza"] else ""}>{k}</option>' for k in rbi.PRIOR)

    def num(campo, label, val, step="any"):
        return f'<label>{label}<input type="number" step="{step}" value="{val}" data-act="rbi" data-campo="{campo}"></label>'

    h = [f'<div class="card"><h2>RBI por adelgazamiento generalizado — {esc(eq["tag"])} (API RP 580 / RP 581)</h2>'
         '<div class="aviso">Modelo académico simplificado: un mecanismo (adelgazamiento generalizado interno), sin cladding, '
         'F_IP = F_DL = 1, consecuencias ingresadas por el usuario (no se modela la liberación). Base temporal: 1 año.</div>'
         '<form class="f" onsubmit="return false">'
         f'<label>CML gobernante<select data-act="rbi" data-campo="cml">{cml_opts}</select></label>'
         f'<label>Fecha de evaluación<input type="date" value="{R["f_eval"]}" data-act="rbi" data-campo="fecha_eval"></label>'
         f'<label>Confianza en la CR (Tabla 4.5)<select data-act="rbi" data-campo="confianza">{conf_opts}</select></label>']
    for k in "ABCD":
        h.append(num(f"insp_{k}", f"N° inspecciones efectividad {k}", cfg["inspecciones"].get(k, 0), "1"))
    h.append(num("pscore", "Puntaje sistema de gestión [%]", cfg.get("pscore", 50)))
    h.append(num("f_om", "F_OM monitoreo en línea", cfg.get("f_om", 1.0)))
    h.append(num("C_A_m2", "Consecuencia de área C_A [m²]", cfg["C_A_m2"]))
    h.append(num("C_E", f"Consecuencia económica C_E [{esc(cfg.get('moneda', 'USD'))}]", cfg["C_E"]))
    h.append(f'<label>Moneda<input value="{esc(cfg.get("moneda", "USD"))}" data-act="rbi" data-campo="moneda"></label>'
             f'<label>Base de valoración<input value="{esc(cfg.get("base_valoracion", ""))}" data-act="rbi" data-campo="base_valoracion"></label>'
             '</form>'
             f'<p class="muted">Escenario de falla: {esc(cfg.get("escenario", ""))}</p></div>')

    h.append('<div class="grid2"><div class="card"><h2>1. Factor de daño D_f (Parte 2, §4.5.7)</h2>')
    filas = [
        ("CR (largo plazo, medida)", "API 581 §4.5.2 recomienda CR de largo plazo", f(e["cr"], 4, "mm/año")),
        ("age (desde puesta en servicio)", f"{fecha_cl(eq['fecha_servicio'])} → {fecha_cl(R['f_eval'])}", f(e["edad"], 2, "años")),
        ("t_rdi (espesor entregado)", "Espesor nominal del CML", f(e["t_rdi"], 2, "mm")),
        ("t_min", "UG-27 (ver Diseño)", f(e["t_min"], 3, "mm")),
        ("Art = CR·age / t_rdi", "ec. 2.12", f(p["Art"], 4)),
        ("FS = (YS + TS)/2 · E · 1,1", "ec. 2.13", f(p["FS"], 1, "MPa")),
        ("SR_P = S·E·t_min / (FS·t_rdi)", "ec. 2.14", f(p["SRp"], 4)),
        ("Prior Pr₁, Pr₂, Pr₃", f"Tabla 4.5 ({cfg['confianza']})", " / ".join(f(x, 2) for x in p["prior"])),
        ("Posterior Po₁, Po₂, Po₃", "ec. 2.16–2.17 (Bayes, Tabla 4.6)", " / ".join(f(x, 4) for x in p["Po"])),
        ("β₁, β₂, β₃", "ec. 2.18 (DS = 1, 2, 4; COV 0,20/0,20/0,05)", " / ".join(f(x, 3) for x in p["beta"])),
        ("D_fB = ΣPo·Φ(−β) / 1,56·10⁻⁴", "ec. 2.19", f(p["DfB"], 2)),
        ("D_f = máx(D_fB / F_OM; 0,1)", "ec. 2.20", f(R["con"]["Df"], 2)),
    ]
    h.append('<table><tr><th>Parámetro</th><th>Origen</th><th class="num">Valor</th></tr>'
             + "".join(f'<tr><td>{a}</td><td class="muted">{b}</td><td class="num">{c}</td></tr>' for a, b, c in filas) + '</table></div>')

    h.append('<div class="card"><h2>2. Probabilidad (frecuencia) de falla</h2>'
             f'<div class="calc"><div class="ec">P_f(t) = gff · F_MS · D_f</div>'
             f'<div class="muted">gff = 3,06·10⁻⁵ fallas/año (Parte 2, Tabla 3.1, recipiente) · F_MS = 10^(−0,02·{f(cfg.get("pscore", 50), 0)} + 1) = {f(R["fms"], 3)} (ec. 2.10)</div>'
             f'<div class="res">P_f = {f(r["Pf"])} fallas/año → categoría POF {r["cat_pof"]}</div>'
             '<div class="ref">D_f es adimensional (multiplica la frecuencia genérica); P_f es una frecuencia anual de falla.</div></div>'
             '<h2 style="margin-top:14px">3. Riesgo (base anual)</h2>'
             f'<div class="calc"><div class="ec">R_A = P_f · C_A = {f(r["Pf"])} · {f(cfg["C_A_m2"], 1)}</div>'
             f'<div class="res">R_A = {f(r["R_A"])} m²/año · Consecuencia de área: categoría {r["cat_area"]}</div></div>'
             f'<div class="calc"><div class="ec">R_E = P_f · C_E = {f(r["Pf"])} · {f(cfg["C_E"], 0)}</div>'
             f'<div class="res">R_E = {f(r["R_E"], 2)} {esc(r["moneda"])}/año · Consecuencia económica: categoría {r["cat_fin"]}</div>'
             f'<div class="ref">Base de valoración: {esc(cfg.get("base_valoracion", ""))}</div></div>'
             '<h2 style="margin-top:14px">4. Efecto de la inspección</h2>'
             '<table><tr><th></th><th class="num">D_f</th><th class="num">P_f [1/año]</th><th class="num">R_A [m²/año]</th><th>Nivel</th></tr>'
             f'<tr><td>Sin inspecciones (prior)</td><td class="num">{f(R["sin"]["Df"], 1)}</td><td class="num">{f(R["r_sin"]["Pf"])}</td>'
             f'<td class="num">{f(R["r_sin"]["R_A"])}</td><td>{R["r_sin"]["nivel"]}</td></tr>'
             f'<tr><td>Con inspecciones registradas</td><td class="num">{f(R["con"]["Df"], 1)}</td><td class="num">{f(r["Pf"])}</td>'
             f'<td class="num">{f(r["R_A"])}</td><td>{r["nivel"]}</td></tr></table>'
             '<p class="muted">La inspección <b>no recupera espesor</b>: no cambia Art ni la CR. Solo actualiza (Bayes) la confianza '
             'en que la CR real sea la medida, reduciendo el peso de los estados de daño 2 y 3 y, con ello, D_f.</p></div></div>')

    h.append('<div class="card"><h2>5. Matriz de riesgo y prioridad</h2><div class="grid3">'
             + matriz(r["cat_pof"], r["cat_area"], f"Riesgo por área → {r['nivel_area']}")
             + matriz(r["cat_pof"], r["cat_fin"], f"Riesgo económico → {r['nivel_fin']}")
             + f'<div><h3>Prioridad de inspección</h3><p style="font-size:22px;font-weight:700">{r["nivel"]}</p>'
               f'<p>{esc(r["accion"])}</p><p class="muted">Gobierna la peor de las dos clasificaciones. Límites de categoría: '
               'API RP 581 Parte 1, Tablas 4.1M (m²) y 4.2 (USD). Matriz 5×5 de niveles: criterio del grupo basado en Parte 1, Fig. 4.2.</p></div>'
             + '</div></div>')
    return "".join(h)


# ------------------------------------------------------------------ validación
def casos_validacion():
    """Casos con resultado esperado calculado de forma independiente (a mano / planilla)."""
    PSI, KSI = 0.006894757, 6.894757
    v_prof = co.velocidades([{"fecha": "2009-06-01", "espesor_mm": 0.318 * IN}, {"fecha": "2010-06-01", "espesor_mm": 0.302 * IN},
                             {"fecha": "2015-06-01", "espesor_mm": 0.255 * IN}, {"fecha": "2020-06-01", "espesor_mm": 0.200 * IN}])
    rl = co.vida_remanente(0.200 * IN, 0.03225 * IN, 0.011 * IN)
    r_rbi = rbi.df_adelgazamiento(cr=0.3656, edad=10.0, t_rdi=16, t_min=9.672, S=137.9, E=0.85, YS=262.0, TS=482.6,
                                  confianza="media", inspecciones={"B": 2})
    return [
        ("Tubería", "t presión B31.3 ec. (3a)", "Ejercicio clase 05: NPS 8 (D = 8,625 in), A53 B, S = 20 ksi, P = 150 psig, E = W = 1, Y = 0,4",
         "B31.3 §304.1.2", 0.03225 * IN, es.tuberia_b313(150 * PSI, 8.625 * IN, 20 * KSI)["valor"], "mm"),
        ("Tubería", "CR corto plazo", "UT 2015 = 0,255 in; 2020 = 0,200 in", "API 570 §7.1.1", 0.011 * IN, v_prof["cr_cp"], "mm/año"),
        ("Tubería", "CR largo plazo", "UT 2009 = 0,318 in; 2020 = 0,200 in", "API 570 §7.1.1", 0.118 / 11 * IN, v_prof["cr_lp"], "mm/año"),
        ("Tubería", "Vida remanente", "t = 0,200 in, t_min = 0,03225 in, CR = 0,011 in/año", "API 570 §7.1.1", 15.25, rl, "años"),
        ("Tubería", "Intervalo Clase 1", "RL/2 = 7,6 años > máx. 5 años", "API 570 Tabla 6.3.3", 5.0, ins.intervalo("tuberia", rl, 1)[0], "años"),
        ("Recipiente", "t UG-27(c)(1)", "P = 1,5 MPa, R = 750 mm, S = 20 ksi, E = 0,85", "ASME VIII-1 UG-27",
         9.6723, es.recipiente_ug27(1.5, 750, 20 * KSI, 0.85)["valor"], "mm"),
        ("Recipiente", "Intervalo API 510", "RL = 12 años → RL/2", "API 510 §7.1.1", 6.0, ins.intervalo("recipiente", 12)[0], "años"),
        ("Tanque", "td API 650 virola 1", "D = 20 m, H = 12 m, G = 0,85, Sd = 137 MPa, CA = 1,5 mm", "API 650 §5.6.3.2",
         8.6139, es.tanque_api650_diseno(20, 12, 0.85, 137, 1.5)["valor"], "mm"),
        ("Tanque", "t_min API 653 virola 1", "S = mín(0,8·205; 0,429·380) = 163,02 MPa", "API 653 §4.3.3.1",
         5.9785, es.tanque_api653_tmin(20, 12, 0.85, 205, 380)["valor"], "mm"),
        ("RBI", "Posterior Po₁", "Confianza media, 2 inspecciones B", "API 581 ec. 2.16–2.17", 0.97443, r_rbi["pasos"]["Po"][0], "—"),
        ("RBI", "D_f adelgazamiento", "CR = 0,3656 mm/año, age = 10 años, t = 16 mm, t_min = 9,672 mm, SA-516-70, E = 0,85",
         "API 581 ec. 2.12–2.20", 16.0315, r_rbi["Df"], "—"),
        ("RBI", "R_A con C_A = 120 m²", "P_f = 3,06·10⁻⁵ · 1 · D_f", "API 581 Parte 1 §4.1", 0.058868,
         rbi.riesgo(r_rbi["Df"], 120, 450000)["R_A"], "m²/año"),
    ]


def vista_validacion():
    h = ['<div class="card"><h2>Comparación independiente</h2>'
         '<p class="muted">“Esperado” = cálculo manual/planilla del grupo (incluye el ejercicio de la clase 05). '
         '“Programa” = resultado de las mismas funciones que usa la aplicación, ejecutadas ahora en el navegador. Tolerancia: 0,5 %.</p>'
         '<table><tr><th>Familia</th><th>Cálculo</th><th>Entradas</th><th>Referencia</th><th class="num">Esperado</th>'
         '<th class="num">Programa</th><th class="num">Dif.</th><th></th></tr>']
    for fam, nom, ent, ref, esp, prog, u in casos_validacion():
        dif = abs(prog - esp) / abs(esp) * 100 if esp else 0
        ok = '<span class="ok">OK</span>' if dif <= 0.5 else '<span class="fail">REVISAR</span>'
        h.append(f'<tr><td>{fam}</td><td>{nom}</td><td class="muted">{ent}</td><td>{ref}</td>'
                 f'<td class="num">{f(esp, 4)} {u}</td><td class="num">{f(prog, 4)} {u}</td><td class="num">{f(dif, 2)} %</td><td>{ok}</td></tr>')
    h.append('</table></div><div class="card"><h2>Casos de condición en el caso demostrativo</h2><table>'
             '<tr><th>Condición</th><th>CML</th><th>Por qué</th></tr>'
             f'<tr><td>{badge("normal")}</td><td>CML-101-01, CML-201-01/02, CML-301-01/02</td><td>t actual sobre t_alerta y fecha vigente</td></tr>'
             f'<tr><td>{badge("alerta")}</td><td>CML-101-02</td><td>t_min &lt; t &lt; t_min + CR·2 años</td></tr>'
             f'<tr><td>{badge("bajo_minimo")}</td><td>CML-201-03</td><td>9,5 mm &lt; t_min 9,67 mm</td></tr>'
             f'<tr><td>{badge("vencida")}</td><td>CML-101-04 (ejercicio clase)</td><td>Próxima inspección (2024) anterior a hoy</td></tr>'
             f'<tr><td>{badge("insuficiente")}</td><td>CML-101-03, CML-301-03</td><td>Spool reemplazado (serie reiniciada) / CML nuevo con 1 lectura</td></tr>'
             '</table></div>')
    return "".join(h)


# ------------------------------------------------------------------ alcance
def vista_acerca():
    return '''<div class="card"><h2>Alcance, supuestos y referencias</h2>
<table><tr><th>Familia</th><th>Diseño / construcción</th><th>En servicio</th><th>Geometría</th><th>Material(es)</th></tr>
<tr><td>Tubería de proceso</td><td>ASME B31.3-2018</td><td>API 570</td><td>Tramo recto</td><td>A106 Gr. B, A53 Gr. B</td></tr>
<tr><td>Recipiente a presión</td><td>ASME VIII-1 2019 + II-D 2019</td><td>API 510</td><td>Envolvente cilíndrica</td><td>SA-516 Gr. 70</td></tr>
<tr><td>Tanque atmosférico</td><td>API 650 12ª ed. (2013)</td><td>API 653</td><td>Virolas del manto (1 pie)</td><td>A283 Gr. C, A36</td></tr></table>
<h3>Supuestos y limitaciones</h3><ul>
<li>Rango de temperatura del catálogo: hasta 260 °C (500 °F) para tubería y recipiente; tanques a temperatura ambiente.</li>
<li>Unidades internas SI (mm, MPa, m). Mediciones en pulgadas se convierten (1 in = 25,4 mm).</li>
<li>CR adoptada = mayor entre largo y corto plazo (criterio conservador). Para RBI se usa la CR de largo plazo (API 581 §4.5.2).</li>
<li>Un reemplazo, reparación o cambio de punto reinicia la serie comparable de mediciones.</li>
<li>Intervalos limitados a la próxima medición de espesores. Tanques: solo manto; fondo, techo e inspección interna quedan como datos pendientes.</li>
<li>RBI: modelo académico simplificado, solo adelgazamiento generalizado, recipiente V-201. Consecuencias ingresadas por el usuario.</li>
<li>Datos del caso demostrativo: ficticios.</li></ul>
<h3>Referencias</h3><ul>
<li>ASME B31.3-2018 Process Piping, §304.1.2, Tablas A-1, A-1A, 302.3.5, 304.1.1.</li>
<li>ASME BPVC Sección VIII Div. 1 (2019), UG-27. ASME BPVC Sección II Parte D (2019), Tabla 1A.</li>
<li>API 650 12ª ed. (2013), §5.6.3, Tabla 5.2a. API 653 §4.3.3, §6.3. API 510 §7.1. API 570 §6.3, §7.1.</li>
<li>API RP 580 3ª ed. (2016). API RP 581 3ª ed. (2016) + Adenda 2 (2020): Parte 1 §4; Parte 2 §3–4.</li>
<li>Apuntes MAN040-B, Prof. A. Badilla: clases 01–06.</li></ul>
<h3>Herramientas</h3><p>Python (PyScript/Pyodide, NumPy, pandas, Matplotlib), HTML/CSS, pytest, Git/GitHub Pages, VS Code y asistente de IA en modo agente
(apoyo en programación y revisión; los cálculos fueron verificados por el grupo con los casos de la pestaña Validación).</p></div>'''
