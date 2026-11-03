# Entregable E3 · Agentes I: el bucle agéntico

Agente de atención técnica de Tostadero Retiro, hecho desde cero (P1–P2), con LangChain (P3)
y con un enrutador delante (P4). Modelo del agente: `anthropic/claude-haiku-4.5` vía OpenRouter.

| Fichero | Qué es |
| --- | --- |
| `s3_agente.py` | P1. Clase `Agente` con trazas, límite de pasos, aprobación humana y métricas de tokens |
| `s3_experimentos.py` | P2. Los cinco experimentos del enunciado (más dos variantes) automatizados |
| `s3_agente_langchain.py` | P3. El mismo agente con `create_agent` + middleware |
| `s3_enrutador.py` | P4. Clasificador de la sesión 2 + camino barato + agente, con medición |
| `salidas/` | Trazas reales de cada ejecución |

Los scripts se ejecutan desde la raíz de `Master-Bloque4` (importan `herramientas.py`,
`llm_client.py` y `s2_extraer_correo.py`).

---

## P1. Un agente desde cero

Sobre el código del kit he añadido tres cosas pequeñas:

- **`aprobador` inyectable**: por defecto pregunta en consola, pero se puede pasar una función.
  Así los experimentos y el enrutador se pueden ejecutar sin teclear.
- **Métricas por ejecución**: `agente.llamadas`, `tokens_entrada` y `tokens_salida` (suma de
  `r.usage` dentro del bucle), necesarias para P4.
- **Errores de negocio como error**: si una herramienta devuelve `{"error": ...}` (p. ej. cliente
  inexistente en `crear_incidencia`), el `tool_result` se marca `is_error=True`.

Ejecución con el correo de ejemplo: `buscar_cliente` → `consultar_pedidos` → (aprobación) →
`crear_incidencia(prioridad="alta")` → respuesta. **3 llamadas, ~4.100 tokens de entrada,
~450 de salida.** La prioridad es correcta (el local no puede servir café) y los datos del pedido
(nº 1003, 496,40 €, pendiente) son reales.

## P2. Experimentos

| Experimento | Qué pasó |
| --- | --- |
| **1. Correo de ejemplo** | Secuencia `buscar_cliente` → `crear_incidencia` + `consultar_pedidos` en paralelo en el paso 2 → respuesta. Prioridad **alta**. En ningún momento dice cuándo llega el pedido (no hay ese dato): lo reconoce y deriva. |
| **2. `max_pasos=2`** | Hace todo el trabajo (¡incluida la incidencia!) pero se corta antes de redactar la respuesta. El cliente recibe *«He alcanzado el límite de pasos sin terminar. Paso el caso a una persona.»* La acción con efectos ya se ha ejecutado aunque el caso «no ha terminado»: el operador humano debe saberlo. |
| **3. Rechazar la aprobación** | No lo reintenta (respeta «No la repitas») y consulta el pedido. Pero **maquilla el rechazo**: dice al cliente que «ha habido un inconveniente en el sistema» y le promete que «alguien del equipo te llamará en breve», algo que nadie ha decidido. |
| **4. Quitar «Úsala solo si…»** | Con la pregunta tal cual (*«¿Revisáis las máquinas en agosto?»*) no crea incidencia ni con la frase ni sin ella: no hay cliente ni avería. Con una variante más tentadora (Bar La Esquina pide revisar la cafetera antes de vacaciones): **con la frase no la crea; sin la frase sí**, una incidencia de «revisión preventiva» con prioridad media y el SKU inventado `CAF-2G`. La descripción de la herramienta sí actúa como barrera. |
| **5. Quitar el paso 1 de `SISTEMA`** | No se inventa ids: sigue llamando a `buscar_cliente` primero. Ni siquiera quitando también «Úsala antes de cualquier otra herramienta que pida cliente_id» de la descripción. Necesita un id y la única forma de obtenerlo es buscar. Además, `crear_incidencia` valida el id en la BD, así que un id inventado volvería como error. |

**Hallazgo extra, el SKU de la máquina.** El SKU real de la cafetera de 2 grupos es `MAQ-010`.
En distintas ejecuciones el agente puso `MAQ-010`, `MAQ-002` o `MAQ-001` **sin consultar
`stock_producto`**: copia el ejemplo de la descripción o se lo inventa. El paso 1 protege el
`cliente_id`, pero nada protege `maquina`. Arreglos: validar el SKU dentro de `crear_incidencia`
(como ya se hace con el cliente) y añadir al procedimiento «busca la máquina con `stock_producto`».

**Conclusiones de P2**

- Las reglas importantes conviene tenerlas **en dos sitios** (prompt y descripción de la
  herramienta) y, si son críticas, **en el código** (validación en la función). El modelo fue
  robusto en lo que el código ya validaba (el cliente) y frágil en lo que no (el SKU).
- El límite de pasos corta, pero **no deshace**: las acciones con efectos deberían ir al final
  o registrarse para que la persona que recoge el caso sepa qué se hizo.
- Tras un rechazo, el modelo tiende a dar una explicación cómoda al cliente. Mejor devolver
  un mensaje más directivo (p. ej. *«Rechazado. Dile al cliente que un técnico revisará su caso; no
  prometas plazos»*).

---

## P3. Comparación: desde cero vs LangChain

Las dos versiones resuelven el mismo correo con la misma secuencia de herramientas y la misma
prioridad. Con LangChain, cambiar a `openai:google/gemini-3.8-flash` fue **solo cambiar la
cadena** (`python s3_agente_langchain.py openai:google/gemini-3.8-flash`). La misma clave de
OpenRouter vale para los dos.

| | Desde cero (`s3_agente.py`) | LangChain (`create_agent`) |
| --- | --- | --- |
| Líneas (kit, sin vacías ni comentarios) | 80, de ellas 46 del bucle `Agente` | 47, sin bucle propio |
| Bucle LLM ↔ herramientas | Lo escribimos nosotros | Lo pone el framework |
| Límite de pasos | `for paso in range(max_pasos)` | `ModelCallLimitMiddleware(run_limit=8)` |
| Aprobación humana | `input()` dentro del bucle: el proceso **se bloquea** esperando | `HumanInTheLoopMiddleware` + checkpointer: el grafo **se pausa**, se guarda el estado y se reanuda con `Command(resume=…)`, incluso desde otro proceso o petición HTTP (con `SqliteSaver`) |
| Cambio de proveedor | Reescribir el bucle (formato de mensajes distinto) | Una cadena: `"anthropic:…"` → `"openai:…"` |
| Esquemas de herramientas | Escritos a mano en JSON Schema | Se derivan de la firma y el docstring (`Literal` → `enum`) |
| Trazas | `print` en cada paso, con el texto de razonamiento | Hay que reconstruirlas del estado (o usar LangSmith) |
| Formato de mensajes | Control total (`is_error`, texto del rechazo…) | Lo decide el framework |
| Dependencias | `anthropic` | `langchain`, `langgraph`, `langchain-anthropic`, `langchain-openai` |

**Qué viene resuelto:** pausa y reanudación de verdad (la parte más difícil de hacer bien a mano),
límites como middleware que se combinan sin tocar el bucle, y portabilidad entre proveedores.

**Qué se pierde:** visibilidad del bucle. En la versión propia veo cada paso mientras ocurre.
En LangChain solo veo el resultado final salvo que recorra `estado["messages"]` o use LangSmith.
También se pierde control fino del formato. Por ejemplo, con el rechazo, en la versión propia
elijo el texto exacto que recibe el modelo («No la repitas»). Con el middleware lo decide el
framework, y en la prueba con Gemini, tras rechazar la incidencia, **el modelo le dijo al cliente
«He tomado nota de la avería»**, como si se hubiera registrado. El rechazo no quedó claro.

**Cuándo usaría cada una:** desde cero para aprender, depurar o cuando el bucle es corto y quiero
controlar cada mensaje. LangChain cuando necesito aprobaciones asíncronas reales (un operador que
aprueba horas después), varios proveedores o middleware reutilizable. Es decir, cuando el agente
pasa de script a servicio.

---

## P4. Enrutador: workflow delante del agente

`atender(correo)` clasifica con el extractor de la sesión 2 (`gpt-5.4-mini`, salida
estructurada). Si es `consulta`, responde un LLM de **una sola llamada** con `SISTEMA_CONSULTAS`.
Si no, va al agente.
`SISTEMA_CONSULTAS` incluye el **catálogo con precios leído de la BD** y prohíbe inventar
horarios, plazos o políticas. Si hace falta información de la cuenta, el modelo dice que lo pasa
al equipo.

Medición con 12 correos (los 6 de la sesión 2 + 6 nuevos; 7 son consultas):

| Estrategia | Llamadas | Tokens entrada | Tokens salida | USD (precios OpenRouter) |
| --- | ---: | ---: | ---: | ---: |
| Todo al agente | 23 | 28.267 | 2.949 | 0,0430 |
| Enrutador, barato = `gemini-3.8-flash` | 33 | 23.568 | 6.930 | **0,0528 (+23 %)** |
| Enrutador, barato = `gpt-5.4-nano` | 32 | 22.071 | 2.794 | **0,0316 (−26 %)** |

- **Clasificación: 12/12.** 7 de 12 correos fueron por el camino barato.
- **Hay más llamadas, no menos**: el clasificador añade una llamada a *todos* los correos.
  Lo que baja son los tokens de entrada: una consulta cuesta ~600 tokens por el camino barato
  frente a ~1.100–2.500 en el agente, que reenvía las definiciones de herramientas en cada paso.
- **Con Gemini el enrutador sale más caro que no tenerlo.** Es un modelo de razonamiento:
  **644 tokens de salida por consulta** frente a **61 con `gpt-5.4-nano`**, para respuestas
  de 2–4 frases. El modelo del camino barato tiene que ser barato *en salida*, no solo en precio
  por token.
- **Calidad**: el camino barato acertó donde el agente falló. Con *«¿Qué precio tiene la
  cafetera de dos grupos?»* el agente buscó el texto literal, no encontró nada y pidió el SKU.
  Con *«¿qué orígenes tenéis?»* dijo que no podía consultarlo. Con el catálogo en el prompt,
  los dos baratos respondieron bien.
- **Coste del enrutador**: *«Hotel Prado Suites: ¿cuándo llega nuestro último pedido?»* se
  clasifica (bien) como consulta, pero necesita datos reales. El agente respondía con el pedido
  nº 1002 «en reparto». El camino barato solo puede decir «lo paso al equipo». Mejora: enrutar
  por **«¿necesita datos del cliente?»** y no solo por tipo, p. ej.
  `if tipo == "consulta" and clasificacion.cliente is None`.

**Conclusión:** el enrutador ahorra un 26 % con un modelo barato de verdad y además
responde mejor a las consultas de catálogo. Con un modelo que razona en exceso puede salir más caro
que no tenerlo. El ahorro crece con la proporción de consultas simples en el correo real.

> Nota: durante las pruebas el agente creó incidencias reales en `tostadero.db` (aprobación
> automática). `python crear_bd.py` deja la BD como al principio.
