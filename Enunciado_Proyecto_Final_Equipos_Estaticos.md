# Proyecto Final — Aplicación web para la gestión e inspección de equipos estáticos

**Sede Viña del Mar · Departamento de Mecánica**
**Carrera:** Ingeniería en Mantenimiento Industrial
**Asignatura:** Mantenimiento a Equipos Estáticos (MAN040-B)
**Profesor:** Mg. Ing. Alejandro Badilla Bello
**Modalidad:** Grupos de 3 a 5 integrantes · Presentación y demostración funcional

---

## 1. Objetivo del proyecto

Desarrollar y presentar una aplicación web que permita gestionar antecedentes técnicos de equipos estáticos, registrar mediciones de espesor, evaluar su deterioro por corrosión y proponer próximas inspecciones. El proyecto integrará criterios de diseño, inspección en servicio e inspección basada en riesgo (RBI), utilizando Python y herramientas de inteligencia artificial en modo agente.

## 2. Modalidad de trabajo y evaluación

El trabajo se realizará en grupos de 3 a 5 integrantes. La evaluación se efectuará mediante una presentación oral con demostración de la aplicación en funcionamiento. Todos los integrantes deberán participar y responder preguntas sobre el desarrollo y sus fundamentos.

> **Sin informe escrito.** Los antecedentes, supuestos, referencias, validaciones y limitaciones se expondrán en las diapositivas y en la defensa oral. La presentación incluirá los enlaces a la aplicación publicada y al repositorio de GitHub.

Se aceptará precargar los equipos y sus antecedentes. Durante la exposición deberán incorporarse o modificarse datos y obtenerse resultados calculados por el programa.

## 3. Enunciado y alcance mínimo

Cada grupo desarrollará un prototipo académico inspirado en las funciones de gestión de integridad de herramientas como UltraPIPE. La aplicación se publicará en **GitHub Pages** y permitirá ejecutar el flujo: seleccionar un equipo, consultar sus antecedentes, revisar sus CML/TML, incorporar una medición y actualizar su evaluación e inspección.

| Familia | Diseño / construcción | En servicio | Geometría mínima |
|---|---|---|---|
| Tuberías de proceso | ASME B31.3 | API 570 | Tramo recto |
| Recipientes a presión | ASME VIII, División 1 | API 510 | Envolvente cilíndrica |
| Tanques atmosféricos | API 650 | API 653 | Virolas del manto |

El caso demostrativo incluirá un sistema de tuberías, un recipiente y un tanque, con **al menos tres ubicaciones de monitoreo por familia**, **tres campañas históricas** y **un esquema por familia**. Se incorporará además un caso completo del módulo RBI.

El catálogo podrá limitarse a uno o dos materiales por familia y a un intervalo de temperaturas definido. Cada grupo declarará las ediciones normativas y el alcance de sus cálculos. La implementación de otras geometrías o mecanismos de daño será una ampliación opcional.

## 4. Funciones mínimas de la aplicación

### 4.1. Registro de equipos y ubicaciones técnicas

Crear o editar equipos asociados a una estructura de planta, área, sistema, equipo o línea y componente. Registrar TAG, descripción, servicio, fluido, material, dimensiones, espesor nominal, condiciones de diseño y operación y código aplicable. Para tuberías, identificar el circuito de inspección.

### 4.2. Materiales y espesores de evaluación

Incorporar esfuerzos admisibles a la temperatura correspondiente, factores de junta y demás parámetros aplicables. Cada familia empleará sus propias referencias; para recipientes se considerará ASME II, Parte D, cuando corresponda.

Distinguir espesor **nominal**, **requerido por cálculo**, **mínimo admisible en servicio**, **medido** y **de alerta**. Explicar el sobreespesor por corrosión y la tolerancia de fabricación. Justificar la alerta, por ejemplo mediante un margen por pérdida prevista durante un plazo de intervención.

Mostrar entradas, unidades, ecuación, referencia y resultado para los casos implementados.

### 4.3. Documentación técnica y CML/TML

Asociar isométricos, esquemas o fotografías a los equipos y representar sus ubicaciones de monitoreo mediante marcadores. Se admitirán imágenes PNG o JPG con coordenadas ingresadas en un formulario.

Vincular cada CML/TML con su equipo, componente, ubicación e historial, y explicar la convención utilizada. Los PDF podrán adjuntarse para consulta; su anotación será opcional.

### 4.4. Mediciones, corrosión y vida remanente

Conservar mediciones por punto con fecha, espesor, unidad, técnica y observaciones. Calcular velocidades de corrosión de corto y largo plazo, justificar la adoptada y estimar la vida remanente con datos comparables. Graficar espesor versus tiempo.

Reconocer datos insuficientes, fechas inconsistentes, velocidades nulas o negativas y espesores bajo el mínimo. Identificar cambios de punto, reparaciones y reemplazos que afecten la comparación.

### 4.5. Próxima inspección y alertas

Calcular la próxima fecha según API 510, API 570 o API 653, indicando tipo de inspección, fecha de referencia, intervalo y criterio gobernante. Se admite limitar el cálculo a las próximas mediciones de espesor.

Aplicar reglas por familia y tipo de inspección. En tanques, declarar el alcance sobre el manto y los datos pendientes para otras inspecciones. Mostrar condición **normal**, **alerta**, **espesor bajo el mínimo** e **inspección vencida**.

## 5. Módulo RBI por adelgazamiento generalizado

El prototipo incorporará un módulo simplificado de RBI, utilizando **API RP 580** como referencia del proceso y **API RP 581** para el método cuantitativo seleccionado. Se admitirá implementar el submodelo de adelgazamiento para una familia de equipos, siempre que su aplicabilidad y sus simplificaciones queden claramente declaradas.

El módulo deberá:

1. Calcular un factor de daño por adelgazamiento generalizado, indicando ecuaciones, parámetros, antecedentes de inspección y referencias.
2. Documentar cómo se obtiene la probabilidad o frecuencia de falla utilizada. El factor de daño deberá distinguirse de la probabilidad de falla.
3. Recibir directamente el área de consecuencia en m² y la consecuencia económica, con moneda y base de valoración.
4. Presentar por separado el riesgo asociado al área y el riesgo económico, manteniendo una base temporal y un escenario de falla consistentes.
5. Mostrar una matriz o clasificación de riesgo y una prioridad de inspección.

Si se utiliza una frecuencia anual de falla $f_F$, los resultados podrán expresarse como:

$$R_A = f_F \, C_A \quad [\text{m}^2/\text{año}]$$

$$R_E = f_F \, C_E \quad [\text{moneda}/\text{año}]$$

donde $C_A$ es el área de consecuencia y $C_E$ la consecuencia económica. Si se utiliza una probabilidad, deberá indicarse el horizonte temporal al que corresponde.

> **Alcance del modelo.** Las consecuencias serán datos ingresados por el usuario; no se exige modelar la liberación ni sus efectos físicos. La implementación parcial deberá identificarse como un modelo académico simplificado. El efecto de una inspección sobre la incertidumbre deberá explicarse; una inspección no recupera el espesor perdido.

## 6. Resultados, conservación de datos y validación

La aplicación dispondrá de un panel de resultados y permitirá filtrar o seleccionar equipos por ubicación, familia o condición. Será suficiente presentar los antecedentes, tendencias y cálculos en pantalla.

Se deberá guardar y recuperar el caso demostrativo, mediante un archivo de proyecto importable y exportable, o almacenamiento persistente del navegador. El respaldo deberá conservar las relaciones entre equipos, puntos y mediciones, e incluir los adjuntos o permitir restablecerlos de manera explícita.

La presentación incluirá una **comparación independiente** para un cálculo de cada familia y un cálculo del módulo RBI, mostrando entradas, referencia, resultado esperado y resultado del programa.

Preparar casos que permitan demostrar condición normal, alerta, espesor bajo el mínimo e información insuficiente. La verificación se expondrá en las diapositivas o en la propia aplicación.

## 7. Herramientas de desarrollo sugeridas

Se utilizarán Python, Visual Studio Code, Git y GitHub, con apoyo de herramientas de IA en modo agente, tales como GitHub Copilot u OpenCode. Se recomienda separar las funciones de cálculo de la interfaz para comprobarlas primero con casos conocidos.

> **Arquitectura compatible con GitHub Pages.** Se recomienda HTML y CSS para la interfaz, con PyScript y Pyodide para ejecutar Python en el navegador. GitHub Pages publica archivos estáticos y no ejecuta un servidor Python. La aplicación deberá funcionar desde su enlace público.

| Herramienta / biblioteca | Aplicación propuesta | Uso |
|---|---|---|
| PyScript y Pyodide | Ejecutar Python en el navegador y conectar formularios, eventos y resultados. | Base recomendada |
| pandas | Organizar equipos y mediciones; leer y exportar tablas CSV. | Recomendada |
| NumPy | Operar con series de mediciones y evaluar escenarios numéricos. | Recomendada |
| Matplotlib | Mostrar tendencias, esquemas con marcadores y matrices de riesgo. | Recomendada |
| Pillow | Abrir y preparar imágenes PNG o JPG de los equipos. | Opcional |
| json, csv, datetime, math, io | Guardar proyectos, procesar fechas, manejar datos y efectuar cálculos básicos. | Biblioteca estándar |
| pyscript.storage | Conservar datos en el almacenamiento persistente del navegador. | Opcional |
| pytest | Comparar localmente las funciones de cálculo con casos de referencia. | Verificación local |

Las bibliotecas aportan herramientas de programación. Las ecuaciones, valores admisibles y reglas de inspección deberán provenir de las referencias aplicables y ser verificados por el grupo. Se recomienda probar y fijar las versiones compatibles antes de completar el desarrollo.

### Uso de inteligencia artificial

La IA podrá apoyar la programación, revisión de errores, preparación de datos y elaboración de las diapositivas. En la presentación se indicarán las herramientas utilizadas, las tareas apoyadas y las comprobaciones realizadas. Todos los integrantes deberán comprender y defender los cálculos y las decisiones que presentan.

Se utilizarán antecedentes ficticios o autorizados. Los documentos normativos y catálogos se emplearán respetando sus condiciones de uso; no será necesario reproducirlos completos en el repositorio público.

## 8. Presentación y demostración funcional

La exposición tendrá una duración de **15 minutos**, incluida la presentación de uso y la demostración funcional de la aplicación, seguida de **5 minutos de preguntas**. Distribución sugerida:

- 3 min — problema y fundamentos
- 9 min — demostración de uso
- 3 min — validaciones, resultados y limitaciones

Durante la demostración se deberá:

1. Abrir la aplicación publicada y mostrar las tres familias de equipos.
2. Seleccionar un equipo, consultar su ubicación técnica y su esquema con CML/TML.
3. Agregar una medición y actualizar la velocidad de corrosión, vida remanente, condición y próxima fecha.
4. Cambiar una variable de diseño u operación y mostrar su efecto sobre el espesor calculado.
5. Modificar una consecuencia y mostrar el cambio en el riesgo o su clasificación.
6. Guardar y recuperar el caso, y explicar las validaciones independientes.

> **Entrega:** una presentación en PDF o PPTX, con identificación de los 3 a 5 integrantes y enlaces a la aplicación y al repositorio. Los fundamentos, fuentes, validaciones y uso de IA se incluirán en las diapositivas. No se solicita informe, memoria técnica ni bitácora escrita independiente.

Se recomienda disponer de una ejecución local probada como respaldo de la demostración. Todos los integrantes deberán participar; el docente podrá formular preguntas individuales.

## 9. Criterios de evaluación

| Criterio | Peso | Evidencia en la presentación |
|---|---|---|
| Fundamento técnico y cálculos | 40 % | Referencias, unidades, espesores, corrosión, fechas y RBI coherentes; comparación con casos independientes. |
| Funcionamiento e integración | 30 % | Datos vinculados, cambios en vivo, recálculo, gráficos, conservación de datos y publicación funcional. |
| Presentación y defensa | 20 % | Exposición clara, participación de todos y comprensión de decisiones, resultados y limitaciones. |
| Trazabilidad y verificación | 10 % | Fuentes y versiones identificadas; evidencia de revisión de cálculos y del apoyo de IA. |
| **Total** | **100 %** | |

## 10. Referencias de trabajo

Consultar ASME B31.3; ASME VIII, División 1; ASME II, Parte D; API 650; API 510, 570 y 653; API RP 580 y 581, según corresponda. La edición y las secciones efectivamente utilizadas deberán identificarse en la presentación. Para el desarrollo se recomienda la documentación oficial enlazada en la sección de herramientas.
