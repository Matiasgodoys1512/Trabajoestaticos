# Gestión de Integridad de Equipos Estáticos

Prototipo académico (MAN040-B, Ingeniería en Mantenimiento Industrial) para gestionar antecedentes técnicos de equipos estáticos, registrar mediciones de espesor por CML/TML, evaluar corrosión y vida remanente, proponer la próxima inspección y estimar el riesgo por adelgazamiento (RBI).

**Aplicación publicada:** https://matiasgodoys1512.github.io/Trabajoestaticos/
(la primera carga tarda 20–40 s porque descarga Python al navegador; luego queda en caché)

| Familia | Diseño / construcción | En servicio | Geometría | Material |
|---|---|---|---|---|
| Tuberías de proceso | ASME B31.3-2018 | API 570 | Tramo recto | A106 Gr. B, A53 Gr. B |
| Recipientes a presión | ASME VIII-1 2019 + II-D 2019 | API 510 | Envolvente cilíndrica | SA-516 Gr. 70 |
| Tanques atmosféricos | API 650 12ª ed. (2013) | API 653 | Virolas del manto | A283 Gr. C, A36 |
| RBI | API RP 580 (2016) / RP 581 (2016 + Add. 2 2020) | — | Adelgazamiento generalizado | Recipiente V-201 |

## Funciones

- Portada con el estado del día (puntos que requieren acción), las familias evaluadas y cómo se usa.
- Navegación con URL propia por vista (botón Atrás, recarga y enlaces directos a un equipo/CML).
- Estructura planta › área › sistema › equipo, con filtros por ubicación, familia y condición.
- Ficha técnica, esquema con marcadores CML (coordenadas en % ingresadas por formulario) y adjuntos PDF.
- Espesores **nominal, requerido por cálculo, de diseño, mínimo en servicio, de alerta y medido**, con ecuación, entradas, unidades y referencia.
- Velocidad de corrosión de largo y corto plazo, vida remanente y gráfico espesor vs. tiempo con proyección.
- Próxima inspección según API 510 / 570 / 653 y condición: normal, alerta, bajo el mínimo, inspección vencida, información insuficiente.
- Detección de datos insuficientes, fechas inconsistentes, CR nula o negativa y reemplazos/reparaciones/cambios de punto.
- Módulo RBI: factor de daño (API 581 Parte 2 §4), frecuencia de falla, riesgo de área (m²/año) y económico (moneda/año), matrices y prioridad.
- Guardado automático en el navegador y exportación/importación del proyecto completo (JSON con esquemas y adjuntos).
- Sección **Validación**: comparación de cada familia y del RBI con cálculos independientes (incluye el ejercicio de la clase 05).

## Guion de la demostración (sección 8 del enunciado)

1. **Inicio** → qué hace la app, qué requiere atención y las tres familias; **Planta** → plano interactivo por áreas con avisos y todos los CML ordenados por severidad. **Plan** → próximas mediciones por mes (exportable a CSV). Fecha de evaluación global en la barra superior.
2. **Inicio → tarjeta Recipiente** → V-201 se abre en su CML más crítico; las migas muestran la ubicación técnica; elegir CML-201-02 en el esquema.
3. **Nueva medición** → agregar un espesor: cambian CR, vida remanente, condición y próxima fecha.
4. **Diseño y espesores** → cambiar presión o temperatura: cambia el espesor requerido.
5. **Riesgo (RBI)** → cambiar C<sub>A</sub> o C<sub>E</sub>: cambia el riesgo y su categoría.
6. **Proyecto → Exportar**, **Restablecer caso demo**, **Importar**: se recupera el caso. Mostrar **Validación**.

## Arquitectura

Sitio estático (GitHub Pages) con HTML + CSS y **Python ejecutado en el navegador** con PyScript/Pyodide. No hay servidor.

```
index.html, css/          Interfaz
py/calc/                  Motor de cálculo (Python puro, sin dependencias)
  materiales.py           Catálogo y esfuerzos admisibles (interpolación)
  espesores.py            B31.3, UG-27, API 650, API 653, espesor de alerta
  corrosion.py            Serie comparable, CR largo/corto plazo, vida remanente
  inspeccion.py           Intervalos API 510/570/653 y condición del CML
  rbi.py                  DF adelgazamiento, POF, riesgo y matriz (API 581)
py/proyecto.py            Validación y saneamiento de datos importados
py/ui.py                  Generación de vistas (HTML) y gráficos (Matplotlib)
py/app.py                 Eventos, estado, persistencia e import/export
data/                     Caso demostrativo (ficticio) y esquemas
docs/fundamentos.md       Ecuaciones, valores, supuestos y referencias
tests/                    Pruebas unitarias (pytest)
tools/                    Generadores del caso demo y prueba E2E (Playwright)
```

## Verificación

```bash
python -m venv .venv
.venv/Scripts/python -m pip install pytest numpy pandas matplotlib playwright
.venv/Scripts/python -m pytest -q                  # pruebas del motor y del validador
.venv/Scripts/python -m playwright install chromium
.venv/Scripts/python tools/e2e.py                  # recorre la demo en un navegador real
.venv/Scripts/python -m http.server 8000           # ejecución local de respaldo
```

Las pruebas unitarias también corren automáticamente en GitHub Actions en cada push.

## Seguridad

- Todo archivo importado o dato recuperado del navegador se valida (tipos, rangos físicos, fechas, referencias) antes de usarse.
- Textos escapados antes de insertarse en la página; coordenadas y valores saneados.
- Adjuntos solo PNG/JPG/PDF, verificando tamaño, tipo y firma binaria; se rechazan URLs `javascript:` o externas.
- Dependencias de CDN con versión fija e integridad (SRI).

## Limitaciones

- Modelo académico: catálogo acotado (hasta 260 °C), solo tramos rectos, envolventes cilíndricas y manto de tanques.
- API 510/570/653 no estaban disponibles en texto completo: sus criterios se tomaron de los apuntes del curso y quedan marcados para verificación.
- RBI simplificado: un mecanismo, sin cladding, consecuencias ingresadas por el usuario.
- Datos del caso demostrativo ficticios.

## Uso de inteligencia artificial

Desarrollo apoyado por un asistente de IA en modo agente (programación, revisión de errores y preparación de datos). Las ecuaciones, valores admisibles y criterios provienen de las normas y apuntes indicados, y fueron verificados por el grupo con los casos de la pestaña Validación y las pruebas automáticas.
