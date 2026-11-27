"""Aplicación PyScript: estado, eventos del navegador, persistencia e importación/exportación.

Seguridad: todo dato externo (archivo importado, localStorage, archivos subidos) se valida con
`proyecto.validar_proyecto` antes de usarse; los textos se escapan en `ui.esc`; los adjuntos solo
se aceptan como PNG/JPG/PDF verificando tamaño, tipo MIME y firma binaria.
"""
import asyncio
import base64
import copy
import json
import time
import traceback
from datetime import date, datetime

import pandas as pd
from pyodide.ffi import create_proxy, to_js
from pyodide.http import pyfetch
from pyscript import document, window

import proyecto
import ui

CLAVE = "giee_proyecto_v1"
LIMITES = {"importar": 25_000_000, "subir_img": 1_500_000, "subir_pdf": 3_000_000}
FIRMAS = {"image/png": b"\x89PNG", "image/jpeg": b"\xff\xd8\xff", "application/pdf": b"%PDF"}
FORM_ACCION = {"form_med": "add_med", "form_cml": "add_cml", "form_xy": "mover_cml", "form_eq": "guardar_eq"}
E = {"data": None, "eq": None, "cml": None, "tab": "inicio", "sub": "resumen", "filtros": {}, "editando": None,
     "rbi_eq": None, "cambio": "", "cambio_ruta": None, "demo": None, "buscar": "", "val_fam": "", "plegados": set(), "nuevo_cml": None, "nuevo_fam": "tuberia", "sucio": False}
VISTAS = ("inicio", "planta", "equipos", "plan", "rbi", "validacion", "acerca")
ETIQUETA_RBI = {"cml": "CML gobernante", "confianza": "Confianza en la CR", "pscore": "Puntaje de gestión [%]", "C_A_m2": "C_A [m²]",
                "C_E": "C_E", "f_om": "F_OM", "moneda": "Moneda", "base_valoracion": "Base de valoración"}
_ruta = {"actual": None}
_proxies = []  # referencias vivas a los proxies de eventos


# ------------------------------------------------------------------ utilidades
def attr(el, nombre):
    """Lee data-<nombre> sin lanzar error si no existe (en Pyodide un atributo ausente lanza AttributeError)."""
    if not hay(el) or not hasattr(el, "getAttribute"):
        return None
    return el.getAttribute(f"data-{nombre}")


def toast(msg, ms=3200, error=False):
    t = document.getElementById("toast")
    t.innerText = msg
    t.classList.toggle("toast-error", error)
    t.hidden = False
    p = create_proxy(lambda: setattr(t, "hidden", True))
    _proxies.append(p)
    window.setTimeout(p, ms)


def eq_actual():
    return next((e for e in E["data"]["equipos"] if e["id"] == E["eq"]), None)


def cml_actual(eq):
    return next((c for c in eq["cmls"] if c["id"] == E["cml"]), None) if eq else None


def leer_form(fid):
    form = document.getElementById(fid)
    out = {}
    if not hay(form):
        return out
    for i in range(form.elements.length):
        el = form.elements.item(i)
        if el.name:
            out[el.name] = el.value
    return out


def descargar(texto, nombre, mime):
    blob = window.Blob.new(to_js([texto]), to_js({"type": mime}, dict_converter=window.Object.fromEntries))
    url = window.URL.createObjectURL(blob)
    a = document.createElement("a")
    a.href, a.download = url, nombre
    a.click()
    window.URL.revokeObjectURL(url)


def estado_guardado():
    """Refleja en la barra superior si hay cambios pendientes de guardar."""
    b = document.getElementById("btn-guardar")
    if not hay(b):
        return
    b.classList.toggle("sucio", E["sucio"])
    b.querySelector(".bg-txt").innerText = "Guardar cambios" if E["sucio"] else "Guardado"
    b.setAttribute("aria-label", "Guardar cambios pendientes" if E["sucio"] else "Sin cambios pendientes")
    if E["sucio"]:
        document.getElementById("estado-guardado").innerText = "Cambios sin guardar"


def guardar_local(aviso=False):
    try:
        window.localStorage.setItem(CLAVE, json.dumps(E["data"], ensure_ascii=False))
        document.getElementById("estado-guardado").innerText = f"Guardado {datetime.now():%H:%M}"
        E["sucio"] = False
        estado_guardado()
        if aviso:
            toast("Cambios guardados en este navegador.")
        return True
    except Exception:  # noqa: BLE001 — QuotaExceededError u otro error del navegador
        document.getElementById("estado-guardado").innerText = "Sin guardar"
        toast("No se pudo guardar en el navegador (espacio insuficiente). Usa «Exportar».", 6000, True)
        return False


async def leer_demo():
    r = await pyfetch("data/demo.json", cache="no-store")
    E["demo"] = proyecto.validar_proyecto(json.loads(await r.string()))
    return copy.deepcopy(E["demo"])


async def cargar_demo():
    E["data"] = await leer_demo()
    E["eq"] = E["data"]["equipos"][0]["id"]
    E["cml"] = None


def base_demo(eq_id):
    """Equipo homónimo del caso demo (valores originales), o None si el equipo no viene del demo."""
    return next((e for e in (E["demo"] or {}).get("equipos", []) if e["id"] == eq_id), None)


# ------------------------------------------------------------------ rutas (URL ↔ estado)
def ruta_desde_estado():
    """#/inicio · #/planta · #/equipos/<id>[/cml/<id>][/diseno] · #/rbi · #/validacion · #/acerca"""
    t = E["tab"]
    if t == "rbi" and E["rbi_eq"]:
        return "#/rbi/" + window.encodeURIComponent(E["rbi_eq"])
    if t != "equipos" or not E["eq"]:
        return f"#/{t}"
    h = "#/equipos/" + window.encodeURIComponent(E["eq"])
    if E["cml"]:
        h += "/cml/" + window.encodeURIComponent(E["cml"])
    if E["sub"] == "diseno":
        h += "/diseno"
    return h


def estado_desde_ruta(h):
    partes = [window.decodeURIComponent(x) for x in str(h or "").lstrip("#").strip("/").split("/") if x]
    tab = partes[0] if partes and partes[0] in VISTAS else "inicio"
    E["tab"], E["editando"] = tab, None
    if tab == "rbi":
        ids = {e["id"] for e in E["data"]["equipos"]}
        E["rbi_eq"] = partes[1] if len(partes) > 1 and partes[1] in ids else E["rbi_eq"]
    if tab == "equipos":
        ids = {e["id"] for e in E["data"]["equipos"]}
        if len(partes) > 1 and partes[1] in ids:
            E["eq"] = partes[1]
        E["cml"] = partes[partes.index("cml") + 1] if "cml" in partes[2:-1] else None
        E["sub"] = "diseno" if "diseno" in partes[2:] else "resumen"


def on_popstate(evt):
    estado_desde_ruta(window.location.hash)
    render(empujar=False)


def ir_a_lo_critico():
    """Lleva al CML más crítico de toda la planta (acción principal de la portada)."""
    res = ui.evaluar_todo(E["data"])
    fl = ui.puntos_atencion(ui.visibles(E["data"]), res)
    if fl:
        E["tab"], E["eq"], E["cml"], E["sub"], E["editando"] = "equipos", fl[0]["_eq"], fl[0]["_cml"], "resumen", None


# ------------------------------------------------------------------ render
def render(empujar=True):
    try:
        data = E["data"]
        res = ui.evaluar_todo(data)
        if not eq_actual():
            E["eq"] = data["equipos"][0]["id"] if data["equipos"] else None
            E["cml"] = None
        eq = eq_actual()
        t = E["tab"]
        if E["cambio_ruta"] != ruta_desde_estado():  # el aviso «último cambio» vive solo en la vista donde se hizo
            E["cambio"], E["cambio_ruta"] = "", None
        sincronizar_fecha()
        # Al abrir un equipo se muestra de inmediato su CML más crítico (menos clics, foco en lo importante)
        if t == "equipos" and eq and eq["cmls"] and not any(c["id"] == E["cml"] for c in eq["cmls"]):
            E["cml"] = ui.cml_gobernante(eq, res[eq["id"]])[0]["id"] if not res[eq["id"]]["error"] else eq["cmls"][0]["id"]
        lateral = t == "equipos"
        document.getElementById("app").classList.toggle("con-lateral", lateral)
        document.getElementById("sidebar").innerHTML = (ui.sidebar(data, res, E["eq"], E["filtros"], E["buscar"], E["plegados"])
                                                         if lateral else "")
        if lateral:
            for inp in document.querySelectorAll('#sidebar input.vis[data-mixto="1"]'):
                inp.indeterminate = True
            if E["buscar"].strip():
                filtrar_lateral()
        vis = ui.visibles(data)  # sin los equipos ocultos desde la lista de Equipos
        for b in document.querySelectorAll("#tabs button"):
            activo = attr(b, "tab") == t
            b.classList.toggle("activo", activo)
            if activo:
                b.setAttribute("aria-current", "page")
            else:
                b.removeAttribute("aria-current")
        sin = '<div class="info">No hay equipos. Crea uno con «+ Nuevo equipo».</div>'
        if E["editando"] is not None:
            html = ui.form_equipo(None if E["editando"] == "nuevo" else eq, data, E["nuevo_fam"])
        elif t == "inicio":
            html = ui.vista_inicio(vis, res)
        elif t == "planta":
            html = ui.panel(vis, res, E["filtros"])
        elif t == "equipos":
            b = base_demo(eq["id"]) if eq else None
            html = ui.pagina_equipo(data, res, eq, E["cml"], E["sub"], base=(b or {}).get("diseno"), cambio=E["cambio"],
                                    nuevo_cml=E["nuevo_cml"]) if eq else sin
        elif t == "plan":
            html = ui.vista_plan(vis, res)
        elif t == "rbi":
            er = eq_rbi()
            b = base_demo(er["id"]) if er else None
            html = ui.vista_rbi(vis, res, er["id"] if er else None, base=(b or {}).get("rbi"), cambio=E["cambio"])
        elif t == "validacion":
            html = ui.vista_validacion(data, E["val_fam"])
        else:
            html = ui.vista_acerca()
        document.getElementById("contenido").innerHTML = ui.subindices(html)
        if E["nuevo_cml"] and t == "equipos":
            campo = document.querySelector('#form_cml input[name="componente"]')
            if hay(campo):
                campo.focus()
        ruta = ruta_desde_estado()
        if ruta != window.location.hash:
            if empujar and _ruta["actual"] is not None:
                window.history.pushState(None, "", ruta)
            else:
                window.history.replaceState(None, "", ruta)
        vista = ruta.split("/cml/")[0].split("/diseno")[0]
        if _ruta["actual"] is not None and vista != _ruta["actual"]:
            window.scrollTo(0, 0)
        _ruta["actual"] = vista
    except Exception as e:  # noqa: BLE001 — límite de error: nunca dejar la pantalla en blanco
        window.console.error(traceback.format_exc())
        document.getElementById("contenido").innerHTML = (
            f'<div class="error">✕ Error al mostrar la vista: {ui.esc(e)}. '
            'Puedes restablecer el caso demostrativo desde la barra superior.</div>')


def cambio():
    """Aplica un cambio: se ve al instante y queda pendiente hasta presionar «Guardar» (o Ctrl + S)."""
    E["sucio"] = True
    estado_guardado()
    render()


def guardar_ahora():
    if guardar_local(True):
        render()


def sincronizar_fecha():
    """Muestra en la barra superior la fecha de evaluación vigente del proyecto."""
    inp = document.getElementById("fecha-eval")
    if hay(inp):
        f = E["data"].get("fecha_evaluacion") or ""
        inp.value = f or date.today().isoformat()
        inp.max = "2100-12-31"
        caja = document.getElementById("caja-fecha")
        caja.classList.toggle("fija", bool(f) and f != date.today().isoformat())
        caja.title = ("Fecha de evaluación fija del proyecto: los cálculos se hacen «al día» de esta fecha. Bórrala para usar la de hoy."
                      if f else "Se evalúa a la fecha de hoy. Elige otra fecha para ver el estado de la planta en ese día.")


def anotar_cambio(txt):
    E["cambio"], E["cambio_ruta"] = txt, ruta_desde_estado()


# ------------------------------------------------------------------ antes → después (U2)
def foto_equipo(eq):
    """Estado del equipo para comparar antes y después de un cambio de diseño."""
    r = ui.evaluar_todo(E["data"])[eq["id"]]
    if r["error"] or not eq["cmls"]:
        return {"error": r["error"]}
    c, _ = ui.cml_gobernante(eq, r)
    x = r["cmls"][c["id"]]
    return {"cml": c["id"], "t_min": x["t_min"], "cond": x["condicion"], "rl": x["rl"], "proxima": ui.prox_txt(x), "eq_cond": r["cond"]}


def foto_rbi(eq):
    r = ui.evaluar_todo(E["data"])[eq["id"]]
    if r["error"] or not eq.get("rbi") or not eq["cmls"]:
        return {}
    R = ui.calcular_rbi(eq, r)
    return {"Df": R["con"]["Df"], "R_A": R["r"]["R_A"], "R_E": R["r"]["R_E"], "nivel": R["r"]["nivel"], "moneda": R["r"]["moneda"]}


def flecha(a, b, fmt):
    return f"{fmt(a)} → <b>{fmt(b)}</b>" if a != b else f"{fmt(b)} (sin cambio)"


def texto_diseno(campo, va, vb, a, b):
    nombre = proyecto.RANGOS.get(campo, (0, 0, 0, campo))[3]
    partes = [f"{ui.esc(nombre)}: {flecha(va, vb, lambda v: ui.f(v, 3))}"]
    if "t_min" in a and "t_min" in b:
        partes.append(f"t mín ({ui.esc(b['cml'])}): {flecha(a['t_min'], b['t_min'], lambda v: ui.f(v, 2, 'mm'))}")
        if a["cml"] != b["cml"]:
            partes.append(f"CML gobernante: {ui.esc(a['cml'])} → <b>{ui.esc(b['cml'])}</b>")
        if a["cond"] != b["cond"] or a["cml"] != b["cml"]:
            partes.append(f"condición: {ui.CONDICION[a['cond']]} → <b>{ui.CONDICION[b['cond']]}</b>")
        if a["proxima"] != b["proxima"]:
            partes.append(f"próxima inspección: {a['proxima']} → <b>{b['proxima']}</b>")
    return " · ".join(partes)


def texto_rbi(campo, va, vb, a, b):
    nombre = ETIQUETA_RBI.get(campo) or (f"Inspecciones {campo[5:]}" if campo.startswith("insp_") else campo)
    unidad = {"C_E": (b or {}).get("moneda", ""), "C_A_m2": ""}.get(campo, "")
    if campo == "C_E":
        fmt_v = lambda v: ui.f(v, 0, unidad)  # noqa: E731
    else:
        fmt_v = lambda v: ui.f(v, 2) if isinstance(v, float) else ui.esc(v)  # noqa: E731
    partes = [f"{ui.esc(nombre)}: {flecha(va, vb, fmt_v)}"]
    if a and b:
        if abs(a["Df"] - b["Df"]) > 1e-9:
            partes.append(f"D_f: {flecha(round(a['Df'], 1), round(b['Df'], 1), lambda v: ui.f(v, 1))}")
        partes.append(f"R_A: {flecha(a['R_A'], b['R_A'], lambda v: ui.f(v, 4, 'm²/año'))}")
        partes.append(f"R_E: {flecha(round(a['R_E']), round(b['R_E']), lambda v: ui.f(float(v), 0, b['moneda'] + '/año'))}")
        partes.append(f"prioridad: {flecha(a['nivel'], b['nivel'], str)}")
    return " · ".join(partes)


def set_diseno(eq, campo, valor):
    """Aplica un valor de diseño validado. Devuelve mensaje de error o None."""
    v, msg = proyecto.validar_campo_diseno(campo, valor)
    if msg:
        return msg
    a, va = foto_equipo(eq), eq["diseno"].get(campo)
    eq["diseno"][campo] = v
    if eq["familia"] == "tanque" and campo == "H_m":
        for c in eq["cmls"]:
            if c.get("diseno_local", {}).get("virola") == 1:
                c["diseno_local"]["H_m"] = v
    anotar_cambio(texto_diseno(campo, va, v, a, foto_equipo(eq)))
    return None


def set_rbi(eq, campo, valor):
    """Aplica una entrada del RBI validada. Devuelve mensaje de error o None."""
    cfg = eq["rbi"]
    a = foto_rbi(eq)
    if campo.startswith("insp_"):
        n = proyecto.numero(valor)
        if n is None or n < 0 or n > 20 or n != int(n):
            return "N° de inspecciones: entero entre 0 y 20."
        va, v = cfg["inspecciones"].get(campo[5:], 0), int(n)
        cfg["inspecciones"][campo[5:]] = v
    elif campo in ("pscore", "f_om", "C_A_m2", "C_E"):
        v = proyecto.numero(valor)
        lim = {"pscore": (0, 100), "f_om": (0.1, 10), "C_A_m2": (0, 1e7), "C_E": (0, 1e12)}[campo]
        if v is None or not lim[0] <= v <= lim[1]:
            return f"Valor fuera de rango ({lim[0]:g} – {lim[1]:g})."
        va = cfg.get(campo)
        cfg[campo] = v
    elif campo in ("cml", "confianza", "moneda", "base_valoracion"):
        v = proyecto.texto(valor, 200)
        if campo == "cml" and v not in {c["id"] for c in eq["cmls"]}:
            return "CML no válido."
        if campo == "confianza" and v not in ui.rbi.PRIOR:
            return "Confianza no válida."
        va = cfg.get(campo)
        cfg[campo] = v
    else:
        return "Campo desconocido."
    if campo != "base_valoracion":
        anotar_cambio(texto_rbi(campo, va, v, a, foto_rbi(eq)))
    return None


# ------------------------------------------------------------------ acciones de clic
def accion_click(el):
    act = attr(el, "act")
    eq = eq_actual()

    if act in ("tab", "sel_eq", "subvista", "cerrar_modal"):
        E["nuevo_cml"] = None
    if act == "cerrar_modal":
        render()
        return
    if act == "abrir_cml":
        if time.monotonic() - _drag.pop("recien", 0) < 0.6:  # el clic que sigue a soltar el ícono ya abrió la ventana
            return
        eq_a = eq_actual()
        if eq_a:
            E["nuevo_cml"] = ui.sugerencia_cml(eq_a)
            render()
        return
    if act == "tab":
        E["tab"], E["editando"] = attr(el, "tab"), None
        if E["tab"] == "equipos":
            E["sub"] = "resumen"
        render()
        return
    if act == "sel_eq":
        nuevo_eq = attr(el, "id")
        if nuevo_eq != E["eq"]:
            E["sub"] = "resumen"
        E["eq"], E["editando"], E["tab"] = nuevo_eq, None, "equipos"
        E["cml"] = attr(el, "cml") or None
        render()
        return
    if act == "subvista":
        E["sub"] = attr(el, "vista")
        render()
        return
    if act == "ir_area":
        area = attr(el, "area")
        if E["tab"] == "planta":  # en Planta el área funciona como interruptor y conserva los demás filtros
            f = dict(E["filtros"])
            if f.get("area") == area:
                f.pop("area")
            else:
                f["area"] = area
            E["filtros"] = f
        else:  # desde las migas de un equipo: ver solo esa área
            E["tab"], E["filtros"] = "planta", {"area": area}
        E["editando"] = None
        render()
        return
    if act == "quitar_filtro":
        E["filtros"] = {k: v for k, v in E["filtros"].items() if k != attr(el, "campo")}
        render()
        return
    if act == "ir_familia":
        E["tab"], E["filtros"], E["editando"] = "planta", {"familia": attr(el, "familia")}, None
        render()
        return
    if act == "ir_critico":
        ir_a_lo_critico()
        render()
        return
    if act == "sel_cml":
        E["cml"] = attr(el, "id")
        render()
        return
    if act == "sel_rbi_eq":
        E["rbi_eq"], E["tab"] = attr(el, "id"), "rbi"
        render()
        return
    if act == "val_fam":
        E["val_fam"] = attr(el, "fam") or ""
        render()
        return
    if act == "exportar_validacion":
        df = pd.DataFrame([{"Grupo": c["fam"], "Cálculo": c["nom"], "Entradas": c["ent"], "Referencia": c["ref"], "Esperado": c["esp"],
                            "Programa": c["prog"], "Unidad": c["u"], "Diferencia [%]": round(c["dif"], 5),
                            "Resultado": "OK" if c["ok"] else "Revisar"} for c in ui.resultados_validacion()])
        descargar("\ufeff" + df.to_csv(index=False, sep=";", decimal=","), "validacion_calculos.csv", "text/csv")
        toast(f"Validación exportada ({len(df)} casos).")
        return
    if act == "imprimir":
        imprimir()
        return
    if act == "exportar_plan":
        exportar_plan()
        return
    if act == "guardar":
        if E["sucio"]:
            guardar_ahora()
        else:
            toast("No hay cambios pendientes: todo está guardado.")
        return
    if act == "exportar":
        asyncio.ensure_future(exportar())
        return
    if act == "exportar_csv":
        filas = ui.filas_panel(ui.visibles(E["data"]), ui.evaluar_todo(E["data"]), E["filtros"])
        if not filas:
            toast("No hay filas para exportar con los filtros actuales.")
            return
        df = pd.DataFrame(filas)
        df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
        descargar("﻿" + df.to_csv(index=False, sep=";", decimal=","), f"resumen_cml_{date.today()}.csv", "text/csv")
        toast(f"CSV exportado ({len(df)} filas).")
        return
    if act == "restablecer":
        if window.confirm("¿Restablecer el caso demostrativo? Se perderán los cambios no exportados."):
            asyncio.ensure_future(restablecer())
        return
    if act == "plegar":
        clave = attr(el, "clave")
        E["plegados"] ^= {clave}
        render()
        return
    if act == "plegar_todo":
        if E["plegados"]:
            E["plegados"] = set()
        else:
            E["plegados"] = {f'a|{e["ubicacion"]["planta"]}|{e["ubicacion"]["area"]}' for e in E["data"]["equipos"]}
        render()
        return
    if act == "mostrar_todos":
        E["data"]["ocultos"] = []
        toast("Todos los equipos vuelven a mostrarse.")
        cambio()
        return
    if act == "nuevo_fam":
        E["nuevo_fam"] = attr(el, "familia")
        render()
        return
    if act == "nuevo_eq":
        E["editando"], E["tab"] = "nuevo", "equipos"
        render()
        return
    if act == "editar_eq":
        E["editando"] = "editar"
        render()
        return
    if act == "cancelar_eq":
        E["editando"] = None
        render()
        return
    if act == "limpiar_filtros":
        E["filtros"] = {}
        render()
        return

    # --- acciones que modifican datos (se guardan) ---
    if act == "add_med":
        if not agregar_medicion(eq):
            return
    elif act == "del_med":
        c = cml_actual(eq)
        if not window.confirm("¿Eliminar esta medición?"):
            return
        c["mediciones"].pop(int(attr(el, "i")))
        toast("Medición eliminada.")
    elif act == "add_cml":
        if not agregar_cml(eq):
            return
    elif act == "mover_cml":
        d = leer_form("form_xy")
        c = cml_actual(eq)
        x, y = proyecto.numero(d.get("x")), proyecto.numero(d.get("y"))
        if x is None or y is None or not (0 <= x <= 100 and 0 <= y <= 100):
            toast("Las coordenadas deben estar entre 0 y 100 %.", error=True)
            return
        c["x"], c["y"] = x, y
        toast(f"Marcador de {c['id']} movido a ({x:g}; {y:g}) %.")
    elif act == "borrar_cml":
        if not window.confirm(f"¿Eliminar {E['cml']} y todo su historial?"):
            return
        eq["cmls"] = [c for c in eq["cmls"] if c["id"] != E["cml"]]
        if eq.get("rbi") and eq["rbi"]["cml"] == E["cml"]:
            eq["rbi"]["cml"] = eq["cmls"][0]["id"] if eq["cmls"] else ""
        E["cml"] = None
    elif act == "guardar_eq":
        if not guardar_equipo(attr(el, "nuevo") == "1"):
            return
    elif act == "borrar_eq":
        if not window.confirm(f"¿Eliminar el equipo {eq['tag']} con todos sus CML y mediciones?"):
            return
        E["data"]["equipos"] = [e for e in E["data"]["equipos"] if e["id"] != eq["id"]]
        E["eq"], E["cml"] = None, None
        toast("Equipo eliminado.")
    elif act == "del_adj":
        eq["adjuntos"].pop(int(attr(el, "i")))
    elif act == "revertir":
        if not revertir(attr(el, "tipo"), attr(el, "campo")):
            return
    elif act == "crear_rbi":
        er = eq_rbi()
        if not er or er.get("rbi") or not er["cmls"]:
            toast("Este equipo necesita al menos un CML para evaluar el riesgo.", error=True)
            return
        r = ui.evaluar_todo(E["data"])[er["id"]]
        cfg = copy.deepcopy(ui.RBI_BASE)
        cfg["cml"] = ui.cml_gobernante(er, r)[0]["id"] if not r["error"] else er["cmls"][0]["id"]
        er["rbi"] = cfg
        toast(f"Evaluación RBI creada para {er['tag']} con valores por defecto: ajústalos al escenario real.", 6000)
    else:
        return
    cambio()


def revertir(tipo, campo):
    """Vuelve un campo al valor del caso demo (U3)."""
    if tipo == "diseno":
        eq = eq_actual()
        b = (base_demo(eq["id"]) or {}).get("diseno", {})
        if campo not in b:
            return False
        msg = set_diseno(eq, campo, b[campo])
    else:
        eq = eq_rbi()
        b = (base_demo(eq["id"]) or {}).get("rbi") or {}
        val = (b.get("inspecciones") or {}).get(campo[5:]) if campo.startswith("insp_") else b.get(campo)
        if val is None:
            return False
        msg = set_rbi(eq, campo, val)
    if msg:
        toast(msg, error=True)
        return False
    return True


def imprimir():
    """Abre todos los plegables del contenido y lanza el diálogo de impresión (guardar como PDF)."""
    for d in document.querySelectorAll("#contenido details"):
        d.setAttribute("open", "")
    window.print()


def exportar_plan():
    plan = ui.filas_plan(ui.visibles(E["data"]), ui.evaluar_todo(E["data"]))
    if not plan:
        toast("No hay CML en el plan.")
        return
    filas = [{"Grupo": g[1], "Fecha": fl["Próxima inspección"], "Equipo": fl["Equipo"], "CML": fl["CML"],
              "Componente": fl.get("Componente", ""), "Tarea": "Medición de espesores (UT)", "Intervalo [años]": fl["Intervalo [años]"],
              "Criterio": fl["Criterio"], "Referencia": fl["Referencia"], "Condición": ui.CONDICION.get(fl["Condición"], fl["Condición"])}
             for g, fl in plan]
    df = pd.DataFrame(filas)
    descargar("\ufeff" + df.to_csv(index=False, sep=";", decimal=","), f"plan_inspeccion_{ui.hoy_eval()}.csv", "text/csv")
    toast(f"Plan exportado ({len(df)} CML).")


def agregar_medicion(eq):
    c = cml_actual(eq)
    d = leer_form("form_med")
    t = proyecto.numero(d.get("espesor"))
    f = proyecto.fecha_valida(d.get("fecha"))
    if f is None:
        toast("Ingresa una fecha válida.", error=True)
        return False
    if t is None or t <= 0:
        toast("Ingresa un espesor mayor que 0.", error=True)
        return False
    if date.fromisoformat(f) > date.today():
        toast("La fecha de la medición no puede ser futura.", error=True)
        return False
    t_mm = t * ui.IN if d.get("unidad") == "in" else t
    if t_mm > 300:
        toast("Espesor fuera de rango (> 300 mm). Revisa la unidad.", error=True)
        return False
    if any(m["fecha"] == f for m in c["mediciones"]) and not window.confirm(
            "Ya existe una medición en esa fecha para este CML. ¿Agregarla igualmente?"):
        return False
    nominal = c.get("t_nom_mm") or eq["t_nom_mm"]
    if nominal and t_mm > nominal * 1.15 and not window.confirm(
            f"El espesor ({t_mm:.2f} mm) supera en más de 15 % el nominal ({nominal:.2f} mm). ¿Es correcto?"):
        return False
    m = {"fecha": f, "espesor_mm": round(t_mm, 4), "unidad": d.get("unidad", "mm"),
         "tecnica": proyecto.texto(d.get("tecnica"), 40), "observaciones": proyecto.texto(d.get("observaciones"), 300)}
    if d.get("evento") in proyecto.EVENTOS:
        m["evento"] = d["evento"]
    c["mediciones"].append(m)
    toast(f"Medición agregada a {c['id']}: {t_mm:.2f} mm. Cálculos actualizados.")
    return True


def agregar_cml(eq):
    d = leer_form("form_cml")
    cid = proyecto.texto(d.get("id"), 40)
    if not cid:
        toast("El ID del CML es obligatorio.", error=True)
        return False
    if any(c["id"] == cid for c in eq["cmls"]):
        toast(f"Ya existe el CML {cid} en este equipo.", error=True)
        return False
    x, y = proyecto.numero(d.get("x")), proyecto.numero(d.get("y"))
    if x is None or y is None or not (0 <= x <= 100 and 0 <= y <= 100):
        toast("Las coordenadas deben estar entre 0 y 100 %.", error=True)
        return False
    tn = proyecto.numero(d.get("t_nom_mm"))
    c = {"id": cid, "componente": proyecto.texto(d.get("componente")), "ubicacion": proyecto.texto(d.get("ubicacion")),
         "x": x, "y": y, "t_nom_mm": tn if tn and 0 < tn <= 300 else eq["t_nom_mm"], "mediciones": []}
    if eq["familia"] == "tanque":
        vir, msg1 = proyecto.validar_campo_diseno("virola", d.get("virola") or 1)
        h, msg2 = proyecto.validar_campo_diseno("H_m", d.get("H_m") or eq["diseno"]["H_m"])
        if msg1 or msg2:
            toast(msg1 or msg2, error=True)
            return False
        c["diseno_local"] = {"virola": int(vir), "H_m": h}
    eq["cmls"].append(c)
    E["cml"], E["nuevo_cml"] = cid, None
    toast(f"CML {cid} agregado. Registra su primera medición.")
    return True


def guardar_equipo(nuevo):
    d = leer_form("form_eq")
    tag = proyecto.texto(d.get("tag"), 60)
    if not tag:
        toast("El TAG es obligatorio.", error=True)
        return False
    fam = d.get("familia") if nuevo else eq_actual()["familia"]
    if ui.MATERIALES[d["material"]]["familia"] != fam:
        toast("El material seleccionado no corresponde a la familia del equipo.", error=True)
        return False
    t_nom = proyecto.numero(d.get("t_nom_mm"))
    if t_nom is None or not 0 < t_nom <= 300:
        toast("Ingresa un espesor nominal válido (0–300 mm).", error=True)
        return False
    if not proyecto.fecha_valida(d.get("fecha_servicio")):
        toast("Ingresa la fecha de puesta en servicio.", error=True)
        return False
    diseno = {}
    for campo in ui.CAMPOS_FORM[fam]:
        if d.get(f"d_{campo}") not in (None, ""):
            v, msg = proyecto.validar_campo_diseno(campo, d.get(f"d_{campo}"))
            if msg:
                toast(msg, error=True)
                return False
            diseno[campo] = v
    if nuevo:
        if any(e["id"] == tag for e in E["data"]["equipos"]):
            toast("Ya existe un equipo con ese TAG.", error=True)
            return False
        eq = {"id": tag, "familia": fam, "diseno": copy.deepcopy(ui.DISENO_BASE[fam]), "cmls": [], "imagen": "",
              "adjuntos": []}
        E["data"]["equipos"].append(eq)
    else:
        eq = eq_actual()
    eq["diseno"].update(diseno)
    clase = proyecto.numero(d.get("clase"))
    eq.update(tag=tag, descripcion=proyecto.texto(d.get("descripcion"), 200), servicio=proyecto.texto(d.get("servicio")),
              fluido=proyecto.texto(d.get("fluido")), circuito=proyecto.texto(d.get("circuito"), 60),
              clase=int(clase) if clase in (1, 2, 3, 4) else (2 if fam == "tuberia" else None), material=d["material"],
              codigo_diseno=proyecto.texto(d.get("codigo_diseno"), 80), codigo_servicio=proyecto.texto(d.get("codigo_servicio"), 80),
              t_nom_mm=t_nom, fecha_servicio=proyecto.fecha_valida(d.get("fecha_servicio")))
    eq["ubicacion"] = {"planta": proyecto.texto(d.get("planta"), 80) or "Planta",
                       "area": proyecto.texto(d.get("area"), 80) or "Sin área",
                       "sistema": proyecto.texto(d.get("sistema"), 80) or "Sin sistema"}
    eq["operacion"] = {"P_MPa": proyecto.numero(d.get("P_op")) or 0.0, "T_C": proyecto.numero(d.get("T_op")) or 20.0}
    E["eq"], E["cml"], E["editando"] = eq["id"], None, None
    E["tab"], E["sub"] = "equipos", ("diseno" if nuevo else "resumen")
    toast("Equipo guardado." + (" Completa ahora sus datos de diseño." if nuevo else ""))
    return True


# ------------------------------------------------------------------ acciones de cambio (inputs)
def accion_change(el):
    act = attr(el, "act")
    campo = attr(el, "campo")
    eq = eq_actual()
    if act == "filtro":
        E["filtros"][campo] = el.value or None
        render()
        return
    if act == "preset_nps" and el.value:
        od, t = el.value.split("|")
        document.querySelector('#form_eq input[name="d_D_ext_mm"]').value = od
        document.querySelector('#form_eq input[name="t_nom_mm"]').value = t
        return
    if act == "preset_g" and el.value:
        document.querySelector('#form_eq input[name="d_G"]').value = el.value
        return
    if act == "form_familia":
        mat = document.querySelector('#form_eq select[name="material"]')
        mat.innerHTML = ui.opciones_material(el.value)
        return
    if act == "diseno":
        msg = set_diseno(eq, campo, el.value)
        if msg:
            toast(msg, error=True)
            render()
            return
    elif act == "rbi":
        er = eq_rbi()
        if not er or not er.get("rbi"):
            return
        msg = set_rbi(er, campo, el.value)
        if msg:
            toast(msg, error=True)
            render()
            return
    elif act == "visible":
        ids = set(json.loads(attr(el, "ids") or "[]"))
        oc = set(E["data"].get("ocultos") or [])
        oc = (oc - ids) if el.checked else (oc | ids)
        E["data"]["ocultos"] = sorted(oc & {e["id"] for e in E["data"]["equipos"]})
        n = len(E["data"]["ocultos"])
        toast(f"{n} equipo(s) oculto(s) en la app." if n else "Todos los equipos visibles.")
    elif act == "sel_rbi":
        E["rbi_eq"] = el.value
        render()
        return
    elif act == "fecha_eval":
        f = proyecto.fecha_valida(el.value) or ""
        if f == date.today().isoformat():
            f = ""
        E["data"]["fecha_evaluacion"] = f
        if f:  # efecto de la fecha elegida respecto de evaluar hoy
            hoy = {(fl["_eq"], fl["_cml"]): fl["Condición"] for fl in ui.filas_panel(E["data"], ui.evaluar_todo(E["data"], date.today()), {})}
            otra = {(fl["_eq"], fl["_cml"]): fl["Condición"] for fl in ui.filas_panel(E["data"], ui.evaluar_todo(E["data"]), {})}
            n = sum(1 for k, v in otra.items() if hoy.get(k) != v)
            toast(f"Evaluación al {ui.fecha_cl(f)}: " + (f"{n} CML con condición distinta a la de hoy." if n
                                                     else "misma condición que hoy en todos los CML."), 5000)
        else:
            toast(f"Evaluación a la fecha de hoy ({date.today():%d-%m-%Y}).")
    elif act in ("importar", "subir_img", "subir_pdf"):
        cerrar_menus()
        asyncio.ensure_future(cargar_archivo(el, act))
        return
    else:
        return
    cambio()


def eq_rbi():
    """Recipiente que se evalúa en Riesgo (RBI): el elegido; si no, el primero con evaluación; si no, el primer recipiente."""
    recs = ui.recipientes(ui.visibles(E["data"]))
    return (next((e for e in recs if e["id"] == E["rbi_eq"]), None) or next((e for e in recs if e.get("rbi")), None)
            or (recs[0] if recs else None))


# ------------------------------------------------------------------ archivos
async def cargar_archivo(el, act):
    archivo = el.files.item(0) if el.files.length else None
    el.value = ""
    if archivo is None:
        return
    try:
        if archivo.size > LIMITES[act]:
            raise ValueError(f"archivo demasiado grande ({archivo.size / 1e6:.1f} MB; máx. {LIMITES[act] / 1e6:.1f} MB)")
        datos = (await archivo.arrayBuffer()).to_py().tobytes()
        if act == "importar":
            data = proyecto.validar_proyecto(json.loads(datos.decode("utf-8-sig")))
            E["data"], E["cml"], E["editando"], E["filtros"], E["rbi_eq"] = data, None, None, {}, None
            E["eq"] = data["equipos"][0]["id"] if data["equipos"] else None
            guardar_local()
            toast(f"Proyecto importado y guardado: {archivo.name} ({len(data['equipos'])} equipos).")
        else:
            permitidos = ("image/png", "image/jpeg") if act == "subir_img" else ("application/pdf",)
            mime = archivo.type
            if mime not in permitidos or not datos.startswith(FIRMAS[mime]):
                raise ValueError("tipo de archivo no permitido" + (" (solo PNG o JPG)" if act == "subir_img" else " (solo PDF)"))
            url = f"data:{mime};base64,{base64.b64encode(datos).decode()}"
            eq = eq_actual()
            if act == "subir_img":
                eq["imagen"] = url
                toast(f"Esquema actualizado: {archivo.name}")
            else:
                if len(eq["adjuntos"]) >= proyecto.MAX_ADJ:
                    raise ValueError(f"máximo {proyecto.MAX_ADJ} PDF por equipo")
                eq["adjuntos"].append({"nombre": proyecto.texto(archivo.name, 120), "url": url})
                toast(f"PDF adjuntado: {archivo.name}")
        cambio()
    except proyecto.ErrorProyecto as e:
        toast(f"Archivo rechazado: {e.errores[0]}" + (f" (+{len(e.errores) - 1} problemas más)" if len(e.errores) > 1 else ""), 8000, True)
    except Exception as e:  # noqa: BLE001
        toast(f"No se pudo leer el archivo: {e}", 6000, True)


async def exportar():
    try:
        data = copy.deepcopy(E["data"])
        for eq in data["equipos"]:
            img = eq.get("imagen") or ""
            if img and not img.startswith("data:"):
                r = await pyfetch(img)
                mime = "image/jpeg" if img.lower().endswith((".jpg", ".jpeg")) else "image/png"
                eq["imagen"] = f"data:{mime};base64,{base64.b64encode(await r.bytes()).decode()}"
        data["exportado"] = datetime.now().isoformat(timespec="seconds")
        descargar(json.dumps(data, ensure_ascii=False, indent=1), f"proyecto_giee_{date.today()}.json", "application/json")
        toast("Proyecto exportado: equipos, CML, mediciones, esquemas y adjuntos.")
    except Exception as e:  # noqa: BLE001
        toast(f"No se pudo exportar: {e}", 6000, True)


async def restablecer():
    await cargar_demo()
    E["tab"], E["filtros"], E["editando"], E["rbi_eq"] = "inicio", {}, None, None
    guardar_local()
    render()
    toast("Caso demostrativo restablecido.")


# ------------------------------------------------------------------ eventos (delegación)
def _seguro(fn, el):
    try:
        fn(el)
    except Exception as e:  # noqa: BLE001
        window.console.error(traceback.format_exc())
        toast(f"Error inesperado: {e}", 6000, True)


def hay(x):
    """True si un resultado del DOM existe (en Pyodide, null puede llegar como None o como JsNull)."""
    return x is not None and type(x).__name__ != "JsNull"


MENUS = "details.menu, details.fam-menu"


def cerrar_menus(excepto=None):
    for m in document.querySelectorAll("details.menu[open], details.fam-menu[open]"):
        if not (hay(excepto) and excepto.isSameNode(m)):
            m.removeAttribute("open")


def on_click(evt):
    menu = evt.target.closest(MENUS)
    en_panel = hay(evt.target.closest(".menu-panel, .fam-menu-panel"))
    # clic fuera de un menú o en una opción → cerrar (salvo "Importar", que se cierra al elegir el archivo);
    # al abrir un menú se cierran los demás
    if not hay(menu) or (en_panel and not hay(evt.target.closest("label"))):
        cerrar_menus()
    else:
        cerrar_menus(excepto=menu)
    el = evt.target.closest("[data-act]")
    if hay(el) and el.tagName not in ("SELECT", "INPUT", "TEXTAREA"):
        evt.preventDefault()
        _seguro(accion_click, el)


def on_change(evt):
    if attr(evt.target, "act"):
        _seguro(accion_change, evt.target)


def filtrar_lateral():
    """Muestra solo los equipos cuyo TAG o descripción contiene el texto buscado (y oculta ramas vacías)."""
    q = E["buscar"].strip().lower()
    if not q:
        render()  # restaura el árbol con sus ramas plegadas
        return
    for el in document.querySelectorAll("#sidebar .arbol ul, #sidebar .eq-lista"):
        el.hidden = False  # al buscar se despliegan todas las ramas
    visibles = 0
    for el in document.querySelectorAll("#sidebar .eq-item"):
        ok = q in (attr(el, "buscar") or "")
        el.parentElement.hidden = not ok
        el.hidden = not ok
        visibles += ok
    for li in document.querySelectorAll("#sidebar .arbol li"):
        li.hidden = li.querySelectorAll(".eq-item:not([hidden])").length == 0
    aviso = document.querySelector("#sidebar .sin-res")
    if hay(aviso):
        aviso.hidden = visibles > 0


# ------------------------------------------------------------------ arrastrar el ícono de CML al esquema
_drag = {}


def _pos_esquema(evt):
    """(x %, y %) del puntero sobre la imagen del esquema, o None si está fuera."""
    img = document.querySelector("#contenido .esquema img")
    if not hay(img):
        return None
    r = img.getBoundingClientRect()
    if r.width == 0 or not (r.left <= evt.clientX <= r.right and r.top <= evt.clientY <= r.bottom):
        return None
    return (evt.clientX - r.left) / r.width * 100, (evt.clientY - r.top) / r.height * 100


def _mover(evt):
    g = _drag.get("fantasma")
    if not g:
        return
    g.style.left, g.style.top = f"{evt.clientX}px", f"{evt.clientY}px"
    _drag["dist"] = max(_drag.get("dist", 0), abs(evt.clientX - _drag["x0"]) + abs(evt.clientY - _drag["y0"]))
    luz = document.querySelector("#contenido .zona-luz")
    esq = document.querySelector("#contenido .esquema")
    pos = _pos_esquema(evt)
    if hay(esq):
        esq.classList.toggle("sobre", pos is not None)
    if not hay(luz):
        return
    z = ui.zona_en(eq_actual(), *pos) if pos else None
    if z:
        x0, y0, x1, y1 = z["r"]
        luz.style.left, luz.style.top = f"{x0}%", f"{y0}%"
        luz.style.width, luz.style.height = f"{x1 - x0}%", f"{y1 - y0}%"
        luz.querySelector("span").innerText = z["nom"]
        luz.hidden = False
    else:
        luz.hidden = True


def _soltar(evt):
    for tipo in ("pointermove", "pointerup", "pointercancel"):
        p = _drag.get(tipo)
        if p:
            document.removeEventListener(tipo, p)
    g = _drag.pop("fantasma", None)
    if g:
        g.remove()
    pos = _pos_esquema(evt) if evt.type == "pointerup" else None
    movio = _drag.get("dist", 0) > 6
    eq = eq_actual()
    if eq and (pos or not movio) and evt.type == "pointerup":
        E["nuevo_cml"] = ui.sugerencia_cml(eq, *pos) if pos else ui.sugerencia_cml(eq)
        _drag["recien"] = time.monotonic()
        render()
    else:
        luz = document.querySelector("#contenido .zona-luz")
        if hay(luz):
            luz.hidden = True
        esq = document.querySelector("#contenido .esquema")
        if hay(esq):
            esq.classList.remove("sobre")
        if movio:
            toast("Suelta el ícono sobre el esquema para ubicar el CML.")


def on_pointerdown(evt):
    t = evt.target.closest('[data-arrastre="cml"]')
    if not hay(t) or evt.button != 0:
        return
    evt.preventDefault()
    g = document.createElement("div")
    g.className = "cml-fantasma"
    g.innerText = "CML"
    g.style.left, g.style.top = f"{evt.clientX}px", f"{evt.clientY}px"
    document.body.appendChild(g)
    _drag.clear()
    _drag.update(fantasma=g, x0=evt.clientX, y0=evt.clientY, dist=0)
    for tipo, fn in (("pointermove", _mover), ("pointerup", _soltar), ("pointercancel", _soltar)):
        p = create_proxy(fn)
        _proxies.append(p)
        _drag[tipo] = p
        document.addEventListener(tipo, p)


def on_input(evt):
    if attr(evt.target, "act") == "buscar_eq":
        E["buscar"] = str(evt.target.value or "")[:60]
        filtrar_lateral()


def on_submit(evt):
    evt.preventDefault()  # el botón del formulario ya recibe un clic (también con Enter)


def on_keydown(evt):
    if (evt.ctrlKey or evt.metaKey) and str(evt.key).lower() == "s":
        evt.preventDefault()
        if E["sucio"]:
            guardar_ahora()
        else:
            toast("No hay cambios pendientes: todo está guardado.")
        return
    if evt.key == "Escape":
        cerrar_menus()
        if E["nuevo_cml"]:
            E["nuevo_cml"] = None
            render()
        return
    if evt.key in ("Enter", " ") and evt.target.getAttribute("role") == "button":
        evt.preventDefault()
        _seguro(accion_click, evt.target)


def on_beforeunload(evt):
    if E["sucio"]:  # el navegador pide confirmar antes de salir con cambios sin guardar
        evt.preventDefault()
        evt.returnValue = ""


def registrar(tipo, fn):
    p = create_proxy(fn)
    _proxies.append(p)
    document.addEventListener(tipo, p)


# ------------------------------------------------------------------ inicio
async def iniciar():
    guardado = window.localStorage.getItem(CLAVE)
    recuperado = False
    if guardado:
        try:
            E["data"] = proyecto.validar_proyecto(json.loads(guardado))
            E["eq"] = E["data"]["equipos"][0]["id"] if E["data"]["equipos"] else None
            recuperado = True
        except Exception:  # noqa: BLE001 — datos corruptos o de otra versión
            window.localStorage.removeItem(CLAVE)
    if not recuperado:
        await cargar_demo()
    else:
        try:
            await leer_demo()
        except Exception:  # noqa: BLE001 — sin demo de referencia solo se pierde la marca de campos editados
            E["demo"] = None
    for tipo, fn in (("click", on_click), ("change", on_change), ("submit", on_submit), ("keydown", on_keydown), ("input", on_input),
                     ("pointerdown", on_pointerdown)):
        registrar(tipo, fn)
    p = create_proxy(on_popstate)
    _proxies.append(p)
    window.addEventListener("popstate", p)
    p = create_proxy(on_beforeunload)
    _proxies.append(p)
    window.addEventListener("beforeunload", p)
    estado_desde_ruta(window.location.hash)
    if hasattr(window, "cargaLista"):  # completa la pantalla de carga y la desvanece (ver index.html)
        window.cargaLista()
    else:
        document.getElementById("cargando").hidden = True
    document.getElementById("app").hidden = False
    render()
    document.getElementById("estado-guardado").innerText = "Recuperado del navegador" if recuperado else "Caso demo"
    estado_guardado()
    if guardado and not recuperado:
        toast("Los datos guardados estaban dañados: se cargó el caso demostrativo.", 6000, True)


await iniciar()
