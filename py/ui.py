"""Generación de HTML para cada vista. No toca el DOM: recibe datos y devuelve texto HTML."""
import base64
import html
import io
import re
from datetime import date

from calc import corrosion as co
from calc import espesores as es
from calc import inspeccion as ins
from calc import rbi
from calc.materiales import MATERIALES, esfuerzo_admisible
from calc.normas import EDICION

FAMILIAS = {"tuberia": "Tubería de proceso", "recipiente": "Recipiente a presión", "tanque": "Tanque atmosférico"}
CONDICION = {"normal": "Normal", "alerta": "Alerta", "bajo_minimo": "Bajo el mínimo",
             "vencida": "Inspección vencida", "insuficiente": "Información insuficiente", "error": "Error de datos"}
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


COLOR = {"normal": "#0ca30c", "alerta": "#fab219", "bajo_minimo": "#d03b3b", "vencida": "#ec835a",
         "insuficiente": "#898781", "error": "#52514e"}
ICONO = {"normal": "●", "alerta": "▲", "bajo_minimo": "✕", "vencida": "◷", "insuficiente": "?", "error": "!"}


def esc(x):
    return html.escape("" if x is None else str(x))


def f(x, n=2, unidad=""):
    if x is None:
        return "—"
    if isinstance(x, float) and (abs(x) >= 1e5 or (0 < abs(x) < 1e-3)):
        s = f"{x:.2e}".replace(".", ",")
    else:
        s = f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} {unidad}".strip()


def sci(x):
    """Frecuencias y probabilidades: notación científica legible (6,29·10⁻³)."""
    if x is None:
        return "—"
    if x == 0:
        return "0"
    m, e = f"{x:.2e}".split("e")
    sup = str(int(e)).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"{m.replace('.', ',')}·10{sup}"


def badge(cond, texto=None):
    return (f'<span class="badge" style="--c:{COLOR.get(cond, "#888")}"><i>{ICONO.get(cond, "")}</i>'
            f'{texto or CONDICION.get(cond, cond)}</span>')


def vin(v):
    """Valor numérico para un atributo value= (sin '.0' sobrante), escapado."""
    if isinstance(v, float):
        return esc(f"{v:.10g}")
    return esc(v)


def pct(v):
    """Coordenada en % saneada para usar dentro de style (evita inyección CSS)."""
    try:
        return f"{min(max(float(v), 0.0), 100.0):.2f}"
    except (TypeError, ValueError):
        return "50.00"


def opciones_material(familia, actual=None):
    return "".join(f'<option value="{esc(k)}" {"selected" if k == actual else ""}>{esc(v["nombre"])}</option>'
                   for k, v in MATERIALES.items() if v["familia"] == familia)


_RE_SUB = re.compile(r"(?<![\w&#])([A-Za-zΔ]{1,3})_([A-Za-z0-9áéíóúñÁÉÍÓÚ]{1,12})(?!\w)")
_RE_TAG = re.compile(r"(<[^>]*>)")


def subindices(html_txt):
    """Muestra 't_min' como t<sub>min</sub> en el texto visible (nunca dentro de etiquetas ni atributos)."""
    partes = _RE_TAG.split(html_txt)
    for i in range(0, len(partes), 2):
        if "_" in partes[i]:
            partes[i] = _RE_SUB.sub(r"\1<sub>\2</sub>", partes[i])
    return "".join(partes)


def prox_txt(x):
    """Texto de la próxima inspección: 'Inmediata' si el CML está bajo el mínimo (H7)."""
    return x.get("proxima_txt") or fecha_cl(x.get("proxima"))


def calc_tmin(x):
    """Tarjeta del espesor mínimo en servicio con la ecuación que realmente lo gobierna (H4)."""
    tc = x["espesores"].get("tmin_calc")
    if tc:
        return calc("Mínimo en servicio (t_min)", f(x["t_min"], 3, "mm"), tc["ecuacion"], tc["entradas"], tc["ref"])
    return calc_r("Mínimo en servicio (t_min)", x["espesores"], valor=x["t_min"])


ORDEN_COND = {"bajo_minimo": 0, "error": 0, "vencida": 1, "alerta": 2, "insuficiente": 3, "normal": 4}


def cml_gobernante(eq, res_eq):
    """CML más crítico: peor condición, luego menor vida remanente, luego menor espesor (H3, H6)."""
    cands = [(c, res_eq["cmls"][c["id"]]) for c in eq["cmls"] if c["id"] in res_eq["cmls"]]
    if not cands:
        return None, None
    def clave(par):
        c, x = par
        return (ORDEN_COND.get(x["condicion"], 5), x["rl"] if x["rl"] is not None else 1e9,
                x["corrosion"]["t_actual"] if x["corrosion"]["t_actual"] is not None else 1e9)
    c, x = min(cands, key=clave)
    motivo = {"bajo_minimo": "bajo el mínimo", "vencida": "inspección vencida", "alerta": "en alerta"}.get(
        x["condicion"], "menor vida remanente")
    return c, motivo


def fecha_cl(iso):
    if not iso:
        return "—"
    if not re.match(r"^\d{4}-\d{2}-\d{2}", str(iso)):
        return esc(iso)
    a, m, d = iso[:10].split("-")
    return f"{d}-{m}-{a}"


def stat(label, valor, unidad="", sub="", clase=""):
    u = f"<small>{unidad}</small>" if unidad else ""
    s = f'<div class="s">{sub}</div>' if sub else ""
    return f'<div class="stat {clase}"><div class="l">{label}</div><div class="v">{valor}{u}</div>{s}</div>'


def plegable(titulo, cuerpo, abierto=False):
    return f'<details {"open" if abierto else ""}><summary>{titulo}</summary><div class="cuerpo">{cuerpo}</div></details>'


def calc(titulo, resultado, ecuacion="", entradas=None, ref="", avisos=()):
    ent = ""
    if entradas:
        ent = '<div class="ent">' + " · ".join(
            f"{esc(k)} = {f(v, 3) if isinstance(v, (int, float)) else esc(v)}" for k, v in entradas.items()) + "</div>"
    ec = f'<div class="ec">{esc(ecuacion)}</div>' if ecuacion else ""
    rf = f'<div class="ref">{esc(ref)}</div>' if ref else ""
    av = "".join(f'<div class="aviso">⚠ {esc(a)}</div>' for a in avisos)
    return f'<div class="calc"><div class="tit"><b>{esc(titulo)}</b><span class="res">{resultado}</span></div>{ec}{ent}{rf}{av}</div>'


def calc_r(titulo, r, unidad="mm", n=3, valor=None):
    v = r["valor"] if valor is None else valor
    return calc(titulo, f(v, n, unidad), r.get("ecuacion", ""), r.get("entradas"), r.get("ref", ""), r.get("avisos", ()))


# ------------------------------------------------------------------ evaluación
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
def sidebar(data, res, sel_id, filtros=None):
    """Estructura de planta (Planta › Área › Sistema › Equipo). Los filtros viven junto a la tabla de Planta."""
    h = ['<div class="lateral-cab"><span>Equipos</span>'
         '<button data-act="nuevo_eq" class="secundario chico" title="Registrar un equipo nuevo">+ Nuevo</button></div>']
    arbol = {}
    for e in data["equipos"]:
        u = e["ubicacion"]
        arbol.setdefault(u["planta"], {}).setdefault(u["area"], {}).setdefault(u["sistema"], []).append(e)
    h.append('<ul class="arbol">')
    for planta, areas_ in arbol.items():
        h.append(f'<li><div class="nodo nodo-planta">{esc(planta)}</div><ul>')
        for area, sistemas in areas_.items():
            h.append(f'<li><div class="nodo">{esc(area)}</div><ul>')
            for sist, eqs in sistemas.items():
                h.append(f'<li><div class="nodo nodo-sistema">{esc(sist)}</div>')
                for e in eqs:
                    cond = res[e["id"]]["cond"]
                    act = "activo" if e["id"] == sel_id else ""
                    h.append(f'<div class="eq-item {act}" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(e["id"])}" '
                             f'title="{CONDICION[cond]}" aria-label="{esc(e["tag"])}, {CONDICION[cond]}">'
                             f'<span class="punto" style="background:{COLOR[cond]}"></span>{esc(e["tag"])}'
                             f'<small>{FAMILIAS[e["familia"]].split()[0]}</small></div>')
                h.append('</li>')
            h.append('</ul></li>')
        h.append('</ul></li>')
    h.append('</ul>')
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


# ------------------------------------------------------------------ plano de planta
BOCETO = {
    "tuberia": '<svg viewBox="0 0 140 100" aria-hidden="true">'
               '<path d="M8 66H92V30H132" fill="none" stroke="currentColor" stroke-width="12" stroke-linejoin="round"/>'
               '<path d="M8 66H92V30H132" fill="none" stroke="var(--sup)" stroke-width="8" stroke-linejoin="round"/>'
               '<path d="M40 58v16M66 58v16M106 22v16" stroke="currentColor" stroke-width="3"/>'
               '<path d="M30 74v16M74 74v16M22 90h16M66 90h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    "recipiente": '<svg viewBox="0 0 140 100" aria-hidden="true">'
                  '<path d="M52 24Q52 8 70 8T88 24V72Q88 88 70 88T52 72Z" fill="var(--sup)" stroke="currentColor" stroke-width="2.5"/>'
                  '<path d="M52 42h36M52 58h36" stroke="currentColor" stroke-width="1" stroke-dasharray="3 3"/>'
                  '<path d="M70 8V1M28 34h24M88 66h22M58 85l-4 13M82 85l4 13M48 98h12M80 98h12" stroke="currentColor" '
                  'stroke-width="2.5" stroke-linecap="round"/></svg>',
    "tanque": '<svg viewBox="0 0 140 100" aria-hidden="true">'
              '<path d="M18 36L70 16L122 36V90H18Z" fill="var(--sup)" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/>'
              '<path d="M18 36h104M18 54h104M18 72h104" stroke="currentColor" stroke-width="1"/>'
              '<path d="M28 90L60 36" stroke="currentColor" stroke-width="2"/><path d="M34 90L66 36" stroke="currentColor" stroke-width="1" '
              'stroke-dasharray="2 4"/><path d="M6 92h128" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>',
}
AVISO = ("bajo_minimo", "vencida", "alerta")
TRIANGULO = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3L2 21h20Z" fill="currentColor"/>'
             '<path d="M12 10v5M12 18v.5" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg>')


def ficha_plano(e, r):
    """Pop-up de un equipo en el plano: condición de cada CML y accesos directos."""
    orden = {"bajo_minimo": 0, "vencida": 1, "alerta": 2, "insuficiente": 3, "normal": 4}
    cmls = sorted(e["cmls"], key=lambda c: orden.get(r["cmls"].get(c["id"], {}).get("condicion"), 5))
    filas = []
    for c in cmls:
        x = r["cmls"].get(c["id"])
        if not x:
            continue
        cond = x["condicion"]
        filas.append(f'<li><button class="pl-cml" data-act="sel_eq" data-id="{esc(e["id"])}" data-cml="{esc(c["id"])}">'
                     f'<span class="punto" style="background:{COLOR[cond]}"></span><span class="pl-cml-id"><b>{esc(c["id"])}</b>'
                     f'<small>{esc(c["componente"])}</small></span><span class="pl-cml-v">{f(x["corrosion"]["t_actual"])} / '
                     f'{f(x["t_min"])} mm<small>{CONDICION[cond]}</small></span></button></li>')
    vacio = '' if filas else '<li class="muted">Sin CML registrados.</li>'
    return (f'<div class="pl-pop" role="dialog" aria-label="Detalle de {esc(e["tag"])}">'
            f'<div class="pl-pop-cab"><b>{esc(e["tag"])}</b>{badge(r["cond"])}</div>'
            f'<div class="muted pl-pop-desc">{FAMILIAS[e["familia"]]} · {esc(e["descripcion"])}</div>'
            f'<div class="pl-pop-tit"><span>CML</span><span>t actual / t mín</span></div><ul>{"".join(filas)}{vacio}</ul>'
            f'<button class="pl-abrir" data-act="sel_eq" data-id="{esc(e["id"])}">Abrir equipo ›</button></div>')


def plano(data, res, filtros):
    """Plano esquemático (sin escala) de la planta: áreas › sistemas › equipos, con avisos por condición."""
    visibles = {e["id"] for e in filtrar(data, res, filtros)}
    arbol = {}
    for e in data["equipos"]:
        u = e["ubicacion"]
        arbol.setdefault(u["area"], {}).setdefault(u["sistema"], []).append(e)
    areas = []
    for area in sorted(arbol):
        sistemas, n_av = [], 0
        for sist, eqs in arbol[area].items():
            tiles = []
            for e in eqs:
                r = res[e["id"]]
                cond = r["cond"]
                malos = [x["condicion"] for x in r["cmls"].values() if x["condicion"] in AVISO]
                n_av += len(malos)
                aviso = ""
                if malos:
                    peor = min(malos, key=AVISO.index)
                    det = ", ".join(f"{CONDICION[k].lower()} ({malos.count(k)})" for k in AVISO if k in malos)
                    aviso = (f'<span class="pl-aviso" style="--c:{COLOR[peor]}" title="{len(malos)} CML requieren atención: {det}">'
                             f'{TRIANGULO}{len(malos)}</span>')
                puntos = "".join(f'<span class="punto" style="background:{COLOR[x["condicion"]]}" '
                                 f'title="{esc(cid)} · {CONDICION[x["condicion"]]}"></span>' for cid, x in r["cmls"].items())
                aria = f'{e["tag"]}, {FAMILIAS[e["familia"]]}, {CONDICION[cond]}' + (f', {len(malos)} avisos' if malos else '')
                clases = "pl-eq" + (" con-aviso" if malos else "") + ("" if e["id"] in visibles else " atenuado")
                tiles.append(f'<div class="{clases}" tabindex="0" data-eq="{esc(e["id"])}" style="--c:{COLOR[cond]}" '
                             f'aria-label="{esc(aria)}" aria-haspopup="dialog">'
                             f'{aviso}<div class="pl-boceto">{BOCETO[e["familia"]]}</div>'
                             f'<div class="pl-tag"><span class="punto" style="background:{COLOR[cond]}"></span>{esc(e["tag"])}</div>'
                             f'<div class="pl-puntos">{puntos}</div>{ficha_plano(e, r)}</div>')
            sistemas.append(f'<div class="pl-sist"><span class="pl-sist-nom">{esc(sist)}</span>'
                            f'<div class="pl-eqs">{"".join(tiles)}</div></div>')
        n_eq = sum(len(v) for v in arbol[area].values())
        av = f'<span class="pl-area-av">{TRIANGULO}{n_av}</span>' if n_av else ''
        sel = " sel" if filtros.get("area") == area else ""
        areas.append(f'<section class="pl-area{sel}"><button class="pl-area-cab" data-act="ir_area" data-area="{esc(area)}" '
                     f'title="Filtrar la tabla por esta área"><span>{esc(area)}<small>{n_eq} equipo(s)</small></span>{av}</button>'
                     f'{"".join(sistemas)}</section>')
    leyenda = "".join(f'<span><span class="punto" style="background:{COLOR[k]}"></span>{CONDICION[k]}</span>'
                      for k in ("normal", "alerta", "vencida", "bajo_minimo", "insuficiente"))
    return ('<div class="card"><div class="card-cab"><h2>Plano de planta</h2>'
            '<span class="muted">Esquema sin escala · selecciona un equipo para ver sus CML</span></div>'
            f'<div class="plano"><span class="pl-norte" aria-hidden="true">N<br>↑</span>{"".join(areas)}</div>'
            f'<div class="pl-leyenda">{leyenda}<span><span class="pl-aviso mini" style="--c:{COLOR["alerta"]}">{TRIANGULO}</span>'
            'Aviso: CML en alerta, vencido o bajo el mínimo</span></div></div>')


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
                          "RL [años]": x["rl"], "Próxima inspección": x.get("proxima_txt") or x["proxima"], "Condición": x["condicion"],
                          "_eq": e["id"], "_cml": c["id"]})
    return filas


def panel(data, res, filtros):
    orden = {"bajo_minimo": 0, "error": 0, "vencida": 1, "alerta": 2, "insuficiente": 3, "normal": 4}
    filas = sorted(filas_panel(data, res, filtros), key=lambda fl: (orden.get(fl["Condición"], 5), fl.get("RL [años]") or 1e9))
    cuenta = {k: 0 for k in ["normal", "alerta", "bajo_minimo", "vencida", "insuficiente"]}
    for fl in filas:
        if fl["Condición"] in cuenta:
            cuenta[fl["Condición"]] += 1
    n_eq = len({fl["_eq"] for fl in filas})
    areas = sorted({e["ubicacion"]["area"] for e in data["equipos"]})

    def opts(valores, actual, todos):
        return f'<option value="">{todos}</option>' + "".join(
            f'<option value="{esc(v)}" {"selected" if v == actual else ""}>{esc(t)}</option>' for v, t in valores)

    activos = any(filtros.values())
    barra = ('<div class="filtros" role="group" aria-label="Filtros">'
             f'<select data-act="filtro" data-campo="area" aria-label="Área">{opts([(x, x) for x in areas], filtros.get("area"), "Todas las áreas")}</select>'
             f'<select data-act="filtro" data-campo="familia" aria-label="Familia">{opts(FAMILIAS.items(), filtros.get("familia"), "Todas las familias")}</select>'
             f'<select data-act="filtro" data-campo="cond" aria-label="Condición">{opts(CONDICION.items(), filtros.get("cond"), "Todas las condiciones")}</select>'
             + ('<button class="chico secundario" data-act="limpiar_filtros">Limpiar filtros</button>' if activos else '')
             + '</div>')
    h = ['<div class="cabecera"><h1>Estado de la planta</h1>'
         '<span class="desc">Plano por áreas y puntos de monitoreo, del más grave al menos grave</span></div>',
         '<div class="stats">', stat("Equipos", n_eq, sub=f"{len(filas)} CML" + (" (filtrado)" if activos else ""), clase="destacado")]
    for k, n in cuenta.items():
        h.append(f'<div class="stat estado" style="--c:{COLOR[k]}"><div class="l">{CONDICION[k]}</div>'
                 f'<div class="v"><span style="color:{COLOR[k]}">{ICONO[k]}</span>{n}</div></div>')
    h.append('</div>' + plano(data, res, filtros))
    h.append(f'<div class="card"><div class="card-cab"><h2>Puntos de monitoreo (CML)</h2>{barra}</div>'
             '<table><tr><th>Equipo</th><th>CML</th><th>Componente</th><th class="num">t actual [mm]</th>'
             '<th class="num">t mín [mm]</th><th class="num">CR [mm/año]</th><th class="num">RL [años]</th><th>Próxima</th><th>Condición</th></tr>')
    for fl in filas:
        h.append(f'<tr class="click" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(fl["_eq"])}" data-cml="{esc(fl["_cml"] or "")}">'
                 f'<td><b>{esc(fl["Equipo"])}</b><div class="muted">{esc(fl["Familia"])}</div></td><td>{esc(fl["CML"])}</td>'
                 f'<td>{esc(fl.get("Componente", ""))}</td><td class="num">{f(fl.get("t_actual [mm]"))}</td>'
                 f'<td class="num">{f(fl.get("t_min [mm]"))}</td><td class="num">{f(fl.get("CR [mm/año]"), 3)}</td>'
                 f'<td class="num">{f(fl.get("RL [años]"), 1)}</td><td>{fecha_cl(fl.get("Próxima inspección"))}</td>'
                 f'<td>{badge(fl["Condición"])}</td></tr>')
    if not filas:
        h.append('<tr><td colspan="9" class="muted">Ningún CML coincide con los filtros.</td></tr>')
    h.append('</table><div class="muted" style="margin-top:8px">Ordenado por severidad. Clic en una fila para abrir el equipo.</div></div>')
    return "".join(h)


# ------------------------------------------------------------------ CML
def calculos_cml(eq, c, x):
    v = x["corrosion"]
    h = [calc_tmin(x)]
    if x["espesores"].get("tmin_calc"):
        h.append(calc("t presión (B31.3 ec. 3a)", f(x["espesores"]["valor"], 3, "mm"), x["espesores"]["ecuacion"],
                      x["espesores"]["entradas"], x["espesores"]["ref"]))
    if v["cr_lp"] is not None:
        h.append(calc("CR largo plazo", f(v["cr_lp"], 3, "mm/año"), "CR_LP = (t_inicial − t_actual) / Δt",
                      {"t_inicial": v["t_inicial"], "t_actual": v["t_actual"], "Δt [años]": v["dt_lp"]}, x["ref_corrosion"]))
        h.append(calc("CR corto plazo", f(v["cr_cp"], 3, "mm/año"), "CR_CP = (t_previo − t_actual) / Δt",
                      {"t_previo": v["t_previo"], "t_actual": v["t_actual"], "Δt [años]": v["dt_cp"]}, x["ref_corrosion"]))
        h.append(calc("CR adoptada", f(v["cr"], 3, "mm/año"), "CR = máx(CR_LP; CR_CP)", None, v["criterio"] or ""))
    h.append(calc("Vida remanente", f(x["rl"], 2, "años"), "RL = (t_actual − t_min) / CR", None, x["ref_corrosion"]))
    h.append(calc_r("Espesor de alerta", x["alerta"]))
    h.append(calc("Intervalo de inspección", f(x["intervalo"], 2, "años"), x["criterio"], None, x["ref_intervalo"]))
    return "".join(h)


def _mas_anios(iso, anios):
    """Fecha ISO + años (float) → fecha ISO; None si no aplica."""
    if not iso or anios is None or anios < 0 or anios > 300:
        return None
    return date.fromordinal(date.fromisoformat(iso).toordinal() + round(anios * 365.25)).isoformat()


def ficha_cml(eq, c, x):
    """Especificaciones del CML: identificación, historial, degradación y proyección."""
    v = x["corrosion"]
    ms = sorted(c.get("mediciones", []), key=lambda m: m["fecha"])
    t_act, t_min, t_al, cr = v["t_actual"], x["t_min"], x["t_alerta"], v["cr"]
    t_ini = v["t_inicial"] if v["t_inicial"] is not None else (ms[0]["espesor_mm"] if ms else None)
    ident = [("Componente", esc(c["componente"])), ("Ubicación", esc(c["ubicacion"])),
             ("t nominal", f(c.get("t_nom_mm") or eq["t_nom_mm"], 2, "mm"))]
    dl = c.get("diseno_local") or {}
    if eq["familia"] == "tanque":
        ident.append(("Virola · nivel H", f'N° {esc(dl.get("virola", "—"))} · {f(dl.get("H_m"), 2, "m")}'))
    ident.append(("Posición en esquema", f'x {f(float(pct(c["x"])), 0)} % · y {f(float(pct(c["y"])), 0)} %'))
    hist = [("Mediciones", f'{len(ms)} registradas · {v["n"]} comparables'),
            ("Primera / última", f'{fecha_cl(ms[0]["fecha"]) if ms else "—"} → {fecha_cl(ms[-1]["fecha"]) if ms else "—"}'),
            ("Técnica (última)", esc(ms[-1].get("tecnica")) if ms else "—")]
    deg = []
    if t_ini is not None and t_act is not None:
        perdida = t_ini - t_act
        deg.append(("Pérdida acumulada", f'{f(perdida)} mm ({f(perdida / t_ini * 100, 1)} % de t inicial)' if t_ini else "—"))
        if t_ini > t_min:
            uso = min(max(perdida / (t_ini - t_min) * 100, 0), 999)
            color = COLOR["bajo_minimo"] if uso >= 100 else COLOR["alerta"] if uso >= 70 else COLOR["normal"]
            deg.append(("Margen consumido",
                        f'<span class="medidor" style="--p:{min(uso, 100):.0f}%;--c:{color}" title="Pérdida / (t inicial − t mín)"><i></i></span>'
                        f'{f(uso, 0)} %'))
    if t_act is not None:
        deg.append(("Margen sobre t mín", f'<b class="{"fail" if t_act < t_min else ""}">{f(t_act - t_min)} mm</b>'))
    deg.append(("CR largo / corto plazo", f'{f(v["cr_lp"], 3)} / {f(v["cr_cp"], 3)} mm/año'))
    deg.append(("CR adoptada", f'{f(cr, 3)} mm/año' + (f' <span class="muted">· {esc(v["criterio"])}</span>' if v["criterio"] else "")))
    proy = []
    if t_act is not None and cr and cr > 0:
        f_al = "ya alcanzado" if t_act <= t_al else fecha_cl(_mas_anios(v["fecha_actual"], (t_act - t_al) / cr))
        f_min = "ya alcanzado" if t_act < t_min else fecha_cl(_mas_anios(v["fecha_actual"], x["rl"]))
        proy += [("Llega a t alerta", f_al), ("Llega a t mín (fin de vida)", f_min)]
    else:
        proy.append(("Proyección", '<span class="muted">requiere CR &gt; 0 (≥ 2 mediciones comparables)</span>'))
    proy.append(("Intervalo", f'{f(x["intervalo"], 1, "años")} <span class="muted">· {esc(x["ref_intervalo"])}</span>'
                 if x["intervalo"] is not None else "—"))
    proy.append(("Próxima inspección", f'<b>{prox_txt(x)}</b>'))

    def bloque(titulo, filas):
        return (f'<div><h3>{titulo}</h3><dl class="kv-col">'
                + "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in filas) + "</dl></div>")
    return (f'<h2>Especificaciones de {esc(c["id"])}</h2><div class="ficha-grid">' + bloque("Identificación", ident)
            + bloque("Historial", hist) + bloque("Degradación", deg) + bloque("Proyección", proy) + '</div>')


def vista_cml(eq, c, x):
    v = x["corrosion"]
    h = [f'<div class="cabecera" style="margin-top:6px"><h2 style="margin:0">{esc(c["id"])}</h2>'
         f'<span class="desc">{esc(c["componente"])} · {esc(c["ubicacion"])}</span>{badge(x["condicion"])}</div>',
         '<div class="stats">',
         stat("t actual", f(v["t_actual"]), "mm", fecha_cl(v["fecha_actual"])),
         stat("t mínimo", f(x["t_min"]), "mm", "servicio"),
         stat("t alerta", f(x["t_alerta"]), "mm", "t_min + CR·2 años"),
         stat("Corrosión", f(v["cr"], 3), "mm/año", "adoptada"),
         stat("Vida remanente", f(x["rl"], 1), "años"),
         stat("Próxima inspección", prox_txt(x), "", "evaluar FFS / reparar" if x.get("proxima_txt") else f"intervalo {f(x['intervalo'], 1)} años", "destacado"),
         '</div>']
    for p in v["problemas"]:
        h.append(f'<div class="error">✕ {esc(p)}</div>')
    if eq["familia"] == "tanque":
        h.append('<div class="info">Alcance API 653: solo espesores del manto. Fondo, techo e inspección interna: datos pendientes.</div>')
    h.append(f'<div class="grid-cml"><div class="card grafico">{grafico(eq, c, x)}</div>'
             f'<div class="card"><h2>Nueva medición</h2>{form_medicion(c)}</div></div>')
    h.append(f'<div class="card ficha-cml">{ficha_cml(eq, c, x)}</div>')
    filas = []
    for i, m in sorted(enumerate(c.get("mediciones", [])), key=lambda t: t[1]["fecha"], reverse=True):
        orig = f' <span class="muted">({m["espesor_mm"] / IN:.3f} in)</span>' if m.get("unidad") == "in" else ""
        ev = badge("bajo_minimo", EVENTOS[m["evento"]]) if m.get("evento") else ""
        filas.append(f'<tr><td>{fecha_cl(m["fecha"])}</td><td class="num"><b>{f(m["espesor_mm"], 2)}</b>{orig}</td>'
                     f'<td>{esc(m.get("tecnica"))}</td><td>{ev} {esc(m.get("observaciones"))}</td>'
                     f'<td class="num"><button class="chico peligro" data-act="del_med" data-i="{i}" title="Eliminar medición" '
                     f'aria-label="Eliminar medición del {fecha_cl(m["fecha"])}">✕</button></td></tr>')
    tabla = ('<table><tr><th>Fecha</th><th class="num">Espesor [mm]</th><th>Técnica</th><th>Observaciones</th><th></th></tr>'
             + ("".join(filas) or '<tr><td colspan="5" class="muted">Sin mediciones. Registra la primera en «Nueva medición».</td></tr>')
             + '</table>')
    h.append(f'<div class="card"><h2>Historial de mediciones ({len(filas)})</h2>{tabla}</div>')
    h.append(plegable("Ver cálculos (ecuaciones, entradas y referencias)", calculos_cml(eq, c, x)))
    pos = ('<form class="f" id="form_xy">'
           f'<label>x [%]<input type="number" step="any" name="x" value="{pct(c["x"])}" min="0" max="100"></label>'
           f'<label>y [%]<input type="number" step="any" name="y" value="{pct(c["y"])}" min="0" max="100"></label>'
           '<button data-act="mover_cml" class="secundario">Mover marcador</button>'
           '<button data-act="borrar_cml" class="peligro">Eliminar CML</button></form>')
    h.append(plegable("Posición del marcador y opciones del CML", pos))
    return "".join(h)


def form_medicion(c):
    hoy = date.today().isoformat()
    tec = "".join(f"<option>{t}</option>" for t in TECNICAS)
    ev = "".join(f'<option value="{k}">{v}</option>' for k, v in EVENTOS.items())
    return (f'<form class="f col" id="form_med">'
            f'<label>Fecha<input type="date" name="fecha" value="{hoy}" required></label>'
            f'<label>Técnica<select name="tecnica">{tec}</select></label>'
            f'<label>Espesor<input type="number" step="0.001" name="espesor" placeholder="0,00" required></label>'
            f'<label>Unidad<select name="unidad"><option>mm</option><option>in</option></select></label>'
            f'<label class="ancho">Evento<select name="evento">{ev}</select></label>'
            f'<label class="ancho">Observaciones<input name="observaciones"></label>'
            f'<button class="ancho" data-act="add_med">Agregar y recalcular</button></form>')


# ------------------------------------------------------------------ gráfico
def grafico(eq, c, x):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np

    TINTA, TINTA2, MUTED, GRID, SERIE, FONDO = "#1d1d1f", "#6e6e73", "#86868b", "#ececf0", "#1f7a4d", "#ffffff"
    ms = sorted(c.get("mediciones", []), key=lambda m: m["fecha"])
    serie, _ = co.serie_comparable(ms)
    claves = {(s["fecha"], s["espesor_mm"]) for s in serie}
    fig, ax = plt.subplots(figsize=(7.6, 3.5), dpi=110)
    fig.patch.set_facecolor(FONDO)
    ax.set_facecolor(FONDO)
    v = x["corrosion"]
    fechas = [date.fromisoformat(m["fecha"][:10]) for m in ms] or [date.today()]
    if x["proxima"]:
        fechas.append(date.fromisoformat(x["proxima"]))
    x_fin = max(fechas + [date.today()])

    def etiqueta(y, texto, color):
        ax.annotate(texto, (1.0, y), xycoords=("axes fraction", "data"), xytext=(10, 0), textcoords="offset points",
                    va="center", fontsize=8, color=TINTA2)
        ax.plot([1.0], [y], marker="s", ms=5, color=color, transform=ax.get_yaxis_transform(), clip_on=False)

    ax.axhline(x["t_min"], color="#d03b3b", lw=2, zorder=1)
    etiqueta(x["t_min"], f"t mín {x['t_min']:.2f} mm", "#d03b3b")
    if abs(x["t_alerta"] - x["t_min"]) > 0.05:
        ax.axhline(x["t_alerta"], color="#fab219", lw=2, ls=(0, (5, 3)), zorder=1)
    if abs(x["t_alerta"] - x["t_min"]) > 0.15:
        etiqueta(x["t_alerta"], f"t alerta {x['t_alerta']:.2f} mm", "#fab219")
    tn = c.get("t_nom_mm")
    if tn:
        ax.axhline(tn, color=MUTED, lw=1, ls=(0, (1, 2)), zorder=1)
        etiqueta(tn, f"t nom {tn:.2f} mm", MUTED)
    if v["cr"] and v["fecha_actual"] and x["rl"]:
        f0 = date.fromisoformat(v["fecha_actual"])
        anios = np.linspace(0, x["rl"], 20)
        fx = [date.fromordinal(f0.toordinal() + int(a * 365.25)) for a in anios]
        ax.plot(fx, v["t_actual"] - v["cr"] * anios, color=SERIE, lw=1.5, ls=(0, (4, 3)), alpha=.7, zorder=2)
        x_fin = max(x_fin, fx[-1])
    if ms:
        fx = [date.fromisoformat(m["fecha"][:10]) for m in ms]
        ty = [m["espesor_mm"] for m in ms]
        comp = [(a, b) for a, b, m in zip(fx, ty, ms) if (m["fecha"], m["espesor_mm"]) in claves]
        prev = [(a, b) for a, b, m in zip(fx, ty, ms) if (m["fecha"], m["espesor_mm"]) not in claves]
        if prev:
            ax.plot(*zip(*prev), color=MUTED, lw=1.5, marker="o", ms=6, mec=FONDO, mew=2, zorder=3)
        if comp:
            ax.plot(*zip(*comp), color=SERIE, lw=2, marker="o", ms=8, mec=FONDO, mew=2, zorder=4)
        for m, a, b in zip(ms, fx, ty):
            if m.get("evento"):
                ax.annotate(EVENTOS[m["evento"]], (a, b), xytext=(6, 8), textcoords="offset points", fontsize=8, color=TINTA2)
    if x["proxima"]:
        fp = date.fromisoformat(x["proxima"])
        ax.axvline(fp, color="#ec835a", lw=1.5, zorder=1)
        ax.annotate("Próx. insp.", (fp, 1.0), xycoords=("data", "axes fraction"), xytext=(-4, -2),
                    textcoords="offset points", fontsize=8, color=TINTA2, ha="right", va="top",
                    bbox=dict(boxstyle="square,pad=0.15", fc=FONDO, ec="none"))
    ax.axvline(date.today(), color=MUTED, lw=1, alpha=.6, zorder=1)
    ax.annotate("Hoy", (date.today(), 1.0), xycoords=("data", "axes fraction"), xytext=(-4, -14),
                textcoords="offset points", fontsize=8, color=MUTED, ha="right", va="top",
                bbox=dict(boxstyle="square,pad=0.15", fc=FONDO, ec="none"))
    ax.set_xlim(right=date.fromordinal(x_fin.toordinal() + 200))
    ax.set_ylabel("Espesor [mm]", fontsize=9, color=TINTA2)
    ax.set_title("Espesor vs tiempo", fontsize=10, color=TINTA, loc="left", fontweight="bold")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, lw=.8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return (f'<img alt="Espesor vs tiempo de {esc(c["id"])}" src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}">'
            '<div class="muted" style="margin-top:6px">● verde: serie comparable · ● gris: antes de reemplazo/reparación · '
            '- - - proyección con la CR adoptada</div>')


# ------------------------------------------------------------------ equipo
def ficha(eq):
    u = eq["ubicacion"]
    mat = MATERIALES.get(eq["material"], {})
    filas = [("Ubicación", f'{u["area"]} › {u["sistema"]}'), ("Servicio", eq["servicio"]), ("Fluido", eq["fluido"]),
             ("Material", mat.get("nombre", eq["material"])), ("Códigos", f'{eq["codigo_diseno"]} / {eq["codigo_servicio"]}'),
             ("t nominal", f(eq["t_nom_mm"], 2, "mm")), ("En servicio", fecha_cl(eq.get("fecha_servicio"))),
             ("Operación", f'{f(eq["operacion"]["P_MPa"])} MPa · {f(eq["operacion"]["T_C"], 0)} °C')]
    if eq["familia"] == "tuberia":
        filas += [("Circuito", eq.get("circuito")), ("Clase API 570", eq.get("clase"))]
    return '<dl class="kv">' + "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in filas) + "</dl>"


def esquema(eq, res_eq, cml_sel):
    if not eq.get("imagen"):
        return '<div class="info">Sin esquema. Súbelo en “Documentación técnica” (PNG o JPG).</div>'
    h = [f'<div class="esquema"><img src="{esc(eq["imagen"])}" alt="Esquema {esc(eq["tag"])}">']
    for c in eq["cmls"]:
        cond = res_eq["cmls"].get(c["id"], {}).get("condicion", "insuficiente")
        sel = "sel" if c["id"] == cml_sel else ""
        h.append(f'<div class="marcador {sel}" role="button" tabindex="0" data-act="sel_cml" data-id="{esc(c["id"])}" '
                 f'title="{esc(c["id"])} · {CONDICION[cond]}" aria-label="{esc(c["id"])}, {CONDICION[cond]}" '
                 f'style="left:{pct(c["x"])}%;top:{pct(c["y"])}%;--c:{COLOR[cond]}"><span>{esc(c["id"].split("-")[-1])}</span></div>')
    h.append('</div>')
    return "".join(h)


def vista_equipo(data, res, eq, cml_sel, cabecera=True):
    r = res[eq["id"]]
    h = [f'<div class="cabecera"><h1>{esc(eq["tag"])}</h1><span class="desc">{esc(eq["descripcion"])}</span>{badge(r["cond"])}'
         '<div class="der"><button class="chico secundario" data-act="editar_eq">Editar</button>'
         '<button class="chico peligro" data-act="borrar_eq">Eliminar</button></div></div>'] if cabecera else []
    if r["error"]:
        h.append(f'<div class="error">✕ No se pudo evaluar: {esc(r["error"])}</div>')
    chips = []
    for c in eq["cmls"]:
        x = r["cmls"].get(c["id"])
        cond = x["condicion"] if x else "insuficiente"
        sel = "sel" if c["id"] == cml_sel else ""
        chips.append(f'<div class="chip {sel}" role="button" tabindex="0" data-act="sel_cml" data-id="{esc(c["id"])}" '
                     f'aria-label="{esc(c["id"])}, {CONDICION[cond]}">'
                     f'<span class="punto" style="background:{COLOR[cond]}"></span>{esc(c["id"])}'
                     f'<small>{f(x["corrosion"]["t_actual"]) if x else "—"} mm</small></div>')
    nuevo = ('<form class="f" id="form_cml">'
             '<label>ID CML<input name="id" placeholder="CML-xxx-05" required></label>'
             '<label>Componente<input name="componente"></label><label>Ubicación<input name="ubicacion"></label>'
             '<label>x [%]<input type="number" name="x" min="0" max="100" value="50"></label>'
             '<label>y [%]<input type="number" name="y" min="0" max="100" value="50"></label>'
             '<label>t nominal [mm]<input type="number" step="0.01" name="t_nom_mm"></label>')
    if eq["familia"] == "tanque":
        nuevo += ('<label>Virola N°<input type="number" name="virola" value="1" min="1"></label>'
                  '<label>H desde fondo virola [m]<input type="number" step="0.01" name="H_m"></label>')
    nuevo += '<button data-act="add_cml">Agregar CML</button></form>'
    h.append(f'<div class="grid-eq"><div class="card">{esquema(eq, r, cml_sel)}'
             '<div class="muted" style="margin-top:8px">Marcadores: CML en (x, y) % del ancho y alto del esquema, '
             'origen arriba a la izquierda. Color = condición.</div></div>'
             f'<div class="card"><h2>Ficha técnica</h2>{ficha(eq)}<h3>CML / TML</h3><div class="chips">{"".join(chips)}</div>'
             f'{plegable("+ Agregar CML", nuevo)}</div></div>')

    c = next((c for c in eq["cmls"] if c["id"] == cml_sel), None)
    if c and r["cmls"].get(c["id"]):
        h.append(vista_cml(eq, c, r["cmls"][c["id"]]))
    elif eq["cmls"]:
        h.append('<div class="info">Selecciona un CML en el esquema o en la ficha para ver tendencia, cálculos e historial.</div>')

    docs = ('<form class="f"><label>Esquema / isométrico / foto (PNG, JPG)'
            '<input type="file" accept="image/png,image/jpeg" data-act="subir_img"></label>'
            '<label>Adjuntar PDF (consulta)<input type="file" accept="application/pdf" data-act="subir_pdf"></label></form>')
    if eq.get("adjuntos"):
        docs += "<ul>" + "".join(f'<li><a href="{esc(a["url"])}" target="_blank" rel="noopener noreferrer" download="{esc(a["nombre"])}">{esc(a["nombre"])}</a> '
                                 f'<button class="chico peligro" data-act="del_adj" data-i="{i}">Quitar</button></li>'
                                 for i, a in enumerate(eq["adjuntos"])) + "</ul>"
    h.append(plegable(f"Documentación técnica ({len(eq.get('adjuntos', []))} PDF)", docs))
    return "".join(h)


def pagina_equipo(data, res, eq, cml_sel, sub="resumen"):
    """Página de un equipo: migas de pan (ubicación técnica), encabezado y subnavegación Resumen | Diseño."""
    r = res[eq["id"]]
    u = eq["ubicacion"]
    migas = ('<nav class="migas" aria-label="Ubicación técnica">'
             f'<button data-act="tab" data-tab="planta">{esc(u["planta"])}</button><span>›</span>'
             f'<button data-act="ir_area" data-area="{esc(u["area"])}" title="Ver los CML de esta área">{esc(u["area"])}</button><span>›</span>'
             f'<span>{esc(u["sistema"])}</span><span>›</span><span aria-current="page">{esc(eq["tag"])}</span></nav>')
    pestanas = "".join(
        f'<button data-act="subvista" data-vista="{k}" class="{"activo" if sub == k else ""}" '
        f'{"aria-current=page" if sub == k else ""}>{t}</button>'
        for k, t in (("resumen", "Resumen y CML"), ("diseno", "Diseño y espesores")))
    cab = (f'{migas}<div class="cabecera cabecera-eq"><div><span class="eyebrow">{FAMILIAS[eq["familia"]]} · '
           f'{esc(eq["codigo_diseno"])} / {esc(eq["codigo_servicio"])}</span>'
           f'<h1>{esc(eq["tag"])} {badge(r["cond"])}</h1><span class="desc">{esc(eq["descripcion"])}</span></div>'
           '<div class="der"><button class="chico secundario" data-act="editar_eq">Editar</button>'
           '<button class="chico peligro" data-act="borrar_eq">Eliminar</button></div></div>'
           f'<div class="segmentado" role="tablist" aria-label="Vista del equipo">{pestanas}</div>')
    cuerpo = vista_diseno(eq, r, cabecera=False) if sub == "diseno" else vista_equipo(data, res, eq, cml_sel, cabecera=False)
    return cab + cuerpo


def puntos_atencion(data, res):
    """CML que requieren acción, del más grave al menos grave (bajo mínimo › vencida › alerta)."""
    orden = {"bajo_minimo": 0, "vencida": 1, "alerta": 2}
    filas = [fl for fl in filas_panel(data, res, {}) if fl["Condición"] in orden]
    return sorted(filas, key=lambda fl: (orden[fl["Condición"]], fl.get("RL [años]") or 1e9))


ICONO_FAMILIA = {
    "tuberia": '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M6 34h12V14h24" fill="none" stroke="currentColor" stroke-width="3" '
               'stroke-linecap="round" stroke-linejoin="round"/><path d="M12 30v8M30 10v8" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
    "recipiente": '<svg viewBox="0 0 48 48" aria-hidden="true"><rect x="15" y="6" width="18" height="34" rx="9" fill="none" stroke="currentColor" '
                  'stroke-width="3"/><path d="M24 2v4M24 40v6M18 44h12" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
    "tanque": '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 16l16-8 16 8v24H8z" fill="none" stroke="currentColor" stroke-width="3" '
              'stroke-linejoin="round"/><path d="M8 24h32M8 32h32M4 40h40" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
}
CODIGOS = {"tuberia": "ASME B31.3 · API 570", "recipiente": "ASME VIII-1 · API 510", "tanque": "API 650 · API 653"}


def vista_inicio(data, res):
    """Portada: qué es la app, qué requiere atención hoy y cómo se usa."""
    filas = filas_panel(data, res, {})
    atencion = puntos_atencion(data, res)
    proximas = sorted(fl["Próxima inspección"] for fl in filas
                      if fl["Próxima inspección"] and re.match(r"^\d{4}-", str(fl["Próxima inspección"]))
                      and fl["Próxima inspección"] >= date.today().isoformat())
    n_crit = sum(1 for fl in atencion if fl["Condición"] in ("bajo_minimo", "vencida"))
    h = ['<section class="hero"><span class="eyebrow">Prototipo académico · MAN040-B</span>'
         '<h1>Integridad de equipos estáticos,<br>en un solo lugar.</h1>'
         '<p class="lead">Registra mediciones de espesor, calcula corrosión y vida remanente, programa la próxima inspección '
         'según API 510, 570 y 653, y prioriza por riesgo con API RP 581.</p>'
         '<div class="cta"><button data-act="tab" data-tab="planta">Ver estado de la planta</button>'
         + ('<button class="secundario" data-act="ir_critico">Ir al punto más crítico</button>' if atencion else '')
         + '</div></section>',
         '<div class="stats">',
         stat("Equipos", len(data["equipos"]), sub="3 familias", clase="destacado"),
         stat("Puntos de monitoreo", len(filas), sub="CML / TML"),
         f'<div class="stat estado" style="--c:{COLOR["bajo_minimo"] if n_crit else COLOR["normal"]}">'
         f'<div class="l">Requieren acción</div><div class="v">{len(atencion)}</div>'
         f'<div class="s">{n_crit} crítico(s) · {len(atencion) - n_crit} en alerta</div></div>',
         stat("Próxima inspección", fecha_cl(proximas[0]) if proximas else "—", sub="programada"),
         '</div>']

    if atencion:
        items = "".join(
            f'<li class="fila-accion" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(fl["_eq"])}" data-cml="{esc(fl["_cml"])}">'
            f'{badge(fl["Condición"])}<span class="fa-txt"><b>{esc(fl["CML"])}</b> · {esc(fl["Equipo"])}'
            f'<small>{esc(fl.get("Componente", ""))} · t actual {f(fl.get("t_actual [mm]"))} mm · t mín {f(fl.get("t_min [mm]"))} mm</small></span>'
            f'<span class="fa-ir">{"Inmediata" if fl["Condición"] == "bajo_minimo" else fecha_cl(fl["Próxima inspección"])} ›</span></li>'
            for fl in atencion[:5])
        h.append(f'<div class="card"><div class="card-cab"><h2>Requiere atención</h2>'
                 f'<button class="chico secundario" data-act="tab" data-tab="planta">Ver todos los CML</button></div>'
                 f'<ul class="lista-accion">{items}</ul></div>')
    else:
        h.append('<div class="card"><h2>Todo en orden</h2><p class="muted">Ningún CML bajo el mínimo, vencido ni en alerta.</p></div>')

    tarjetas = []
    for fam, nombre in FAMILIAS.items():
        eqs = [e for e in data["equipos"] if e["familia"] == fam]
        if not eqs:
            continue
        e = eqs[0]
        n_cml = sum(len(x["cmls"]) for x in eqs)
        tarjetas.append(
            f'<div class="familia" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(e["id"])}" '
            f'aria-label="Abrir {esc(e["tag"])}, {nombre}"><div class="familia-ico">{ICONO_FAMILIA[fam]}</div>'
            f'<div class="familia-txt"><span class="eyebrow">{CODIGOS[fam]}</span><h3>{nombre}</h3>'
            f'<p>{esc(e["tag"])} · {esc(e["descripcion"])}</p></div>'
            f'<div class="familia-pie">{badge(res[e["id"]]["cond"])}<span class="muted">{n_cml} CML ›</span></div></div>')
    h.append(f'<h2 class="titulo-seccion">Equipos del caso de estudio</h2><div class="familias">{"".join(tarjetas)}</div>')

    pasos = [("Elige un equipo", "Desde Planta o Equipos. Verás su ubicación técnica, esquema y CML; se abre el más crítico."),
             ("Revisa el CML", "Espesor actual, mínimo y de alerta, corrosión, vida remanente y la tendencia en el gráfico."),
             ("Registra una medición", "Ingresa la lectura de UT: la condición y la próxima inspección se recalculan al instante."),
             ("Evalúa el riesgo", "En Riesgo (RBI) ajusta consecuencias e inspecciones y observa la prioridad en la matriz.")]
    h.append('<h2 class="titulo-seccion">Cómo se usa</h2><ol class="pasos">' + "".join(
        f'<li><span class="paso-n">{i}</span><h3>{t}</h3><p>{d}</p></li>' for i, (t, d) in enumerate(pasos, 1)) + '</ol>')
    h.append('<footer class="pie-inicio"><span>Cálculos verificados en <button class="enlace" data-act="tab" data-tab="validacion">Validación</button>'
             ' · Normas y supuestos en <button class="enlace" data-act="tab" data-tab="acerca">Acerca</button></span>'
             '<a href="https://github.com/Matiasgodoys1512/Trabajoestaticos" target="_blank" rel="noopener noreferrer">Repositorio en GitHub ↗</a></footer>')
    return "".join(h)


def form_equipo(eq=None):
    nuevo = eq is None
    eq = eq or {"id": "", "tag": "", "familia": "tuberia", "descripcion": "", "servicio": "", "fluido": "",
                "ubicacion": {"planta": "Refinería Demo", "area": "", "sistema": ""}, "circuito": "", "clase": 2,
                "material": "A106-B", "codigo_diseno": "", "codigo_servicio": "", "t_nom_mm": 0,
                "fecha_servicio": date.today().isoformat(), "operacion": {"P_MPa": 0, "T_C": 20}}
    fam_opts = "".join(f'<option value="{k}" {"selected" if k == eq["familia"] else ""}>{v}</option>' for k, v in FAMILIAS.items())
    u = eq["ubicacion"]

    def inp(name, label, val, tipo="text", extra=""):
        return f'<label>{label}<input type="{tipo}" name="{name}" value="{esc(val)}" {extra}></label>'

    return (f'<div class="card"><h2>{"Nuevo equipo" if nuevo else "Editar " + esc(eq["tag"])}</h2>'
            '<form class="f" id="form_eq">'
            + inp("tag", "TAG", eq["tag"], extra='required maxlength="60"')
            + f'<label>Familia<select name="familia" data-act="form_familia" {"" if nuevo else "disabled"}>{fam_opts}</select></label>'
            + inp("descripcion", "Descripción", eq["descripcion"]) + inp("servicio", "Servicio", eq["servicio"])
            + inp("fluido", "Fluido", eq["fluido"]) + inp("planta", "Planta", u["planta"])
            + inp("area", "Área", u["area"]) + inp("sistema", "Sistema / línea", u["sistema"])
            + inp("circuito", "Circuito de inspección (tubería)", eq.get("circuito") or "")
            + inp("clase", "Clase API 570 (1–4)", eq.get("clase") or "", "number", 'min="1" max="4"')
            + f'<label>Material<select name="material">{opciones_material(eq["familia"], eq["material"])}</select></label>'
            + inp("codigo_diseno", "Código de diseño", eq["codigo_diseno"])
            + inp("codigo_servicio", "Código en servicio", eq["codigo_servicio"])
            + inp("t_nom_mm", "Espesor nominal [mm]", eq["t_nom_mm"] or "", "number", 'step="0.01" min="0.1" required')
            + inp("fecha_servicio", "Puesta en servicio", eq.get("fecha_servicio", ""), "date")
            + inp("P_op", "P operación [MPa]", eq["operacion"]["P_MPa"], "number", 'step="0.01"')
            + inp("T_op", "T operación [°C]", eq["operacion"]["T_C"], "number", 'step="1"')
            + '<div class="acciones-form ancho">'
            f'<button data-act="guardar_eq" data-nuevo="{1 if nuevo else 0}">Guardar equipo</button>'
            '<button type="button" class="secundario" data-act="cancelar_eq">Cancelar</button></div></form>'
            '<p class="muted">Los datos de diseño (P, T, dimensiones, E, CA) se editan después en la pestaña «Diseño».</p></div>')


# ------------------------------------------------------------------ diseño
def escalera(items, tope):
    """Barras horizontales a escala (0 → tope) con el espesor en mm. items: (nombre, valor, color[, grupo])."""
    paso = next(p for p in (0.5, 1, 2, 2.5, 5, 10, 20, 50) if tope / p <= 6)
    marcas = [i * paso for i in range(int(tope // paso) + 1)]
    eje = "".join(f'<span style="left:{m / tope * 100:.2f}%">{f(m, 0) if paso >= 1 else f(m, 1)}</span>' for m in marcas)
    h = ['<div class="escalera" role="img" aria-label="Espesores en milímetros">']
    grupo_prev = None
    for it in items:
        nom, val, color = it[:3]
        grupo = it[3] if len(it) > 3 else None
        if val is None:
            continue
        if grupo and grupo != grupo_prev:
            h.append(f'<div class="esc-grupo">{grupo}</div>')
            grupo_prev = grupo
        ancho = max(min(val / tope * 100, 100), 1)
        h.append(f'<div class="esc-fila"><span>{nom}</span><div><div class="barra" style="width:{ancho:.1f}%;--c:{color}"></div></div>'
                 f'<span class="val">{f(val)} <small>mm</small></span></div>')
    h.append(f'<div class="esc-fila esc-eje" aria-hidden="true"><span></span><div class="eje">{eje}</div>'
             '<span class="val"><small>t [mm]</small></span></div></div>')
    return "".join(h)


TOLERANCIA = {
    "tuberia": '<li><b>Tolerancia de fabricación</b>: tubo sin costura hasta −12,5 % del espesor nominal (ASTM A106/A53) '
               '→ t_compra ≥ t_m / 0,875 (ASME B31.3 §304.1.1).</li>',
    "recipiente": '<li><b>Tolerancia de plancha</b>: se acepta una diferencia menor que el menor valor entre 0,3 mm (0,01 in) '
                  'y el 6 % del espesor de diseño; si la especificación permite más, se aumenta el espesor pedido (ASME VIII-1 UG-16(c)).</li>',
    "tanque": '<li><b>Tolerancia de plancha</b>: se acepta una merma de hasta 0,3 mm (0,01 in) respecto del espesor de diseño '
              'o mínimo permitido (API 650 §4.2.1.2.3).</li>',
}


def vista_diseno(eq, res_eq, cabecera=True):
    fam = eq["familia"]
    d = eq["diseno"]
    mat = MATERIALES[eq["material"]]
    campos = "".join(f'<label>{label}<input type="number" step="any" value="{vin(d.get(k, ""))}" data-act="diseno" data-campo="{k}"></label>'
                     for k, label in CAMPOS_DISENO[fam])
    if fam == "tanque":
        s_txt = f'{mat["nombre"]} · Sd = {f(mat["Sd"], 0)} MPa · Y = {f(mat["YS"], 0)} · T = {f(mat["TS"], 0)} MPa'
    else:
        try:
            S = esfuerzo_admisible(eq["material"], d["T_diseno_C"])
            s_txt = f'{mat["nombre"]} · S({f(d["T_diseno_C"], 0)} °C) = {f(S, 1)} MPa ({f(S / 6.894757, 1)} ksi)'
        except ValueError as e:
            s_txt = f'<span class="fail">{esc(e)}</span>'
    h = ([f'<div class="cabecera"><h1>{esc(eq["tag"])}</h1><span class="desc">Condiciones de diseño · {FAMILIAS[fam]}</span></div>']
         if cabecera else []) + [
         f'<div class="card"><h2>Variables de diseño</h2><form class="f">{campos}</form>'
         f'<div class="info" style="margin-top:12px">{s_txt}&nbsp;<span class="muted">· {esc(mat["ref"])}</span></div>'
         '<div class="muted">Cambia un valor y presiona Enter o Tab: se recalcula todo el equipo.</div></div>']
    if res_eq["error"]:
        h.append(f'<div class="error">✕ {esc(res_eq["error"])}</div>')
        return "".join(h)
    c_gob, motivo = cml_gobernante(eq, res_eq)
    cmls = (eq["cmls"] if fam == "tanque" else [c_gob]) if c_gob else [None]
    for c in cmls:
        if c is None:  # equipo sin CML: espesores solo con datos de diseño
            esp = es.evaluar_equipo(eq)
            x = {"espesores": esp, "t_min": esp["t_min"], "t_alerta": esp["t_min"], "corrosion": {"t_actual": None}}
        else:
            x = res_eq["cmls"][c["id"]]
        dis = es.espesor_diseno(eq, c)
        tn = (c or {}).get("t_nom_mm") or eq["t_nom_mm"]
        items = [("Nominal", tn, "#aeaeb2", "Diseño y fabricación"), ("Diseño / compra", dis["valor"], "#5fb38a", "Diseño y fabricación"),
                 ("Requerido por cálculo", dis["t_calc"], "#9ccfb3", "Diseño y fabricación"),
                 ("Medido (último)", x["corrosion"]["t_actual"], "#1f7a4d", "En servicio"),
                 ("Alerta", x["t_alerta"], "#fab219", "En servicio"), ("Mínimo en servicio", x["t_min"], "#d03b3b", "En servicio")]
        tope = max(it[1] for it in items if it[1]) * 1.05
        if fam == "tanque" and c:
            titulo = f'Espesores de pared [mm] · {esc(c["id"])} · {esc(c["componente"])}'
        elif c:
            titulo = f'Espesores de pared [mm] · CML gobernante: {esc(c["id"])} ({motivo})'
        else:
            titulo = "Espesores de pared [mm] · sin CML (solo datos de diseño)"
        if fam == "tanque":
            d_calc = calc("Requerido por cálculo", f(dis["t_calc"], 3, "mm"), "td − CA = 4,9·D·(H − 0,3)·G / Sd",
                          dis["entradas"], dis["ref"])
        else:
            d_calc = calc("Requerido por cálculo", f(dis["t_calc"], 3, "mm"), x["espesores"]["ecuacion"],
                          x["espesores"]["entradas"], x["espesores"]["ref"], x["espesores"].get("avisos", ()))
        if fam == "tanque":
            d_calc += calc("Prueba hidrostática tt", f(dis["tt"], 3, "mm"), "tt = 4,9·D·(H − 0,3) / St", None, "API 650 §5.6.3.2")
            d_calc += calc("Mínimo nominal por diámetro", f(dis["t_nom_min"], 1, "mm"), "", None, "API 650 §5.6.1.1")
            d_calc += f'<div class="muted">Gobierna: {esc(dis["gobierna"])}</div>'
        elif fam == "recipiente":
            d_calc += (f'<div class="muted">UG-27: t circunferencial = {f(x["espesores"]["t_circ"], 3)} mm · '
                       f't longitudinal = {f(x["espesores"]["t_long"], 3)} mm → gobierna {esc(x["espesores"]["gobierna"])}</div>')
        detalle = (d_calc + calc_r("Diseño / compra", dis) + calc_tmin(x)
                   + (f'<div class="muted">{esc(x["espesores"]["regla_S"])} → S = {f(x["espesores"]["S"], 1)} MPa</div>' if fam == "tanque" else ""))
        alerta = f'<div class="error">✕ Nominal ({f(tn)} mm) menor que el de diseño ({f(dis["valor"])} mm).</div>' if dis["valor"] > tn else ""
        tabla = ""
        if fam != "tanque" and len(eq["cmls"]) > 1:
            filas = "".join(
                f'<tr><td>{esc(cc["id"])}{" ★" if cc is c else ""}</td><td>{esc(cc["componente"])}</td>'
                f'<td class="num">{f(res_eq["cmls"][cc["id"]]["corrosion"]["t_actual"])}</td>'
                f'<td class="num">{f(res_eq["cmls"][cc["id"]]["t_alerta"])}</td><td class="num">{f(res_eq["cmls"][cc["id"]]["t_min"])}</td>'
                f'<td>{badge(res_eq["cmls"][cc["id"]]["condicion"])}</td></tr>' for cc in eq["cmls"])
            tabla = plegable("Espesores por CML", '<table><tr><th>CML</th><th>Componente</th><th class="num">Medido [mm]</th>'
                             '<th class="num">Alerta [mm]</th><th class="num">Mínimo [mm]</th><th>Condición</th></tr>' + filas + '</table>'
                             '<div class="muted">★ = CML gobernante (peor condición, luego menor vida remanente).</div>', True)
        margen = ""
        if x["corrosion"]["t_actual"] is not None:
            mg = x["corrosion"]["t_actual"] - x["t_min"]
            margen = (f'<div class="muted esc-nota">Margen sobre el mínimo: <b class="{"fail" if mg < 0 else ""}">{f(mg)} mm</b> · '
                      'barras a escala desde 0 mm. Todos los valores son espesores de pared.</div>')
        h.append(f'<div class="card"><h2>{titulo}</h2>{alerta}{escalera(items, tope)}{margen}{tabla}{plegable("Ver cálculos", detalle)}</div>')
    notas = ('<ul><li><b>CA</b>: sobreespesor que se consume en servicio; no forma parte del t_min.</li>'
             + TOLERANCIA[fam] +
             '<li><b>Alerta</b>: t_min + CR·T_int, con T_int = 2 años (gestión de OT, repuestos y parada).</li></ul>')
    h.append(plegable("Definiciones de espesor", notas))
    return "".join(h)


# ------------------------------------------------------------------ RBI
def matriz(cat_p, cat_c, titulo):
    h = [f'<div><h3>{titulo}</h3><div class="matriz">']
    for p in "54321":
        h.append(f'<div class="eje">{p}</div>')
        for c in "ABCDE":
            n = rbi.nivel_riesgo(int(p), c)
            aqui = p == cat_p and c == cat_c
            h.append(f'<div class="m-{n} {"aqui" if aqui else ""}" title="POF {p} · COF {c}: {n}">{"●" if aqui else ""}</div>')
    h.append('<div></div>' + "".join(f'<div class="eje">{c}</div>' for c in "ABCDE"))
    h.append('</div><div class="matriz-pie">Filas: POF · Columnas: consecuencia</div></div>')
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
    return {"ent": ent, "con": con, "sin": sin, "fms": fms, "r": rr, "r_sin": rs, "f_eval": f_eval, "cml": c,
            "cr_adoptada": v["cr"]}


def vista_rbi(data, res):
    eq = next((e for e in data["equipos"] if e.get("rbi") and e["familia"] == "recipiente"), None)
    if not eq:
        return '<div class="info">No hay un recipiente con caso RBI definido.</div>'
    if res[eq["id"]]["error"]:
        return f'<div class="error">{esc(res[eq["id"]]["error"])}</div>'
    cfg = eq["rbi"]
    R = calcular_rbi(eq, res[eq["id"]])
    p, e, r = R["con"]["pasos"], R["ent"], R["r"]
    cml_opts = "".join(f'<option {"selected" if c["id"] == cfg["cml"] else ""}>{esc(c["id"])}</option>' for c in eq["cmls"])
    conf_opts = "".join(f'<option {"selected" if k == cfg["confianza"] else ""}>{k}</option>' for k in rbi.PRIOR)

    def num(campo, label, val, step="any"):
        return f'<label>{label}<input type="number" step="{step}" value="{vin(val)}" data-act="rbi" data-campo="{campo}"></label>'

    color_nivel = {"Bajo": "#0ca30c", "Medio": "#fab219", "Medio-alto": "#ec835a", "Alto": "#d03b3b"}[r["nivel"]]
    h = [f'<div class="cabecera"><h1>RBI · {esc(eq["tag"])}</h1><span class="desc">Adelgazamiento generalizado · API RP 580 / 581</span></div>',
         '<div class="stats">',
         stat("Factor de daño D_f", f(R["con"]["Df"], 1), "", "adimensional"),
         stat("Frecuencia de falla P_f", sci(r["Pf"]), "1/año", f"categoría POF {r['cat_pof']}"),
         stat("Riesgo de área R_A", f(r["R_A"], 4), "m²/año", f"C_A categoría {r['cat_area']}"),
         stat("Riesgo económico R_E", f(r["R_E"], 0), f"{esc(r['moneda'])}/año", f"C_E categoría {r['cat_fin']}"),
         f'<div class="stat estado" style="--c:{color_nivel}"><div class="l">Prioridad</div><div class="v">{r["nivel"]}</div>'
         f'<div class="s">{esc(r["accion"].split(":")[0])}</div></div>',
         '</div>']
    entradas = ('<form class="f col">'
                f'<label>CML gobernante<select data-act="rbi" data-campo="cml">{cml_opts}</select></label>'
                f'<label>Fecha de evaluación<input type="date" value="{R["f_eval"]}" data-act="rbi" data-campo="fecha_eval"></label>'
                f'<label>Confianza en la CR<select data-act="rbi" data-campo="confianza">{conf_opts}</select></label>'
                + num("pscore", "Puntaje gestión [%]", cfg.get("pscore", 50))
                + "".join(num(f"insp_{k}", f"Inspecciones {k}", cfg["inspecciones"].get(k, 0), "1") for k in "ABCD")
                + num("C_A_m2", "Consecuencia de área C_A [m²]", cfg["C_A_m2"])
                + num("C_E", f"Consecuencia económica C_E [{esc(cfg.get('moneda', 'USD'))}]", cfg["C_E"])
                + f'<label>Moneda<input value="{esc(cfg.get("moneda", "USD"))}" data-act="rbi" data-campo="moneda"></label>'
                + num("f_om", "F_OM (monitoreo)", cfg.get("f_om", 1.0))
                + f'<label class="ancho">Base de valoración<input value="{esc(cfg.get("base_valoracion", ""))}" data-act="rbi" data-campo="base_valoracion"></label>'
                + '</form>')
    h.append(f'<div class="grid-cml"><div class="card"><h2>Matriz de riesgo</h2><div class="grid2">'
             f'{matriz(r["cat_pof"], r["cat_area"], "Por área → " + r["nivel_area"])}'
             f'{matriz(r["cat_pof"], r["cat_fin"], "Económica → " + r["nivel_fin"])}</div>'
             f'<div class="info" style="margin-top:12px"><b>{r["nivel"]}:</b>&nbsp;{esc(r["accion"])}</div>'
             '<h3>Efecto de la inspección</h3><table><tr><th></th><th class="num">D_f</th><th class="num">P_f</th><th>Nivel</th></tr>'
             f'<tr><td>Sin inspecciones</td><td class="num">{f(R["sin"]["Df"], 1)}</td><td class="num">{sci(R["r_sin"]["Pf"])}</td><td>{R["r_sin"]["nivel"]}</td></tr>'
             f'<tr><td>Con inspecciones registradas</td><td class="num">{f(R["con"]["Df"], 1)}</td><td class="num">{sci(r["Pf"])}</td><td>{r["nivel"]}</td></tr></table>'
             '<div class="muted" style="margin-top:6px">La inspección no recupera espesor: reduce la incertidumbre sobre la CR real (Bayes) y con ello D_f.</div>'
             f'</div><div class="card"><h2>Entradas</h2>{entradas}</div></div>')
    filas = [
        ("CR largo plazo (usada en D_f)", "API 581 §4.5.2 recomienda la CR de largo plazo", f(e["cr"], 4, "mm/año")),
        ("CR adoptada en vida remanente", "máx(CR_LP; CR_CP), criterio conservador del panel", f(R["cr_adoptada"], 4, "mm/año")),
        ("age", f"{fecha_cl(eq['fecha_servicio'])} → {fecha_cl(R['f_eval'])}", f(e["edad"], 2, "años")),
        ("t_rdi", "espesor entregado", f(e["t_rdi"], 2, "mm")), ("t_min", "UG-27", f(e["t_min"], 3, "mm")),
        ("Art = CR·age / t_rdi", "ec. 2.12", f(p["Art"], 4)), ("FS = (YS + TS)/2 · E · 1,1", "ec. 2.13", f(p["FS"], 1, "MPa")),
        ("SR_P = S·E·t_min / (FS·t_rdi)", "ec. 2.14", f(p["SRp"], 4)),
        ("Pr₁ / Pr₂ / Pr₃", f"Tabla 4.5 ({cfg['confianza']})", " / ".join(f(v, 2) for v in p["prior"])),
        ("Po₁ / Po₂ / Po₃", "ec. 2.16–2.17, Tabla 4.6", " / ".join(f(v, 4) for v in p["Po"])),
        ("β₁ / β₂ / β₃", "ec. 2.18 (DS 1, 2, 4)", " / ".join(f(v, 3) for v in p["beta"])),
        ("D_fB = ΣPo·Φ(−β) / 1,56·10⁻⁴", "ec. 2.19", f(p["DfB"], 2)), ("D_f = máx(D_fB / F_OM; 0,1)", "ec. 2.20", f(R["con"]["Df"], 2)),
        ("P_f = gff · F_MS · D_f", f"gff 3,06·10⁻⁵ (Tabla 3.1) · F_MS {f(R['fms'], 3)} (ec. 2.10)", sci(r["Pf"]) + " 1/año"),
        ("R_A = P_f · C_A", "Parte 1 §4.1", f(r["R_A"], 5, "m²/año")), ("R_E = P_f · C_E", "Parte 1 §4.1", f(r["R_E"], 2, f"{r['moneda']}/año")),
    ]
    tabla = ('<table><tr><th>Paso</th><th>Origen</th><th class="num">Valor</th></tr>'
             + "".join(f'<tr><td>{a}</td><td class="muted">{b}</td><td class="num">{c}</td></tr>' for a, b, c in filas) + '</table>')
    h.append(plegable("Desarrollo del cálculo (API RP 581 Parte 2 §4.5.7)", tabla))
    h.append(plegable("Supuestos del modelo",
                      '<ul><li>Modelo académico simplificado: un mecanismo, sin cladding, F_IP = F_DL = 1.</li>'
                      '<li>Consecuencias ingresadas por el usuario; base temporal 1 año.</li>'
                      f'<li>Escenario: {esc(cfg.get("escenario", ""))}</li>'
                      f'<li>Base de valoración: {esc(cfg.get("base_valoracion", ""))}</li>'
                      '<li>Límites de categoría: Parte 1, Tablas 4.1M y 4.2. Matriz de niveles: criterio del grupo (Parte 1, Fig. 4.2).</li></ul>'))
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
        ("Recipiente", "t UG-27(c)(2) longitudinal", "P = 1,5 MPa, R = 750 mm, S = 20 ksi, E = 0,85", "ASME VIII-1 UG-27",
         4.7868, es.recipiente_ug27(1.5, 750, 20 * KSI, 0.85)["t_long"], "mm"),
        ("Recipiente", "Intervalo API 510", "RL = 12 años → RL/2", "API 510 §6.5.1.1", 6.0, ins.intervalo("recipiente", 12)[0], "años"),
        ("Tanque", "td API 650 virola 1", "D = 20 m, H = 12 m, G = 0,85, Sd = 137 MPa, CA = 1,5 mm", "API 650 §5.6.3.2",
         8.6139, es.tanque_api650_diseno(20, 12, 0.85, 137, 1.5)["valor"], "mm"),
        ("Tanque", "tt API 650 virola 1", "D = 20 m, H = 12 m, St = 154 MPa", "API 650 §5.6.3.2",
         7.4455, es.tanque_api650_diseno(20, 12, 0.85, 137, 1.5, St=154)["tt"], "mm"),
        ("Tanque", "t_min API 653 virola 1", "S = mín(0,8·205; 0,429·380) = 163,02 MPa", "API 653 §4.3.3.1",
         5.9785, es.tanque_api653_tmin(20, 12, 0.85, 205, 380)["valor"], "mm"),
        ("RBI", "Posterior Po₁", "Confianza media, 2 inspecciones B", "API 581 ec. 2.16–2.17", 0.97443, r_rbi["pasos"]["Po"][0], "—"),
        ("RBI", "D_f adelgazamiento", "CR = 0,3656 mm/año, age = 10 años, t = 16 mm, t_min = 9,672 mm, SA-516-70, E = 0,85",
         "API 581 ec. 2.12–2.20", 16.0315, r_rbi["Df"], "—"),
        ("RBI", "R_A con C_A = 120 m²", "P_f = 3,06·10⁻⁵ · 1 · D_f", "API 581 Parte 1 §4.1", 0.058868,
         rbi.riesgo(r_rbi["Df"], 120, 450000)["R_A"], "m²/año"),
    ]


def vista_validacion():
    casos = casos_validacion()
    filas, ok_n = [], 0
    for fam, nom, ent, ref, esp, prog, u in casos:
        dif = abs(prog - esp) / abs(esp) * 100 if esp else 0
        ok = dif <= 0.5
        ok_n += ok
        filas.append(f'<tr><td><b>{esc(nom)}</b><div class="muted">{esc(fam)} · {esc(ref)}</div></td><td class="muted">{esc(ent)}</td>'
                     f'<td class="num">{f(esp, 4)}</td><td class="num">{f(prog, 4)}</td><td>{u}</td><td class="num">{"&lt; 0,001" if dif < 0.001 else f(dif, 3)} %</td>'
                     f'<td>{badge("normal", "OK") if ok else badge("bajo_minimo", "Revisar")}</td></tr>')
    h = ['<div class="cabecera"><h1>Validación</h1><span class="desc">Comparación con cálculos independientes</span></div>',
         '<div class="stats">', stat("Casos verificados", f"{ok_n}/{len(casos)}", "", "tolerancia 0,5 %", "destacado"),
         stat("Familias", "3 + RBI"), stat("Caso de clase", "Ejercicio 05", "", "8\" A53 B · HF"), '</div>',
         '<div class="card"><table><tr><th>Cálculo</th><th>Entradas</th><th class="num">Esperado</th><th class="num">Programa</th>'
         '<th>Unidad</th><th class="num">Dif.</th><th></th></tr>' + "".join(filas) + '</table>'
         '<div class="muted" style="margin-top:8px">Esperado: cálculo manual / planilla. Programa: mismas funciones de la app, ejecutadas en el navegador.</div></div>']
    cond = [("normal", "CML-101-01 · 201-01/02 · 301-01/02", "t sobre t_alerta y fecha vigente"),
            ("alerta", "CML-101-02", "t_min < t < t_min + CR·2 años"),
            ("bajo_minimo", "CML-201-03", "9,50 mm < t_min 9,67 mm"),
            ("vencida", "CML-101-04", "Ejercicio de clase: próxima inspección en 2024"),
            ("insuficiente", "CML-101-03 · 301-03", "Spool reemplazado / CML nuevo con 1 lectura")]
    h.append('<div class="card"><h2>Casos de condición en la demo</h2><table>'
             + "".join(f'<tr><td>{badge(k)}</td><td>{esc(a)}</td><td class="muted">{esc(b)}</td></tr>' for k, a, b in cond) + '</table></div>')
    return "".join(h)


# ------------------------------------------------------------------ alcance
def vista_acerca():
    alcance = ('<table><tr><th>Familia</th><th>Diseño</th><th>Servicio</th><th>Geometría</th><th>Materiales</th></tr>'
               '<tr><td>Tubería</td><td>ASME B31.3-2018</td><td>API 570</td><td>Tramo recto</td><td>A106 B, A53 B</td></tr>'
               '<tr><td>Recipiente</td><td>ASME VIII-1 2019 + II-D</td><td>API 510</td><td>Envolvente cilíndrica</td><td>SA-516 Gr. 70</td></tr>'
               '<tr><td>Tanque</td><td>API 650 (2013)</td><td>API 653</td><td>Virolas (1 pie)</td><td>A283 C, A36</td></tr></table>')
    sup = ('<ul><li>Catálogo hasta 260 °C; tanques a temperatura ambiente. Unidades SI (1 in = 25,4 mm).</li>'
           '<li>CR adoptada = máx(LP; CP). RBI con CR de largo plazo (API 581 §4.5.2).</li>'
           '<li>Reemplazo, reparación o cambio de punto reinicia la serie comparable.</li>'
           '<li>Intervalos: próxima medición de espesores. Tanques: solo manto.</li>'
           '<li>RBI: modelo académico, solo adelgazamiento generalizado en V-201.</li><li>Datos de la demo: ficticios.</li></ul>')
    refs = ('<ul>'
            f'<li>{EDICION["B31.3"]}: §304.1.1, §304.1.2, Tablas A-1, A-1A, 302.3.5, 304.1.1.</li>'
            f'<li>{EDICION["VIII-1"]}: UG-16(c), UG-27 · {EDICION["II-D"]}: Tabla 1A.</li>'
            f'<li>{EDICION["API 650"]}: §4.2.1.2.3, §5.6.1.1, §5.6.3.2, Tabla 5.2a.</li>'
            f'<li>{EDICION["API 510"]}: §6.5.1.1, §7.1.1.</li>'
            f'<li>{EDICION["API 570"]}: §6.3.3, §7.1.1 · {EDICION["API 574"]}: espesor estructural mínimo.</li>'
            f'<li>{EDICION["API 653"]}: §4.3.3.1, §6.3.3.2.</li>'
            f'<li>API RP 580 3ª ed. (2016) · {EDICION["API 581"]}: Parte 1 §4; Parte 2 §3–4.</li>'
            '<li>Apuntes MAN040-B, clases 01–06 (Prof. A. Badilla).</li></ul>'
            '<div class="muted">API 510, 570, 574 y 653: no se dispuso del texto completo; los criterios provienen de los apuntes '
            'del curso (clase 05) y deben verificarse contra la edición declarada.</div>')
    herr = ('<p>Python (PyScript/Pyodide, NumPy, pandas, Matplotlib), HTML/CSS, pytest, Git, GitHub Pages y VS Code. '
            'Asistente de IA en modo agente como apoyo en programación y revisión; los cálculos se verificaron con los casos de la pestaña Validación.</p>')
    return ('<div class="cabecera"><h1>Alcance y referencias</h1></div>'
            f'<div class="card"><h2>Alcance por familia</h2>{alcance}</div>'
            + '<div class="info">Repositorio: <a href="https://github.com/Matiasgodoys1512/Trabajoestaticos" target="_blank" '
              'rel="noopener noreferrer">github.com/Matiasgodoys1512/Trabajoestaticos</a></div>'
            + plegable("Supuestos y limitaciones", sup, True) + plegable("Referencias normativas", refs) + plegable("Herramientas", herr))
