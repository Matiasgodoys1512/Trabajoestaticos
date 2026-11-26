# Guía de uso y comparación con el enunciado

App: https://matiasgodoys1512.github.io/Trabajoestaticos/ (primera carga 20–40 s).

## 1. Cómo se usa (lo básico)

**Navegación (barra superior).** Seis secciones, siempre visibles. La URL cambia con cada vista: el botón Atrás del navegador funciona, al recargar se mantiene la vista y un enlace (por ejemplo `#/equipos/V-201/cml/CML-201-03`) abre directo ese punto.

| Sección | Para qué sirve | Qué se puede hacer |
|---|---|---|
| **Inicio** | Portada: qué es la app, qué requiere atención hoy y cómo se usa | «Ver estado de la planta», «Ir al punto más crítico», abrir cualquiera de las 3 familias |
| **Planta** | **Plano de planta** (áreas › sistemas › equipos, con boceto por familia y aviso ⚠ parpadeante en equipos con CML en alerta, vencidos o bajo el mínimo) y tabla de todos los CML, del más grave al menos grave | Clic en un equipo del plano → pop-up con sus CML (t actual / t mín) y acceso directo; clic en un área → filtra la tabla; filtros por área, familia y condición; clic en una fila → abre ese equipo y CML |
| **Equipos** | Barra lateral con la estructura Planta › Área › Sistema › Equipo; página del equipo con migas de pan (ubicación técnica) | Al abrir un equipo se muestra su **CML más crítico**. Dos vistas: **Resumen y CML** y **Diseño y espesores** |
| ↳ Resumen y CML | Ficha técnica, esquema con marcadores (color = condición), 6 indicadores del CML, gráfico espesor vs tiempo, **especificaciones del CML** (identificación, historial, pérdida acumulada, margen consumido, CR LP/CP, fecha en que llega a t alerta y t mín), historial | **Agregar medición**; ver cálculos paso a paso en «Ver cálculos»; agregar CML con coordenadas (x, y); mover marcador; adjuntar esquema PNG/JPG o PDF; editar o eliminar el equipo |
| ↳ Diseño y espesores | Variables de diseño, esfuerzo admisible y «escalera» de espesores de pared en mm (a escala, con eje), agrupada en diseño/fabricación y servicio, margen sobre el mínimo y tabla por CML | Cambiar P, T, diámetro, E, CA… y presionar Enter/Tab: se recalcula todo |
| **Plan** | Próximas mediciones de espesor agrupadas: acción inmediata, vencidas, por mes y sin fecha, con el criterio y la norma de cada intervalo | Clic en una fila → abre el CML; **Exportar plan CSV** |
| **Riesgo (RBI)** | D<sub>f</sub>, P<sub>f</sub>, riesgo de área y económico, dos matrices 5×5, prioridad y efecto de la inspección | Cambiar CML gobernante, confianza en la CR, n° de inspecciones A–D, puntaje de gestión, C<sub>A</sub>, C<sub>E</sub>, moneda |
| **Validación** | 14 casos: valor esperado (cálculo manual) vs. valor del programa, con diferencia % | Mostrar en la defensa |
| **Acerca** | Normas y ediciones, supuestos, limitaciones, herramientas, uso de IA y enlace al repositorio | Mostrar en la defensa |

**Fecha de evaluación** (arriba a la derecha, «Evaluado al»). Todo se calcula «al día» de esa fecha: condición, próxima inspección y RBI. El caso demo viene fijo al 26-11-2026 para que los valores de la presentación no cambien. Si se adelanta (p. ej. a 01-06-2027) se ve en vivo cómo un CML en alerta pasa a *Inspección vencida*. Las mediciones posteriores a la fecha elegida no se consideran.

**Otras ayudas.** Los íconos «?» explican cada indicador. En *Diseño* y *Riesgo (RBI)*, un recuadro «Último cambio» muestra el antes → después; los campos distintos del caso demo quedan en ámbar y «↺» los devuelve al valor original. En Planta, la tarjeta *Calidad de datos* reúne los avisos de todos los CML. En *Riesgo (RBI)* se puede elegir el recipiente y, con dos o más evaluados, aparece la matriz y el ranking de riesgo de la planta. En cada equipo, «Imprimir ficha» genera un informe para guardar en PDF.

**Menú «Proyecto»** (arriba a la derecha). Los cambios se guardan solos en el navegador (el estado aparece al lado, p. ej. «Guardado 13:01»). El menú agrupa las acciones sobre el archivo, separadas de la navegación para evitar errores:
- **Guardar ahora** · **Exportar proyecto** (JSON con equipos, CML, mediciones, esquemas y PDF) · **Importar proyecto** (se valida; si hay datos inválidos se rechaza e indica el motivo) · **Exportar resumen CSV** (para Excel).
- **Restablecer caso demo**, en rojo y al final, porque descarta los cambios no exportados (pide confirmación).

**Estados de un CML** (orden de gravedad):
✕ Bajo el mínimo (t medido < t mín) › ? Información insuficiente (menos de 2 mediciones comparables) › ◷ Inspección vencida (hoy > próxima fecha) › ▲ Alerta (t medido < t mín + CR·2 años) › ● Normal.

## 2. Comparación con el enunciado, sección por sección

Leyenda: ✅ cumplido · ⚠️ cumplido con observación · 🔲 pendiente del grupo.

### §2–3 Modalidad, alcance mínimo y caso demostrativo
| Requisito | Estado | Dónde |
|---|---|---|
| Publicada en GitHub Pages, funciona desde el link | ✅ | Link arriba (probado en navegador real) |
| Flujo: seleccionar equipo → antecedentes → CML → medición → evaluación e inspección | ✅ | Equipos → barra lateral → Equipo → CML → Nueva medición |
| Tuberías B31.3/API 570, recipientes VIII-1/API 510, tanques API 650/653 | ✅ | Las tres familias en el caso demo |
| ≥ 3 CML por familia | ✅ | Tubería 4, recipiente 3, tanque 3 |
| 3 campañas históricas | ✅ | Tubería 2019/2022/2025, recipiente 2019/2022/2025 (+ línea base 2016), tanque 2018/2021/2024 |
| Un esquema por familia | ✅ | Equipos → Resumen y CML |
| Caso completo de RBI | ✅ | Riesgo (RBI) → V-201 |
| Catálogo acotado, ediciones y alcance declarados | ✅ | Acerca y `docs/fundamentos.md` |
| Agregar/modificar datos en vivo y obtener resultados | ✅ | Nueva medición, Diseño, RBI |

### §4.1 Registro de equipos y ubicaciones técnicas
| Requisito | Estado | Dónde |
|---|---|---|
| Crear/editar equipos en estructura planta › área › sistema › equipo/línea › componente | ✅ | + Nuevo equipo / Editar; el componente se define en cada CML |
| TAG, descripción, servicio, fluido, material, dimensiones, espesor nominal, diseño y operación, código | ✅ | Formulario de equipo + pestaña Diseño |
| Circuito de inspección en tuberías | ✅ | Campo "Circuito" (CI-HF-01) y clase API 570 |

### §4.2 Materiales y espesores de evaluación
| Requisito | Estado | Dónde |
|---|---|---|
| Esfuerzo admisible a la temperatura, factores de junta | ✅ | Diseño → recuadro del material (interpolado de B31.3 Tabla A-1, II-D Tabla 1A, API 650 Tabla 5.2a) |
| Distinguir nominal, requerido, mínimo en servicio, medido y alerta | ✅ | Diseño → escalera de espesores; Equipo → indicadores |
| Explicar sobreespesor por corrosión y tolerancia de fabricación | ✅ | Diseño → "Definiciones de espesor" |
| Justificar la alerta | ✅ | t<sub>alerta</sub> = t<sub>mín</sub> + CR × 2 años (plazo de intervención) |
| Mostrar entradas, unidades, ecuación, referencia y resultado | ✅ | "Ver cálculos" en Equipo y Diseño |

### §4.3 Documentación técnica y CML/TML
| Requisito | Estado | Dónde |
|---|---|---|
| Asociar esquemas/fotos y marcadores con coordenadas por formulario | ✅ | Equipo → esquema; "+ Agregar CML" y "Posición del marcador" |
| Vincular CML con equipo, componente, ubicación e historial; explicar convención | ✅ | Equipo → CML; nota bajo el esquema |
| Adjuntar PDF para consulta | ✅ | Equipo → "Documentación técnica" |

### §4.4 Mediciones, corrosión y vida remanente
| Requisito | Estado | Dónde |
|---|---|---|
| Medición con fecha, espesor, unidad, técnica y observaciones | ✅ | Formulario "Nueva medición" |
| CR corto y largo plazo, CR adoptada justificada, vida remanente | ✅ | "Ver cálculos" (se adopta la mayor: criterio conservador de la clase 05) |
| Gráfico espesor vs tiempo | ✅ | Equipo → gráfico con proyección |
| Detectar datos insuficientes, fechas inconsistentes, CR nula/negativa, bajo mínimo | ✅ | Mensajes rojos sobre el gráfico; estados |
| Identificar cambio de punto, reparación, reemplazo | ✅ | Campo "Evento": reinicia la serie (ej. CML-101-03) |

### §4.5 Próxima inspección y alertas
| Requisito | Estado | Dónde |
|---|---|---|
| Próxima fecha según API 510/570/653 con tipo, fecha de referencia, intervalo y criterio gobernante | ⚠️ | "Ver cálculos" → Intervalo. Limitado a medición de espesores (lo permite el enunciado). Ediciones declaradas: API 510 10ª ed. (2014), API 570 4ª ed. (2016), API 653 5ª ed. (2014); el texto completo no estaba en la carpeta, criterios de los apuntes. Un CML bajo el mínimo muestra "Inmediata" |
| Reglas por familia; en tanques, alcance sobre manto y datos pendientes | ✅ | Aviso en los CML del tanque |
| Condiciones normal, alerta, bajo mínimo, vencida | ✅ | Planta, Inicio y badges (+ "información insuficiente") |

### §5 Módulo RBI
| Requisito | Estado | Dónde |
|---|---|---|
| 1. Factor de daño por adelgazamiento con ecuaciones y referencias | ✅ | RBI → "Desarrollo del cálculo" (API 581 Parte 2 §4.5.7, ec. 2.12–2.20) |
| 2. Cómo se obtiene P<sub>f</sub>; distinguir D<sub>f</sub> de P<sub>f</sub> | ✅ | Indicadores separados; P<sub>f</sub> = gff × F<sub>MS</sub> × D<sub>f</sub> |
| 3. C<sub>A</sub> en m² y C<sub>E</sub> con moneda y base de valoración | ✅ | RBI → Entradas |
| 4. Riesgo de área y económico por separado, base anual | ✅ | Indicadores R<sub>A</sub> (m²/año) y R<sub>E</sub> (USD/año) |
| 5. Matriz y prioridad | ✅ | Dos matrices + prioridad |
| Modelo simplificado declarado; efecto de la inspección explicado | ✅ | "Supuestos del modelo" y tabla "Efecto de la inspección" |

### §6 Resultados, conservación y validación
| Requisito | Estado | Dónde |
|---|---|---|
| Panel con filtros por ubicación, familia o condición | ✅ | Planta → filtros sobre la tabla |
| Guardar y recuperar con relaciones y adjuntos | ✅ | Guardado automático + Exportar/Importar |
| Comparación independiente: un cálculo por familia + RBI | ⚠️ | Validación (14 casos). **El grupo debe rehacer al menos 4 casos a mano o en Excel** para que la comparación sea realmente independiente y poder defenderla |
| Casos normal, alerta, bajo mínimo e insuficiente | ✅ | Validación → "Casos de condición en la demo" |

### §7 Herramientas
| Requisito | Estado |
|---|---|
| Python, VS Code, Git y GitHub, IA en modo agente | ✅ |
| PyScript/Pyodide, pandas, NumPy, Matplotlib, json/csv/datetime/math | ✅ |
| pytest para comparar cálculos | ✅ (37 pruebas + prueba en navegador real) |
| Pillow, pyscript.storage (opcionales) | — No usados (localStorage cumple la función) |
| Indicar herramientas de IA, tareas apoyadas y comprobaciones | ✅ en la app (Alcance) · 🔲 en las diapositivas |

### §8 Demostración (6 pasos)
| Paso | Cómo hacerlo |
|---|---|
| 1. Abrir la app y mostrar las 3 familias | Inicio (tarjetas de familias) → Planta |
| 2. Equipo, ubicación técnica y esquema con CML | Inicio → tarjeta «Recipiente» (abre V-201 en su CML crítico; migas = ubicación técnica) → clic en CML-201-02 |
| 3. Agregar medición y ver CR, vida remanente, condición y fecha | "Nueva medición" → espesor 12,4 → Agregar y recalcular |
| 4. Cambiar variable de diseño y ver efecto | Diseño y espesores → Presión 1,5 → 2,0 → Enter |
| 5. Modificar consecuencia y ver cambio de riesgo | Riesgo (RBI) → C<sub>E</sub> 450 000 → 5 000 000 → Enter (pasa de Medio-alto a Alto; el RBI parte en CML-201-03, el más crítico) |
| 6. Guardar, recuperar y explicar validaciones | Proyecto → Exportar → Restablecer caso demo → Importar → Validación |

## 3. Rúbrica (§9)

| Criterio | Peso | Estado | Qué falta |
|---|---|---|---|
| Fundamento técnico y cálculos | 40 % | ✅ Ecuaciones con referencia, 14 casos de validación, ejercicio de clase reproducido | Rehacer casos de validación a mano; confirmar criterios API 510/570/653 si consiguen las normas |
| Funcionamiento e integración | 30 % | ✅ Publicada, datos vinculados, recálculo en vivo, gráficos, guardado, probada en navegador real | Abrir el link antes de exponer (carga inicial) |
| Presentación y defensa | 20 % | 🔲 | Diapositivas, ensayo de 15 min, que todos entiendan los cálculos |
| Trazabilidad y verificación | 10 % | ✅ Ediciones declaradas, `docs/fundamentos.md`, pruebas automáticas, uso de IA declarado | Incluirlo en las diapositivas con los links |
