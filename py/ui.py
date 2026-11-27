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
    if isinstance(x, float) and 0 < abs(x) < 1e-3:
        s = sci(x)
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


GLOSARIO = {
    "t_actual": "Último espesor medido de la serie comparable del CML.",
    "t_min": "Espesor mínimo requerido en servicio (presión o estructural). Bajo este valor: evaluar FFS (API 579-1), reparar o reemplazar.",
    "t_alerta": "t mín + CR · 2 años: margen para gestionar OT, repuestos y parada (criterio del grupo).",
    "cr": "Velocidad de corrosión adoptada: la mayor entre largo y corto plazo (criterio conservador, API 510 / 570 §7.1.1).",
    "rl": "Vida remanente = (t actual − t mín) / CR. Años hasta llegar al mínimo con la CR adoptada.",
    "proxima": "Próxima medición de espesores: última medición + mín(RL/2; máximo de la norma). API 510 §6.5.1.1, API 570 Tabla 6.3.3, API 653 §6.3.3.2.",
    "nominal": "Espesor de catálogo o de plancha con que se fabricó el componente.",
    "diseno": "Espesor de compra: requerido + sobreespesor de corrosión, corregido por la tolerancia de fabricación.",
    "requerido": "Espesor que exige el código de diseño solo por presión o carga hidrostática, sin sobreespesor.",
    "medido": "Última lectura de UT del CML evaluado.",
    "df": "Factor de daño: multiplica la frecuencia genérica de falla. No es una probabilidad (API 581 Parte 2 §4).",
    "pf": "Frecuencia de falla = gff · FMS · Df, en fallas por año (API 581 Parte 1 §4.1).",
    "ra": "Riesgo de área = Pf · CA: superficie afectada esperada por año (m²/año).",
    "re": "Riesgo económico = Pf · CE: costo esperado por año.",
    "prioridad": "Nivel de la matriz 5×5 (el peor entre área y económica) y acción recomendada. POF 1–5 según API 581 Parte 1, Tabla 4.1M.",
}


def ayuda(clave):
    """Ícono «?» con una definición breve; se muestra al pasar el mouse o con el teclado (foco)."""
    tip = esc(GLOSARIO.get(clave, ""))
    return f'<span class="ayuda" tabindex="0" role="img" aria-label="{tip}" data-tip="{tip}">?</span>' if tip else ""


def stat(label, valor, unidad="", sub="", clase="", ayuda_k=None):
    u = f"<small>{unidad}</small>" if unidad else ""
    s = f'<div class="s">{sub}</div>' if sub else ""
    a = ayuda(ayuda_k) if ayuda_k else ""
    return f'<div class="stat {clase}"><div class="l">{label}{a}</div><div class="v">{valor}{u}</div>{s}</div>'


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
def _distinto(a, b):
    try:
        return abs(float(a) - float(b)) > 1e-9
    except (TypeError, ValueError):
        return str(a) != str(b)


def campo_num(act, campo, label, val, base=None, step="any", fmt=None):
    """Input numérico. Si el valor difiere del caso demo (base), se resalta y ofrece «↺» para volver a él."""
    editado = base is not None and _distinto(val, base)
    rev = (f'<button type="button" class="revertir" data-act="revertir" data-tipo="{act}" data-campo="{campo}" '
           f'title="Volver al valor del caso demo ({esc(fmt(base) if fmt else vin(base))})" '
           f'aria-label="Volver {esc(campo)} al valor del caso demo">↺</button>') if editado else ""
    return (f'<label class="{"editado" if editado else ""}">{label}<span class="campo">'
            f'<input type="number" step="{step}" value="{vin(val)}" data-act="{act}" data-campo="{campo}">{rev}</span></label>')


def aviso_cambio(txt):
    """Resultado del último cambio («antes → después»), visible hasta el próximo cambio de vista."""
    return f'<div class="cambio" role="status"><b>Último cambio</b><span>{txt}</span></div>' if txt else ""


_CTX = {"hoy": None}  # fecha de evaluación vigente (la fija evaluar_todo en cada render)


def fecha_evaluacion(data):
    """Fecha de evaluación del proyecto: la elegida por el usuario o, si no hay, la del computador."""
    f = data.get("fecha_evaluacion")
    return date.fromisoformat(f) if f else date.today()


def hoy_eval():
    return _CTX["hoy"] or date.today()


def evaluar_todo(data, hoy=None):
    hoy = hoy or fecha_evaluacion(data)
    _CTX["hoy"] = hoy
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
                    desc = e.get("descripcion") or FAMILIAS[e["familia"]]
                    h.append(f'<div class="eq-item {act}" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(e["id"])}" '
                             f'title="{esc(e["tag"])} · {esc(desc)} · {CONDICION[cond]}" aria-label="{esc(e["tag"])}, {CONDICION[cond]}">'
                             f'<span class="punto" style="background:{COLOR[cond]}"></span>'
                             f'<span class="eq-txt"><span class="eq-tag">{esc(e["tag"])}</span>'
                             f'<small>{FAMILIAS[e["familia"]].split()[0]} · {esc(desc)}</small></span></div>')
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
    plantas = {}
    for e in data["equipos"]:
        u = e["ubicacion"]
        plantas.setdefault(u["planta"], {}).setdefault(u["area"], {}).setdefault(u["sistema"], []).append(e)
    bloques = [(planta, areas_planta(arbol, res, visibles, filtros)) for planta, arbol in plantas.items()]
    if len(bloques) == 1:
        cuerpo = bloques[0][1]
    else:
        cuerpo = "".join(f'<div class="pl-planta"><div class="pl-planta-nom">{esc(pl)}</div><div class="pl-areas">{ar}</div></div>'
                         for pl, ar in bloques)
    leyenda = "".join(f'<span><span class="punto" style="background:{COLOR[k]}"></span>{CONDICION[k]}</span>'
                      for k in ("normal", "alerta", "vencida", "bajo_minimo", "insuficiente"))
    return ('<div class="card"><div class="card-cab"><h2>Plano de planta</h2>'
            '<span class="muted">Esquema sin escala · selecciona un equipo para ver sus CML</span></div>'
            f'<div class="plano"><span class="pl-norte" aria-hidden="true">N<br>↑</span>{cuerpo}</div>'
            f'<div class="pl-leyenda">{leyenda}<span><span class="pl-aviso mini" style="--c:{COLOR["alerta"]}">{TRIANGULO}</span>'
            'Aviso: CML en alerta, vencido o bajo el mínimo</span></div></div>')


def areas_planta(arbol, res, visibles, filtros):
    """Áreas (con sus sistemas y equipos) de una planta, para el plano."""
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
        marcada = filtros.get("area") == area
        sel = " sel" if marcada else ""
        ayuda_area = "Clic de nuevo para ver todas las áreas" if marcada else "Filtrar indicadores y tabla por esta área"
        quitar = '<span class="pl-area-x" aria-hidden="true">✕</span>' if marcada else ""
        areas.append(f'<section class="pl-area{sel}"><button class="pl-area-cab" data-act="ir_area" data-area="{esc(area)}" '
                     f'aria-pressed="{"true" if marcada else "false"}" title="{ayuda_area}">'
                     f'<span>{esc(area)}<small>{n_eq} equipo(s){" · filtrando" if marcada else ""}</small></span>{av}{quitar}</button>'
                     f'{"".join(sistemas)}</section>')
    return "".join(areas)


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
                          "Intervalo [años]": x["intervalo"], "Criterio": x["criterio"], "Referencia": x["ref_intervalo"],
                          "_eq": e["id"], "_cml": c["id"], "_problemas": v["problemas"]})
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
    nombres = {"area": lambda v: v, "familia": lambda v: FAMILIAS.get(v, v), "cond": lambda v: CONDICION.get(v, v)}
    chips = "".join(f'<button class="filtro-chip" data-act="quitar_filtro" data-campo="{k}" title="Quitar este filtro">'
                    f'{esc(nombres[k](v))}<span aria-hidden="true">✕</span></button>' for k, v in filtros.items() if v and k in nombres)
    activos_txt = ('<div class="filtros-activos" role="status"><span class="muted">Mostrando solo:</span>' + chips
                   + '<button class="enlace" data-act="limpiar_filtros">Quitar filtros</button></div>') if activos else ""
    h = ['<div class="cabecera"><h1>Estado de la planta</h1>'
         '<span class="desc">Plano por áreas y puntos de monitoreo, del más grave al menos grave</span></div>',
         activos_txt,
         '<div class="stats">', stat("Equipos", n_eq, sub=f"{len(filas)} CML" + (" (filtrado)" if activos else ""), clase="destacado")]
    for k, n in cuenta.items():
        h.append(f'<div class="stat estado" style="--c:{COLOR[k]}"><div class="l">{CONDICION[k]}</div>'
                 f'<div class="v"><span style="color:{COLOR[k]}">{ICONO[k]}</span>{n}</div></div>')
    h.append('</div>' + plano(data, res, filtros))
    h.append(f'<div class="card"><div class="card-cab"><h2>Puntos de monitoreo (CML)</h2>{barra}</div>'
             '<div class="tabla-scroll"><table class="tabla-fija" id="tabla-cml"><tr><th>CML · equipo</th><th>Componente</th><th class="num">t actual [mm]</th>'
             '<th class="num">t mín [mm]</th><th class="num">CR [mm/año]</th><th class="num">RL [años]</th><th>Próxima</th><th>Condición</th></tr>')
    for fl in filas:
        h.append(f'<tr class="click" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(fl["_eq"])}" data-cml="{esc(fl["_cml"] or "")}">'
                 f'<td><b>{esc(fl["CML"])}</b><div class="muted">{esc(fl["Equipo"])} · {esc(fl["Familia"].split()[0])}</div></td>'
                 f'<td>{esc(fl.get("Componente", ""))}</td><td class="num">{f(fl.get("t_actual [mm]"))}</td>'
                 f'<td class="num">{f(fl.get("t_min [mm]"))}</td><td class="num">{f(fl.get("CR [mm/año]"), 3)}</td>'
                 f'<td class="num">{f(fl.get("RL [años]"), 1)}</td><td>{fecha_cl(fl.get("Próxima inspección"))}</td>'
                 f'<td>{badge(fl["Condición"])}</td></tr>')
    if not filas:
        h.append('<tr><td colspan="8" class="muted">Ningún CML coincide con los filtros.</td></tr>')
    h.append('</table></div><div class="muted" style="margin-top:8px">Ordenado por severidad. Clic en una fila para abrir el equipo.</div></div>')
    h.append(calidad_datos(data, res, filtros))
    return "".join(h)


# ------------------------------------------------------------------ calidad de datos (F3)
def tipo_aviso(msg):
    m = msg.lower()
    for clave, tipo in (("insuficiente", "Información insuficiente"), ("posterior", "Fuera de la fecha de evaluación"),
                        ("futura", "Fecha futura"), ("duplicad", "Fechas duplicadas"), ("inconsistente", "Fechas inconsistentes"),
                        ("nula o negativa", "CR nula o negativa"), ("reiniciada", "Serie reiniciada"), ("inválid", "Dato inválido")):
        if clave in m:
            return tipo
    return "Otro"


def avisos_datos(data, res, filtros=None):
    """Reúne los avisos de calidad de datos de los CML (§4.4 del enunciado), respetando los filtros de Planta."""
    out = []
    for e in filtrar(data, res, filtros or {}):
        r = res[e["id"]]
        if r["error"]:
            out.append({"eq": e, "cml": None, "tipo": "Error de cálculo", "msg": r["error"]})
            continue
        for c in e["cmls"]:
            for msg in r["cmls"][c["id"]]["corrosion"]["problemas"]:
                out.append({"eq": e, "cml": c["id"], "tipo": tipo_aviso(msg), "msg": msg})
    return out


def calidad_datos(data, res, filtros=None):
    av = avisos_datos(data, res, filtros)
    if not av:
        return '<div class="card"><h2>Calidad de datos</h2><p class="muted">Sin avisos: todas las series son comparables y consistentes.</p></div>'
    filas = "".join(
        f'<tr class="click" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(a["eq"]["id"])}" data-cml="{esc(a["cml"] or "")}">'
        f'<td><b>{esc(a["cml"] or "—")}</b><div class="muted">{esc(a["eq"]["tag"])}</div></td>'
        f'<td><span class="etiqueta">{esc(a["tipo"])}</span></td><td>{esc(a["msg"])}</td><td class="fa-ir">Revisar ›</td></tr>' for a in av)
    n_cml = len({(a["eq"]["id"], a["cml"]) for a in av})
    cuerpo = ('<div class="tabla-scroll"><table><tr><th>CML · equipo</th><th>Tipo</th><th>Detalle</th><th></th></tr>' + filas + '</table></div>'
              '<div class="muted" style="margin-top:8px">Avisos detectados al calcular la corrosión: datos insuficientes, fechas inconsistentes, '
              'velocidades nulas o negativas y series reiniciadas por reemplazo, reparación o cambio de punto.</div>')
    return (f'<div class="card" id="calidad"><div class="card-cab"><h2>Calidad de datos</h2>'
            f'<span class="muted">{len(av)} aviso(s) en {n_cml} punto(s)</span></div>{cuerpo}</div>')


# ------------------------------------------------------------------ plan de inspección (F5)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def filas_plan(data, res):
    """Plan de mediciones de espesor: inmediatas y vencidas primero, luego por fecha; sin fecha al final."""
    filas = [fl for fl in filas_panel(data, res, {}) if fl["_cml"]]

    def grupo(fl):
        prox = fl["Próxima inspección"]
        if fl["Condición"] == "bajo_minimo":
            return (0, "Acción inmediata")
        if fl["Condición"] == "vencida":
            return (1, "Vencidas")
        if prox and re.match(r"^\d{4}-\d{2}", str(prox)):
            a, m = int(prox[:4]), int(prox[5:7])
            return (2, f"{MESES[m - 1].capitalize()} {a}")
        return (3, "Sin fecha: falta información")
    return sorted(((grupo(fl), fl) for fl in filas),
                  key=lambda t: (t[0][0], str(t[1]["Próxima inspección"] or ""), t[1]["CML"]))


def vista_plan(data, res):
    plan = filas_plan(data, res)
    hoy = hoy_eval()
    lim = date.fromordinal(hoy.toordinal() + 365).isoformat()
    n_inm = sum(1 for g, _ in plan if g[0] == 0)
    n_ven = sum(1 for g, _ in plan if g[0] == 1)
    n_12 = sum(1 for g, fl in plan if g[0] == 2 and fl["Próxima inspección"] <= lim)
    n_sin = sum(1 for g, _ in plan if g[0] == 3)
    h = ['<div class="cabecera"><h1>Plan de inspección</h1>'
         f'<span class="desc">Próximas mediciones de espesor por fecha · evaluado al {hoy:%d-%m-%Y}</span>'
         '<div class="der"><button class="chico secundario" data-act="exportar_plan">Exportar plan CSV</button></div></div>',
         '<div class="stats">',
         f'<div class="stat estado" style="--c:{COLOR["bajo_minimo"]}"><div class="l">Acción inmediata</div><div class="v">{n_inm}</div><div class="s">bajo el mínimo</div></div>',
         f'<div class="stat estado" style="--c:{COLOR["vencida"]}"><div class="l">Vencidas</div><div class="v">{n_ven}</div><div class="s">fecha ya cumplida</div></div>',
         stat("Próximos 12 meses", n_12, sub=f"hasta {fecha_cl(lim)}"),
         stat("Sin fecha", n_sin, sub="requieren 2.ª medición"),
         stat("Total", len(plan), sub="CML en el plan", clase="destacado"), '</div>', '<div class="card plan">']
    h.append('<div class="tabla-scroll"><table class="tabla-fija tabla-plan"><colgroup><col style="width:24%"><col style="width:11%">'
             '<col style="width:17%"><col><col style="width:17%"></colgroup>'
             '<tr><th>CML · equipo</th><th>Fecha</th><th>Tarea</th><th>Criterio</th><th>Condición</th></tr>')
    actual = None
    for (orden, titulo), fl in plan:
        if titulo != actual:
            n = sum(1 for g, _ in plan if g[1] == titulo)
            h.append(f'<tr class="plan-grupo"><th colspan="5">{esc(titulo)} <span class="muted">· {n} CML</span></th></tr>')
            actual = titulo
        fecha = "Inmediata" if orden == 0 else fecha_cl(fl["Próxima inspección"])
        iv = f'{f(fl["Intervalo [años]"], 1)} años · ' if fl["Intervalo [años]"] else ""
        h.append(f'<tr class="click" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(fl["_eq"])}" data-cml="{esc(fl["_cml"])}">'
                 f'<td><b>{esc(fl["CML"])}</b><div class="muted">{esc(fl["Equipo"])} · {esc(fl.get("Componente", ""))}</div></td>'
                 f'<td><b>{fecha}</b></td><td>Medición de espesores (UT)</td>'
                 f'<td>{iv}{esc(fl["Criterio"])}<div class="muted">{esc(fl["Referencia"])}</div></td><td>{badge(fl["Condición"])}</td></tr>')
    if not plan:
        h.append('<tr><td colspan="5" class="muted">No hay CML registrados.</td></tr>')
    h.append('</table></div>')
    h.append('</div>')
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
         stat("t actual", f(v["t_actual"]), "mm", fecha_cl(v["fecha_actual"]), ayuda_k="t_actual"),
         stat("t mínimo", f(x["t_min"]), "mm", "servicio", ayuda_k="t_min"),
         stat("t alerta", f(x["t_alerta"]), "mm", "t_min + CR·2 años", ayuda_k="t_alerta"),
         stat("Corrosión", f(v["cr"], 3), "mm/año", "adoptada", ayuda_k="cr"),
         stat("Vida remanente", f(x["rl"], 1), "años", ayuda_k="rl"),
         stat("Próxima inspección", prox_txt(x), "", "evaluar FFS / reparar" if x.get("proxima_txt") else f"intervalo {f(x['intervalo'], 1)} años",
              "destacado", ayuda_k="proxima"),
         '</div>']
    for p in v["problemas"]:
        h.append(f'<div class="error">✕ {esc(p)}</div>')
    if eq["familia"] == "tanque":
        h.append('<div class="info">Alcance API 653: solo espesores del manto. Fondo, techo e inspección interna: datos pendientes.</div>')
    h.append(f'<div class="grid-cml"><div class="card grafico">{grafico(eq, c, x)}</div>'
             f'<div class="card no-imprimir"><h2>Nueva medición</h2>{form_medicion(c)}</div></div>')
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
    h.append(f'<div class="card"><h2>Historial de mediciones ({len(filas)})</h2><div class="tabla-scroll">{tabla}</div></div>')
    h.append(plegable("Ver cálculos (ecuaciones, entradas y referencias)", calculos_cml(eq, c, x)))
    pos = ('<form class="f" id="form_xy">'
           f'<label>x [%]<input type="number" step="any" name="x" value="{pct(c["x"])}" min="0" max="100"></label>'
           f'<label>y [%]<input type="number" step="any" name="y" value="{pct(c["y"])}" min="0" max="100"></label>'
           '<button data-act="mover_cml" class="secundario">Mover marcador</button>'
           '<button data-act="borrar_cml" class="peligro">Eliminar CML</button></form>')
    h.append(plegable("Posición del marcador y opciones del CML", pos))
    return "".join(h)


def form_medicion(c):
    hoy = min(hoy_eval(), date.today()).isoformat()
    tec = "".join(f"<option>{t}</option>" for t in TECNICAS)
    ev = "".join(f'<option value="{k}">{v}</option>' for k, v in EVENTOS.items())
    return (f'<form class="f col" id="form_med">'
            f'<label>Fecha<input type="date" name="fecha" value="{hoy}" max="{date.today().isoformat()}" required></label>'
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
    hoy = hoy_eval()
    txt_hoy = "Hoy" if hoy == date.today() else f"Evaluación {hoy:%d-%m-%Y}"
    fechas = [date.fromisoformat(m["fecha"][:10]) for m in ms] or [hoy]
    if x["proxima"]:
        fechas.append(date.fromisoformat(x["proxima"]))
    x_fin = max(fechas + [hoy])

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
    ax.axvline(hoy, color=MUTED, lw=1, alpha=.6, zorder=1)
    ax.annotate(txt_hoy, (hoy, 1.0), xycoords=("data", "axes fraction"), xytext=(-4, -14),
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

    if not r["error"] and eq["cmls"]:
        filas = "".join(
            f'<tr><td>{esc(cc["id"])}</td><td>{esc(cc["componente"])}</td><td class="num">{f(r["cmls"][cc["id"]]["corrosion"]["t_actual"])}</td>'
            f'<td class="num">{f(r["cmls"][cc["id"]]["t_min"])}</td><td class="num">{f(r["cmls"][cc["id"]]["corrosion"]["cr"], 3)}</td>'
            f'<td class="num">{f(r["cmls"][cc["id"]]["rl"], 1)}</td><td>{prox_txt(r["cmls"][cc["id"]])}</td>'
            f'<td>{CONDICION[r["cmls"][cc["id"]]["condicion"]]}</td></tr>' for cc in eq["cmls"])
        h.append('<div class="card solo-imprimir"><h2>Resumen de CML</h2><table><tr><th>CML</th><th>Componente</th><th class="num">t actual [mm]</th>'
                 '<th class="num">t mín [mm]</th><th class="num">CR [mm/año]</th><th class="num">RL [años]</th><th>Próxima</th><th>Condición</th></tr>'
                 + filas + '</table></div>')
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


def pagina_equipo(data, res, eq, cml_sel, sub="resumen", base=None, cambio=""):
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
           '<div class="der"><button class="chico secundario" data-act="imprimir" title="Informe para imprimir o guardar en PDF">Imprimir ficha</button>'
           '<button class="chico secundario" data-act="editar_eq">Editar</button>'
           '<button class="chico peligro" data-act="borrar_eq">Eliminar</button></div></div>'
           f'<div class="solo-imprimir">Informe de integridad · {esc(eq["tag"])} · evaluado al {hoy_eval():%d-%m-%Y} · '
           f'{esc(u["planta"])} › {esc(u["area"])} › {esc(u["sistema"])}</div>'
           f'<div class="segmentado" role="tablist" aria-label="Vista del equipo">{pestanas}</div>')
    cuerpo = (vista_diseno(eq, r, cabecera=False, base=base, cambio=cambio) if sub == "diseno"
              else vista_equipo(data, res, eq, cml_sel, cabecera=False))
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


COLOR_FAMILIA = {"tuberia": ("#1f7a4d", "#3dbb83"), "recipiente": ("#0e6f8f", "#3fb0d6"), "tanque": ("#b5651d", "#eaa53f")}
ICONO_KPI = {
    "equipos": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V9l8-5 8 5v11M9 20v-6h6v6" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    "cml": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>',
    "accion": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3L2 21h20Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 10v5M12 18v.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
    "fecha": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M8 3v4M16 3v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
}


PLURAL = {"tuberia": "Tuberías", "recipiente": "Recipientes", "tanque": "Tanques"}
DESC_FAMILIA = {"tuberia": "Circuitos y tramos rectos de cañería de proceso.",
                "recipiente": "Envolventes cilíndricas de recipientes a presión.",
                "tanque": "Manto de tanques de almacenamiento atmosféricos, por virola."}
ORDEN_COND = {"error": -1, "bajo_minimo": 0, "vencida": 1, "alerta": 2, "insuficiente": 3, "normal": 4}


def peor_condicion(conds):
    conds = list(conds)
    return min(conds, key=lambda c: ORDEN_COND.get(c, 5)) if conds else "insuficiente"


def _marcadores(eqs, res, puntos):
    """Un punto por equipo de la familia (color = su peor condición); los que requieren acción laten."""
    h = []
    for e, (x, y) in zip(eqs, puntos):
        cond = res[e["id"]]["cond"]
        late = f'<circle class="ilu-pulso" cx="{x}" cy="{y}" r="9" fill="{COLOR[cond]}"/>' if cond in AVISO else ""
        h.append(f'{late}<circle cx="{x}" cy="{y}" r="7" fill="{COLOR[cond]}" stroke="#fff" stroke-width="2.5">'
                 f'<title>{esc(e["tag"])} · {CONDICION[cond]}</title></circle>')
    return "".join(h)


def _rotulo(x, y, texto, cond):
    ancho = 22 + 7.2 * len(texto)
    return (f'<g transform="translate({x - ancho / 2:.0f},{y})"><rect width="{ancho:.0f}" height="26" rx="13" fill="#fff" '
            f'stroke="rgba(0,0,0,.08)"/><circle cx="13" cy="13" r="4.5" fill="{COLOR[cond]}"/>'
            f'<text x="23" y="17.5" font-size="12.5" font-weight="600" fill="#1d1d1f">{esc(texto)}</text></g>')


def ilustracion_planta(data, res):
    """Escena esquemática (sin escala): bomba → línea → separador → rack → tanque, con los CML reales del caso."""
    fam = {f: [e for e in data["equipos"] if e["familia"] == f] for f in FAMILIAS}

    def grupo(f):
        """Atributos del dibujo de una familia: abre Planta filtrada por esa familia (si tiene equipos)."""
        if not fam[f]:
            return '<g class="ilu-eq vacio">'
        return (f'<g class="ilu-eq" role="button" tabindex="0" data-act="ir_familia" data-familia="{f}" '
                f'aria-label="{PLURAL[f]}: {len(fam[f])} equipo(s). Ver en Planta">')

    def extra(f, puntos, x, y):
        eqs = fam[f]
        if not eqs:
            return ""
        cond = peor_condicion(res[e["id"]]["cond"] for e in eqs)
        return _marcadores(eqs, res, puntos) + _rotulo(x, y, f"{PLURAL[f]} · {len(eqs)}", cond)
    g = ['<svg class="ilu" viewBox="0 0 1000 320" role="img" aria-label="Esquema de la planta con el estado de sus puntos de monitoreo">',
         '<defs><linearGradient id="ilu-suelo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e7efe9"/>'
         '<stop offset="1" stop-color="#e7efe9" stop-opacity="0"/></linearGradient>'
         '<linearGradient id="ilu-rec" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#d7eef6"/><stop offset=".5" stop-color="#fff"/>'
         '<stop offset="1" stop-color="#cfe6ef"/></linearGradient>'
         '<linearGradient id="ilu-tk" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f6e6cf"/><stop offset=".5" stop-color="#fff"/>'
         '<stop offset="1" stop-color="#f1dcc0"/></linearGradient></defs>',
         '<rect x="0" y="268" width="1000" height="52" fill="url(#ilu-suelo)"/><path d="M20 268H980" stroke="#c9d6cd" stroke-width="2"/>',
         # rack de cañerías
         '<g stroke="#b9c4bd" stroke-width="4" stroke-linecap="round"><path d="M560 268V118M690 268V118M545 118H705M545 150H705"/></g>']
    # bomba + línea de descarga
    g.append(grupo("tuberia") +
             '<rect x="60" y="226" width="78" height="42" rx="8" fill="#eaf5ef" stroke="#1f7a4d" stroke-width="2.5"/>'
             '<circle cx="99" cy="226" r="24" fill="#fff" stroke="#1f7a4d" stroke-width="2.5"/><circle cx="99" cy="226" r="8" fill="#1f7a4d"/>'
             '<path d="M123 226H250V150H392" fill="none" stroke="#1f7a4d" stroke-width="16" stroke-linejoin="round"/>'
             '<path d="M123 226H250V150H392" fill="none" stroke="#e9f6ef" stroke-width="10" stroke-linejoin="round"/>'
             '<path d="M180 214v24M300 138v24M360 138v24" stroke="#1f7a4d" stroke-width="4"/>'
             '<path d="M200 234v34M310 158v110M190 268h20M300 268h20" stroke="#b9c4bd" stroke-width="3" stroke-linecap="round"/>'
             + extra("tuberia", [(165, 226), (225, 226), (250, 190), (330, 150)], 190, 168)
             + '</g>')
    # separador vertical
    g.append(grupo("recipiente") +
             '<path d="M398 72Q398 34 445 34T492 72V214Q492 252 445 252T398 214Z" fill="url(#ilu-rec)" stroke="#0e6f8f" stroke-width="3"/>'
             '<path d="M398 120h94M398 168h94" stroke="#0e6f8f" stroke-width="1.5" stroke-dasharray="5 5" opacity=".6"/>'
             '<path d="M445 34V14M445 252v16M412 246l-8 22M478 246l8 22" stroke="#0e6f8f" stroke-width="3" stroke-linecap="round"/>'
             '<path d="M445 14H560V118" fill="none" stroke="#0e6f8f" stroke-width="7" stroke-linejoin="round"/>'
             + extra("recipiente", [(445, 96), (445, 144), (445, 196), (420, 120)], 445, 278)
             + '</g>')
    # línea por el rack hacia el tanque
    g.append('<path d="M560 118H745V150" fill="none" stroke="#0e6f8f" stroke-width="7" stroke-linejoin="round"/>')
    # tanque atmosférico
    g.append(grupo("tanque") +
             '<path d="M735 150L840 112L945 150V268H735Z" fill="url(#ilu-tk)" stroke="#b5651d" stroke-width="3" stroke-linejoin="round"/>'
             '<path d="M735 150H945M735 189H945M735 228H945" stroke="#b5651d" stroke-width="1.5" opacity=".55"/>'
             '<path d="M755 268L800 150" stroke="#b5651d" stroke-width="3"/><path d="M765 268L810 150" stroke="#b5651d" stroke-width="1.5" stroke-dasharray="3 5"/>'
             + extra("tanque", [(880, 248), (880, 208), (880, 170), (910, 208)], 840, 76)
             + '</g>')
    g.append('</svg>')
    return "".join(g)


def kpi(clave, color, label, valor, sub=""):
    return (f'<div class="kpi" style="--k:{color}"><span class="kpi-ico">{ICONO_KPI[clave]}</span>'
            f'<div><div class="kpi-v">{valor}</div><div class="kpi-l">{label}</div>{f"<div class=kpi-s>{sub}</div>" if sub else ""}</div></div>')


def vista_inicio(data, res):
    """Portada: qué es la app, el estado de la planta de un vistazo, qué requiere atención y cómo se usa."""
    filas = filas_panel(data, res, {})
    atencion = puntos_atencion(data, res)
    proximas = sorted(fl["Próxima inspección"] for fl in filas
                      if fl["Próxima inspección"] and re.match(r"^\d{4}-", str(fl["Próxima inspección"]))
                      and fl["Próxima inspección"] >= hoy_eval().isoformat())
    n_crit = sum(1 for fl in atencion if fl["Condición"] in ("bajo_minimo", "vencida"))
    leyenda = "".join(f'<span><i style="background:{COLOR[k]}"></i>{CONDICION[k]}</span>'
                      for k in ("normal", "alerta", "vencida", "bajo_minimo", "insuficiente"))
    h = ['<section class="hero-panel">',
         '<span class="pildora-hero">Prototipo académico · MAN040-B · ASME / API</span>',
         '<div class="hero"><h1>Integridad de equipos estáticos,<br><span class="degradado">en un solo lugar.</span></h1>'
         '<p class="lead">Registra mediciones de espesor, calcula corrosión y vida remanente, programa la próxima inspección '
         'según API 510, 570 y 653, y prioriza por riesgo con API RP 581.</p>'
         '<div class="cta"><button data-act="tab" data-tab="planta">Ver estado de la planta</button>'
         + ('<button class="secundario" data-act="ir_critico">Ir al punto más crítico</button>' if atencion else '')
         + '</div></div>',
         f'<figure class="ilu-marco">{ilustracion_planta(data, res)}'
         f'<figcaption><span class="ilu-ayuda">Esquema sin escala · cada punto es un equipo con su condición (la peor de sus CML) · clic en una familia para verla en Planta</span>'
         f'<span class="ilu-leyenda">{leyenda}</span></figcaption></figure>',
         '</section>',
         '<div class="kpis">',
         kpi("equipos", "#1f7a4d", "Equipos", len(data["equipos"]), f'{len({e["familia"] for e in data["equipos"]})} familias'),
         kpi("cml", "#0e6f8f", "Puntos de monitoreo", len(filas), "CML / TML"),
         kpi("accion", COLOR["bajo_minimo"] if n_crit else COLOR["normal"], "Requieren acción", len(atencion),
             f"{n_crit} crítico(s) · {len(atencion) - n_crit} en alerta"),
         kpi("fecha", "#b5651d", "Próxima inspección", fecha_cl(proximas[0]) if proximas else "—", f"evaluado al {hoy_eval():%d-%m-%Y}"),
         '</div>']

    if atencion:
        items = "".join(
            f'<li class="fila-accion" role="button" tabindex="0" data-act="sel_eq" data-id="{esc(fl["_eq"])}" data-cml="{esc(fl["_cml"])}" '
            f'style="--c:{COLOR[fl["Condición"]]}">'
            f'{badge(fl["Condición"])}<span class="fa-txt"><b>{esc(fl["CML"])}</b> · {esc(fl["Equipo"])}'
            f'<small>{esc(fl.get("Componente", ""))} · t actual {f(fl.get("t_actual [mm]"))} mm · t mín {f(fl.get("t_min [mm]"))} mm</small></span>'
            f'<span class="fa-ir">{"Inmediata" if fl["Condición"] == "bajo_minimo" else fecha_cl(fl["Próxima inspección"])} ›</span></li>'
            for fl in atencion[:5])
        h.append(f'<div class="card card-atencion"><div class="card-cab"><h2>Requiere atención</h2>'
                 f'<button class="chico secundario" data-act="tab" data-tab="planta">Ver todos los CML</button></div>'
                 f'<ul class="lista-accion">{items}</ul></div>')
    else:
        h.append('<div class="card"><h2>Todo en orden</h2><p class="muted">Ningún CML bajo el mínimo, vencido ni en alerta.</p></div>')

    tarjetas = []
    for fam, nombre in FAMILIAS.items():
        eqs = [e for e in data["equipos"] if e["familia"] == fam]
        c1, c2 = COLOR_FAMILIA[fam]
        n_cml = sum(len(x["cmls"]) for x in eqs)
        cond = peor_condicion(res[e["id"]]["cond"] for e in eqs) if eqs else None
        orden = sorted(eqs, key=lambda e: ORDEN_COND.get(res[e["id"]]["cond"], 5))
        resumen = (f'{len(eqs)} equipo(s) · {n_cml} CML · peor condición: {badge(cond)}' if eqs
                   else '<span class="muted">Sin equipos registrados en esta familia.</span>')
        if eqs:
            items = "".join(
                f'<button role="menuitem" data-act="sel_eq" data-id="{esc(e["id"])}">'
                f'<span class="punto" style="background:{COLOR[res[e["id"]]["cond"]]}"></span>'
                f'<span class="fm-txt"><b>{esc(e["tag"])}</b><small>{esc(e["descripcion"])}</small></span>'
                f'<span class="fm-cond">{CONDICION[res[e["id"]]["cond"]]}</span></button>' for e in orden)
            cabeza = (f'<details class="fam-menu"><summary class="familia-ilu" aria-label="{nombre}: ver sus {len(eqs)} equipo(s)">'
                      f'{BOCETO[fam]}<span class="fam-menu-btn">{len(eqs)} equipo(s) ▾</span></summary>'
                      f'<div class="fam-menu-panel" role="menu" aria-label="Equipos: {nombre}">'
                      f'<div class="fm-tit">{PLURAL[fam]} registrados · del más grave al menos grave</div>{items}'
                      f'<hr><button role="menuitem" class="fm-todos" data-act="ir_familia" data-familia="{fam}">'
                      f'Ver {PLURAL[fam].lower()} en Planta ›</button></div></details>')
        else:
            cabeza = f'<div class="familia-ilu">{BOCETO[fam]}</div>'
        tarjetas.append(
            f'<div class="familia" style="--f1:{c1};--f2:{c2}">{cabeza}'
            f'<div class="familia-txt"><span class="eyebrow">{CODIGOS[fam]}</span><h3>{nombre}</h3>'
            f'<p>{DESC_FAMILIA[fam]}</p><div class="familia-resumen">{resumen}</div></div>'
            f'<div class="familia-pie"><button class="secundario chico" data-act="ir_familia" data-familia="{fam}" '
            f'{"disabled" if not eqs else ""}>Ver {PLURAL[fam].lower()} en Planta ›</button></div></div>')
    h.append('<div class="titulo-centro"><span class="eyebrow">Tres familias, un mismo flujo</span>'
             f'<h2 class="titulo-seccion">Equipos por familia</h2></div><div class="familias">{"".join(tarjetas)}</div>')

    pasos = [("Elige un equipo", "Desde Planta o Equipos. Verás su ubicación técnica, esquema y CML; se abre el más crítico.", "#1f7a4d"),
             ("Revisa el CML", "Espesor actual, mínimo y de alerta, corrosión, vida remanente y la tendencia en el gráfico.", "#0e6f8f"),
             ("Registra una medición", "Ingresa la lectura de UT: la condición y la próxima inspección se recalculan al instante.", "#b5651d"),
             ("Evalúa el riesgo", "En Riesgo (RBI) ajusta consecuencias e inspecciones y observa la prioridad en la matriz.", "#7a4fb5")]
    h.append('<div class="titulo-centro"><span class="eyebrow">En cuatro pasos</span><h2 class="titulo-seccion">Cómo se usa</h2></div>'
             '<ol class="pasos">' + "".join(
                 f'<li style="--p:{c}"><span class="paso-n">{i}</span><h3>{t}</h3><p>{d}</p></li>'
                 for i, (t, d, c) in enumerate(pasos, 1)) + '</ol>')
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


def vista_diseno(eq, res_eq, cabecera=True, base=None, cambio=""):
    fam = eq["familia"]
    d = eq["diseno"]
    mat = MATERIALES[eq["material"]]
    base = base or {}
    campos = "".join(campo_num("diseno", k, label, d.get(k, ""), base.get(k)) for k, label in CAMPOS_DISENO[fam])
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
         aviso_cambio(cambio),
         f'<div class="card"><h2>Variables de diseño</h2><form class="f">{campos}</form>'
         f'<div class="info" style="margin-top:12px">{s_txt}&nbsp;<span class="muted">· {esc(mat["ref"])}</span></div>'
         '<div class="muted">Cambia un valor y presiona Enter o Tab: se recalcula todo el equipo. '
         'Los campos distintos del caso demo quedan marcados; «↺» vuelve al valor original.</div></div>']
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
        items = [("Nominal" + ayuda("nominal"), tn, "#aeaeb2", "Diseño y fabricación"),
                 ("Diseño / compra" + ayuda("diseno"), dis["valor"], "#5fb38a", "Diseño y fabricación"),
                 ("Requerido por cálculo" + ayuda("requerido"), dis["t_calc"], "#9ccfb3", "Diseño y fabricación"),
                 ("Medido (último)" + ayuda("medido"), x["corrosion"]["t_actual"], "#1f7a4d", "En servicio"),
                 ("Alerta" + ayuda("t_alerta"), x["t_alerta"], "#fab219", "En servicio"),
                 ("Mínimo en servicio" + ayuda("t_min"), x["t_min"], "#d03b3b", "En servicio")]
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
    f_eval = hoy_eval().isoformat()  # fecha de evaluación global del proyecto
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


RBI_BASE = {"confianza": "baja", "inspecciones": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}, "pscore": 50, "f_om": 1.0,
            "C_A_m2": 100.0, "C_E": 100000.0, "moneda": "USD",
            "base_valoracion": "Valores por defecto: ajustar al escenario del equipo",
            "escenario": "Fuga por adelgazamiento generalizado de la envolvente"}
COLOR_NIVEL = {"Bajo": "#0ca30c", "Medio": "#fab219", "Medio-alto": "#ec835a", "Alto": "#d03b3b"}


def recipientes(data):
    return [e for e in data["equipos"] if e["familia"] == "recipiente"]


def riesgos_planta(data, res):
    """Riesgo de cada recipiente con evaluación RBI (para la matriz de la planta)."""
    out = []
    for e in recipientes(data):
        if e.get("rbi") and not res[e["id"]]["error"] and e["cmls"]:
            try:
                out.append((e, calcular_rbi(e, res[e["id"]])))
            except (ValueError, KeyError, StopIteration):
                continue
    return out


def matriz_planta(puntos, sel_id, rango=None):
    """Matriz 5×5 con un punto por equipo: POF vs. la mayor categoría de consecuencia (área o económica)."""
    celdas = {}
    for e, R in puntos:
        r = R["r"]
        cof = max(r["cat_area"], r["cat_fin"])
        celdas.setdefault((r["cat_pof"], cof), []).append(e)
    h = ['<div class="matriz matriz-planta">']
    for p_ in "54321":
        h.append(f'<div class="eje">{p_}</div>')
        for c in "ABCDE":
            n = rbi.nivel_riesgo(int(p_), c)
            chips = "".join(f'<button class="m-chip {"sel" if e["id"] == sel_id else ""}" data-act="sel_rbi_eq" data-id="{esc(e["id"])}" '
                            f'title="{esc(e["tag"])}" aria-label="{esc(e["tag"])}">{(rango or {}).get(e["id"], esc(e["tag"]))}</button>'
                            for e in celdas.get((p_, c), []))
            h.append(f'<div class="m-{n}" title="POF {p_} · COF {c}: {n}">{chips}</div>')
    h.append('<div></div>' + "".join(f'<div class="eje">{c}</div>' for c in "ABCDE"))
    h.append('</div><div class="matriz-pie">Filas: POF · Columnas: mayor categoría de consecuencia (área o económica)</div>')
    return "".join(h)


def vista_rbi(data, res, eq_id=None, base=None, cambio=""):
    recs = recipientes(data)
    if not recs:
        return '<div class="info">No hay recipientes a presión. El RBI implementado cubre adelgazamiento generalizado de recipientes.</div>'
    eq = next((e for e in recs if e["id"] == eq_id), None) or next((e for e in recs if e.get("rbi")), recs[0])
    opts = "".join(f'<option value="{esc(e["id"])}" {"selected" if e is eq else ""}>{esc(e["tag"])}'
                   f'{"" if e.get("rbi") else " (sin evaluar)"}</option>' for e in recs)
    selector = (f'<label class="sel-rbi">Equipo<select data-act="sel_rbi" aria-label="Equipo a evaluar">{opts}</select></label>'
                if len(recs) > 1 else "")
    cab = (f'<div class="cabecera"><h1>RBI · {esc(eq["tag"])}</h1><span class="desc">Adelgazamiento generalizado · API RP 580 / 581 · '
           f'evaluado al {hoy_eval():%d-%m-%Y}</span><div class="der">{selector}</div></div>')
    puntos = riesgos_planta(data, res)
    planta = ""
    if len(puntos) > 1:
        orden = sorted(puntos, key=lambda t: (-["Bajo", "Medio", "Medio-alto", "Alto"].index(t[1]["r"]["nivel"]), -t[1]["r"]["R_E"]))
        ranking = "".join(
            f'<tr class="click {"sel" if e is eq else ""}" role="button" tabindex="0" data-act="sel_rbi_eq" data-id="{esc(e["id"])}">'
            f'<td>{i}</td><td><b>{esc(e["tag"])}</b><div class="muted">{esc(R["cml"]["id"])}</div></td>'
            f'<td class="num">{f(R["con"]["Df"], 1)}</td><td class="num">{sci(R["r"]["Pf"])}</td>'
            f'<td class="num">{f(R["r"]["R_E"], 0 if R["r"]["R_E"] >= 100 else 2)} {esc(R["r"]["moneda"])}</td>'
            f'<td><span class="etiqueta" style="box-shadow:inset 3px 0 0 {COLOR_NIVEL[R["r"]["nivel"]]}">{R["r"]["nivel"]}</span></td></tr>'
            for i, (e, R) in enumerate(orden, 1))
        planta = (f'<div class="card"><div class="card-cab"><h2>Riesgo de la planta</h2>'
                  f'<span class="muted">{len(puntos)} equipos evaluados · clic en un equipo para verlo</span></div>'
                  f'<div class="rbi-planta"><div>{matriz_planta(puntos, eq["id"], {e["id"]: i for i, (e, _) in enumerate(orden, 1)})}</div>'
                  '<div class="tabla-scroll"><table><tr><th>#</th><th>Equipo</th><th class="num">D_f</th><th class="num">P_f</th>'
                  f'<th class="num">R_E</th><th>Nivel</th></tr>{ranking}</table>'
                  '<div class="muted" style="margin-top:8px">Ordenado por nivel de riesgo y luego por riesgo económico. '
                  'El número de la matriz corresponde a la columna #.</div></div></div></div>')
    if not eq.get("rbi"):
        return (cab + '<div class="card"><h2>Este equipo aún no tiene evaluación RBI</h2>'
                '<p class="muted">Se creará con valores por defecto (confianza baja, sin inspecciones, C<sub>A</sub> = 100 m², '
                'C<sub>E</sub> = 100.000 USD) que debes ajustar al escenario real del equipo.</p>'
                '<button data-act="crear_rbi">Crear evaluación RBI</button></div>' + planta)
    if res[eq["id"]]["error"]:
        return cab + f'<div class="error">{esc(res[eq["id"]]["error"])}</div>'
    if not eq["cmls"]:
        return cab + '<div class="info">El equipo no tiene CML: agrega al menos uno con mediciones para evaluar el riesgo.</div>'
    cfg = eq["rbi"]
    base = base or {}
    R = calcular_rbi(eq, res[eq["id"]])
    p, e, r = R["con"]["pasos"], R["ent"], R["r"]
    cml_opts = "".join(f'<option {"selected" if c["id"] == cfg["cml"] else ""}>{esc(c["id"])}</option>' for c in eq["cmls"])
    conf_opts = "".join(f'<option {"selected" if k == cfg["confianza"] else ""}>{k}</option>' for k in rbi.PRIOR)
    b_insp = base.get("inspecciones") or {}

    def num(campo, label, val, b=None, step="any", fmt=None):
        return campo_num("rbi", campo, label, val, b, step, fmt)

    color_nivel = COLOR_NIVEL[r["nivel"]]
    h = [cab, aviso_cambio(cambio),
         '<div class="stats">',
         stat("Factor de daño D_f", f(R["con"]["Df"], 1), "", "adimensional", ayuda_k="df"),
         stat("Frecuencia de falla P_f", sci(r["Pf"]), "1/año", f"categoría POF {r['cat_pof']}", ayuda_k="pf"),
         stat("Riesgo de área R_A", f(r["R_A"], 4), "m²/año", f"C_A categoría {r['cat_area']}", ayuda_k="ra"),
         stat("Riesgo económico R_E", f(r["R_E"], 0 if r["R_E"] >= 100 else 2), f"{esc(r['moneda'])}/año", f"C_E categoría {r['cat_fin']}", ayuda_k="re"),
         f'<div class="stat estado" style="--c:{color_nivel}"><div class="l">Prioridad{ayuda("prioridad")}</div><div class="v">{r["nivel"]}</div>'
         f'<div class="s">{esc(r["accion"].split(":")[0])}</div></div>',
         '</div>']
    miles = lambda v: f(v, 0)  # noqa: E731
    entradas = ('<form class="f col">'
                f'<label>CML gobernante<select data-act="rbi" data-campo="cml">{cml_opts}</select></label>'
                f'<label>Fecha de evaluación<span class="dato-fijo" title="Fecha global del proyecto: se cambia en la barra superior">'
                f'{fecha_cl(R["f_eval"])} <small>· barra superior</small></span></label>'
                f'<label>Confianza en la CR<select data-act="rbi" data-campo="confianza">{conf_opts}</select></label>'
                + num("pscore", "Puntaje gestión [%]", cfg.get("pscore", 50), base.get("pscore"))
                + "".join(num(f"insp_{k}", f"Inspecciones {k}", cfg["inspecciones"].get(k, 0),
                              b_insp.get(k) if base else None, "1") for k in "ABCD")
                + num("C_A_m2", "Consecuencia de área C_A [m²]", cfg["C_A_m2"], base.get("C_A_m2"))
                + num("C_E", f"Consecuencia económica C_E [{esc(cfg.get('moneda', 'USD'))}]", cfg["C_E"], base.get("C_E"), fmt=miles)
                + f'<label>Moneda<input value="{esc(cfg.get("moneda", "USD"))}" data-act="rbi" data-campo="moneda"></label>'
                + num("f_om", "F_OM (monitoreo)", cfg.get("f_om", 1.0), base.get("f_om"))
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
    h.append(planta)
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
    # Caso de la demo: V-201 / CML-201-03, evaluado al 26-11-2026 (CR de largo plazo de sus 4 mediciones)
    v201 = co.velocidades([{"fecha": "2016-05-01", "espesor_mm": 16.0}, {"fecha": "2019-05-20", "espesor_mm": 13.5},
                           {"fecha": "2022-05-18", "espesor_mm": 11.4}, {"fecha": "2025-05-21", "espesor_mm": 9.5}])
    r201 = rbi.df_adelgazamiento(cr=v201["cr_lp"], edad=co.anios("2016-05-01", "2026-11-26"), t_rdi=16,
                                 t_min=es.recipiente_ug27(1.5, 750, 20 * KSI, 0.85)["valor"], S=20 * KSI, E=0.85,
                                 YS=38 * KSI, TS=70 * KSI, confianza="media", inspecciones={"B": 2})
    rr201 = rbi.riesgo(r201["Df"], 120, 450000)
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
        ("RBI demo", "D_f CML-201-03", "CR_LP = 0,7179 mm/año, age = 10,571 años (01-05-2016 → 26-11-2026), t = 16 mm, "
         "t_min = 9,672 mm, confianza media, 2 inspecciones B", "API 581 ec. 2.12–2.20", 205.5932, r201["Df"], "—"),
        ("RBI demo", "R_A CML-201-03", "P_f = 3,06·10⁻⁵ · 1 · 205,59 = 6,291·10⁻³ /año; C_A = 120 m²", "API 581 Parte 1 §4.1",
         0.75494, rr201["R_A"], "m²/año"),
        ("RBI demo", "R_E CML-201-03", "P_f = 6,291·10⁻³ /año; C_E = 450.000 USD", "API 581 Parte 1 §4.1",
         2831.02, rr201["R_E"], "USD/año"),
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
           '<li>RBI: modelo académico, solo adelgazamiento generalizado en recipientes (V-201 en la demo).</li><li>Datos de la demo: ficticios.</li></ul>')
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
