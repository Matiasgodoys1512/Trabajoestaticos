# CLAUDE.md — Proyecto Final Equipos Estáticos (MAN040-B)

## Contexto
- App web académica de gestión de integridad (inspirada en UltraPIPE): equipos estáticos, CML/TML, mediciones de espesor, corrosión, vida remanente, próxima inspección y RBI simplificado.
- Enunciado completo: `Enunciado_Proyecto_Final_Equipos_Estaticos.md` (fuente de verdad de los requisitos).
- **Entrega: viernes 2026-11-27.** Presentación oral de 15 min + demo en vivo. Iteraciones rápidas.
- Usuario: estudiante de Ing. en Mantenimiento Industrial, no es informático. Domina la parte técnica; Claude lleva la programación y explica lo justo para defenderla.
- Repo remoto: `github.com/Matiasgodoys1512/Trabajoestaticos` → publicar en GitHub Pages.

## Stack (herramientas sugeridas por el profesor)
- Interfaz: **HTML + CSS**. Lógica: **Python vía PyScript/Pyodide** en el navegador (sin servidor). JS solo si PyScript no lo permite.
- Motor de cálculo `py/calc/`: Python puro (solo stdlib), sin DOM. UI en Python: `py/app.py`.
- Gráficos: Matplotlib (Pyodide). Persistencia: localStorage + exportar/importar JSON (imágenes en base64).
- Verificación local: `.venv/Scripts/python -m pytest -q`.
- Servidor local de prueba: `.venv/Scripts/python -m http.server 8000`.

## Reglas de seguridad del entorno
- Todo lo instalable va en `.venv/` (ignorado por git). No tocar el Python global, el PATH ni la config global de Git.
- Las normas (PDF/MD con copyright) **no se suben** al repo. Están en `C:/Users/matia/Downloads/Trabajo final estaticos` (solo lectura).
- Commits y push solo cuando el usuario lo pida. Sin líneas de coautoría de Claude.
- Versionado: tras cada push, tag anotado subiendo la versión menor (0.1.0 → 0.2.0 → …), sin prefijo "v".

## Referencias
- Carpeta de normas/clases: ver arriba. MD: API 650, RP 580, RP 581, B31.3, VIII-1. II-D solo en PDF (Tabla 1A, p. 82–84). PPTX de clases 01–06.
- **No hay API 510/570/653** → sus criterios están marcados ⚠️ en `docs/fundamentos.md`.
- Ecuaciones, valores y criterios: `docs/fundamentos.md` (mantenerlo actualizado).
- Validación con el ejercicio del profesor: ppt 05, lámina 15 (8" A53 B, 150 psig, 200 °F).

## Arquitectura
- `py/calc/` → materiales, espesores, corrosion, inspeccion, rbi (probados en `tests/`).
- `py/proyecto.py` → validación/saneamiento de todo dato externo (import, localStorage). Probado en `tests/test_proyecto.py`.
- `py/ui.py` → vistas HTML (todo texto con `esc()`), `py/app.py` → eventos (delegación, `attr()` para leer data-*), estado y archivos.
- `index.html`, `css/` → interfaz. `.nojekyll` es obligatorio (GitHub Pages ignora `__init__.py` sin él).
- E2E en navegador real: `.venv/Scripts/python tools/e2e.py` (Playwright + Chromium dentro de `.venv/ms-playwright`).
- `data/` → caso demostrativo (JSON) + esquemas PNG.
- Fecha de evaluación global: `data["fecha_evaluacion"]` (vacía = hoy). `ui.evaluar_todo` la fija en `ui._CTX`; usar `ui.hoy_eval()`, nunca `date.today()`, en cálculos de condición/RBI/plan.

## Alcance técnico
- Tubería: ASME B31.3 / API 570, tramo recto. Recipiente: VIII-1 UG-27 + II-D / API 510. Tanque: API 650 / API 653, virolas (1 pie).
- RBI: API RP 580/581, adelgazamiento generalizado, solo para el recipiente, como modelo académico simplificado.
- Cada cálculo en la UI muestra: entradas, unidades, ecuación, referencia y resultado.
- Estados: normal, alerta, bajo el mínimo, inspección vencida, información insuficiente.

## Estilo de comunicación
- Respuestas **breves y directas**. Nada de muros de texto. Ir ajustando sobre la marcha.
- Español con tildes correctas.
