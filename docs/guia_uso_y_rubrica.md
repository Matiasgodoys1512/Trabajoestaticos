# Guía de uso y comparación con el enunciado

App: https://matiasgodoys1512.github.io/Trabajoestaticos/ (primera carga 20–40 s).

## 1. Cómo se usa (lo básico)

**Barra superior**
- **Guardar**: guarda en este navegador (también se guarda solo con cada cambio; el estado aparece a la izquierda, p. ej. "Guardado 13:01").
- **Exportar**: descarga el proyecto completo en un archivo `.json` (equipos, CML, mediciones, esquemas y PDF).
- **Importar**: carga un `.json` exportado. Si el archivo tiene datos inválidos, se rechaza e indica el motivo.
- **CSV**: descarga la tabla resumen de CML (se abre en Excel).
- **Restablecer demo**: vuelve al caso demostrativo original.

**Barra lateral**: árbol Planta › Área › Sistema › Equipo. El punto de color es la condición del equipo (la de su peor CML). **Filtros** por área, familia y condición. **+ Nuevo equipo** abre el formulario de alta.

**Pestañas**

| Pestaña | Qué muestra | Qué se puede hacer |
|---|---|---|
| **Panel** | Totales por condición y tabla de todos los CML, ordenada de más grave a menos grave | Clic en una fila → abre ese equipo y CML |
| **Equipo** | Ficha técnica, esquema con marcadores CML (color = condición), CML como botones | Elegir CML; agregar CML (con coordenadas x, y); subir esquema PNG/JPG o PDF; editar o eliminar el equipo |
| ↳ CML seleccionado | 6 indicadores (t actual, t mín, t alerta, CR, vida remanente, próxima inspección), gráfico espesor vs tiempo, historial | **Agregar medición** (fecha, espesor en mm o pulgadas, técnica, evento, observaciones); ver cálculos paso a paso en "Ver cálculos"; mover marcador; borrar mediciones |
| **Diseño** | Variables de diseño, esfuerzo admisible del material y "escalera" de espesores (nominal, diseño, medido, alerta, mínimo, requerido) | Cambiar P, T, diámetro, E, CA… y presionar Enter/Tab: se recalcula todo |
| **RBI** | D<sub>f</sub>, P<sub>f</sub>, riesgo de área y económico, dos matrices 5×5, prioridad y efecto de la inspección | Cambiar CML gobernante, confianza en la CR, n° de inspecciones A–D, puntaje de gestión, C<sub>A</sub>, C<sub>E</sub>, moneda |
| **Validación** | 14 casos: valor esperado (cálculo manual) vs. valor del programa, con diferencia % | Mostrar en la defensa |
| **Alcance** | Normas y ediciones, supuestos, limitaciones, herramientas y uso de IA | Mostrar en la defensa |

**Estados de un CML** (orden de gravedad):
✕ Bajo el mínimo (t medido < t mín) › ? Información insuficiente (menos de 2 mediciones comparables) › ◷ Inspección vencida (hoy > próxima fecha) › ▲ Alerta (t medido < t mín + CR·2 años) › ● Normal.

## 2. Comparación con el enunciado, sección por sección

Leyenda: ✅ cumplido · ⚠️ cumplido con observación · 🔲 pendiente del grupo.

### §2–3 Modalidad, alcance mínimo y caso demostrativo
| Requisito | Estado | Dónde |
|---|---|---|
| Publicada en GitHub Pages, funciona desde el link | ✅ | Link arriba (probado en navegador real) |
| Flujo: seleccionar equipo → antecedentes → CML → medición → evaluación e inspección | ✅ | Barra lateral → Equipo → CML → Nueva medición |
| Tuberías B31.3/API 570, recipientes VIII-1/API 510, tanques API 650/653 | ✅ | Las tres familias en el caso demo |
| ≥ 3 CML por familia | ✅ | Tubería 4, recipiente 3, tanque 3 |
| 3 campañas históricas | ✅ | Tubería 2019/2022/2025, recipiente 2019/2022/2025 (+ línea base 2016), tanque 2018/2021/2024 |
| Un esquema por familia | ✅ | Pestaña Equipo |
| Caso completo de RBI | ✅ | Pestaña RBI (V-201) |
| Catálogo acotado, ediciones y alcance declarados | ✅ | Pestaña Alcance y `docs/fundamentos.md` |
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
| Condiciones normal, alerta, bajo mínimo, vencida | ✅ | Panel y badges (+ "información insuficiente") |

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
| Panel con filtros por ubicación, familia o condición | ✅ | Panel + Filtros |
| Guardar y recuperar con relaciones y adjuntos | ✅ | Guardado automático + Exportar/Importar |
| Comparación independiente: un cálculo por familia + RBI | ⚠️ | Pestaña Validación (14 casos). **El grupo debe rehacer al menos 4 casos a mano o en Excel** para que la comparación sea realmente independiente y poder defenderla |
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
| 1. Abrir la app y mostrar las 3 familias | Panel |
| 2. Equipo, ubicación técnica y esquema con CML | Barra lateral → V-201 → clic en CML-201-02 |
| 3. Agregar medición y ver CR, vida remanente, condición y fecha | "Nueva medición" → espesor 12,4 → Agregar y recalcular |
| 4. Cambiar variable de diseño y ver efecto | Diseño → Presión 1,5 → 2,0 → Enter |
| 5. Modificar consecuencia y ver cambio de riesgo | RBI → C<sub>E</sub> 450 000 → 5 000 000 → Enter (pasa de Medio-alto a Alto; el RBI parte en CML-201-03, el más crítico) |
| 6. Guardar, recuperar y explicar validaciones | Exportar → Restablecer demo → Importar → pestaña Validación |

## 3. Rúbrica (§9)

| Criterio | Peso | Estado | Qué falta |
|---|---|---|---|
| Fundamento técnico y cálculos | 40 % | ✅ Ecuaciones con referencia, 14 casos de validación, ejercicio de clase reproducido | Rehacer casos de validación a mano; confirmar criterios API 510/570/653 si consiguen las normas |
| Funcionamiento e integración | 30 % | ✅ Publicada, datos vinculados, recálculo en vivo, gráficos, guardado, probada en navegador real | Abrir el link antes de exponer (carga inicial) |
| Presentación y defensa | 20 % | 🔲 | Diapositivas, ensayo de 15 min, que todos entiendan los cálculos |
| Trazabilidad y verificación | 10 % | ✅ Ediciones declaradas, `docs/fundamentos.md`, pruebas automáticas, uso de IA declarado | Incluirlo en las diapositivas con los links |
