# Entregable E2 · Salidas estructuradas y uso de herramientas

Modelos (todos vía OpenRouter, una sola clave): `openai/gpt-5.4-mini` (Responses API),
`anthropic/claude-haiku-4.5` (Messages API) y `google/gemini-3.8-flash` (Chat Completions).

| Fichero | Qué es |
| --- | --- |
| `s2_extraer_correo.py` | P1. Clasificador con 18 casos y validación de negocio con `buscar_cliente` |
| `s2_chat_herramientas.py` | P3. Bucle de herramientas con OpenAI, con traza y tokens por vuelta |
| `s2_chat_claude.py` / `s2_chat_gemini.py` | P4. El mismo bucle con Claude y con Gemini |
| `s2_comparar_asistentes.py` | P4. Las cuatro preguntas en los tres proveedores y la tabla comparativa |
| `salidas/` | Salida real de cada ejecución |

Los scripts se importan entre sí y usan `herramientas.py` y `tostadero.db`. Para ejecutarlos,
cópialos a la raíz junto a esos ficheros (como indica el kit: todo junto) y ejecuta, por ejemplo,
`python s2_comparar_asistentes.py`.

---

## P1. Clasificador de correos con evaluación

### Casos

Los 6 del kit más 12 nuevos (18 en total), con los casos difíciles que pide el enunciado:

| Tipo de caso | Casos | Ejemplo |
| --- | --- | --- |
| Del kit | 1–6 | «Necesito 20 kg del blend…» |
| Ironía | 7, 8 | «Genial, otra vez la cafetera sin presión. Me encanta empezar así el lunes.» → `incidencia` |
| Dos clientes | 9 | «Desde Bar La Esquina, y en nombre también del Restaurante Lumbre…» → `pedido` |
| En inglés | 10, 11 | «Our grinder stopped working this morning…» → `incidencia` |
| Sin nombre de negocio | 12, 13 | «URGENTE: la máquina echa humo por detrás.» → `incidencia` |
| Cliente que no existe en la BD | 14, 15 | «Somos Café Central…», «Cafetería Nube aquí…» |
| Ambiguos | 16–18 | «¿Cuánto cuesta el descafeinado? Y apuntadme 2 kg.» |

### Resultados

| Proveedor | 1.ª ejecución | Tras corregir la etiqueta del caso 16 |
| --- | ---: | ---: |
| OpenAI (`gpt-5.4-mini`) | 17 / 18 | **18 / 18** |
| Claude (`claude-haiku-4.5`) | 17 / 18 | **18 / 18** |
| Gemini (`gemini-3.8-flash`) | 17 / 18 | **18 / 18** |

### Fallos revisados y etiquetas corregidas

- **Caso 16** («¿Cuánto cuesta el descafeinado? Y apuntadme 2 kg. Bar La Esquina»). Lo etiqueté
  como `pedido` y **los tres modelos dijeron `mixto`**. Cuando los tres fallan igual, sospecho
  del caso y no del modelo. El correo contiene una consulta (precio) y un pedido (2 kg), así que
  `mixto` es correcto. **Error del caso, no del modelo**: cambio la etiqueta a `mixto`.
  El problema de fondo es que el esquema no define `mixto`. Para el modelo significa «más de una
  intención», y yo lo había pensado como «pedido + incidencia». Si importa la diferencia, hay que
  definirla en la descripción del campo.
- **Ironía, inglés y correos sin nombre**: ningún fallo. La ironía de los casos 7 y 8 no confunde
  a ningún modelo, y en inglés clasifican igual de bien (el `resumen` sale en español, como pide el
  esquema). Sin nombre de negocio, `cliente` sale `null` y no se lanza la validación.

### Validación de negocio

`validar_negocio()` comprueba que las cantidades sean positivas y que, **si hay cliente,
`buscar_cliente` lo encuentre en la BD**. Los avisos que saltaron:

| Caso | OpenAI | Claude | Gemini | ¿Correcto? |
| --- | --- | --- | --- | --- |
| 14 · Café Central | aviso | aviso | aviso | Sí: no existe |
| 15 · Cafetería Nube | aviso | aviso | aviso | Sí: no existe |
| 9 · dos clientes | — | aviso | aviso | **No: falsa alarma** |

En el caso 9, OpenAI devolvió solo el primer cliente. Claude y Gemini juntaron los dos en un
solo texto (`'Bar La Esquina / Restaurante Lumbre'`, `'Bar La Esquina y Restaurante Lumbre'`),
y ese texto no coincide con ningún cliente de la BD. Los dos existen, pero el esquema solo admite
**un** `cliente`. Corregirlo es cambiar el esquema a `clientes: list[str]` y validar cada uno,
no parchear la búsqueda. Es un buen ejemplo de que el esquema garantiza la forma, no el sentido.

---

## P3. El bucle de herramientas con OpenAI

Traza real (`salidas/p3_p4_asistentes.txt`):

| Pregunta | Herramientas (en orden y con argumentos) | Respuesta del asistente |
| --- | --- | --- |
| 1. ¿Qué pedidos pendientes tiene el Bar La Esquina y cuánto suman? | `buscar_cliente(texto="Bar La Esquina")` → id 1 · `consultar_pedidos(cliente_id=1)` | 1 pedido pendiente, el 1004 (30/09/2026), **98,00 €**. Es correcto: el 1001 está entregado y lo descarta. |
| 2. ¿Cuánto stock queda de descafeinado? | `stock_producto(texto="descafeinado")` | **45 unidades** de Café descafeinado 1 kg (CAF-003). Correcto. |
| 3. ¿Qué pedidos tiene el Bar Inexistente? | `buscar_cliente(texto="Bar Inexistente")` → `[]` | No encuentra el cliente y ofrece buscar otra variante del nombre. **No llama a `consultar_pedidos` ni se inventa un id**: trata la lista vacía como «no existe». |
| 4. Borra el pedido 1003 | ninguna | «No tengo una herramienta para borrar pedidos» y ofrece alternativas. No intenta usar otra herramienta en su lugar. |

- La pregunta 1 necesita **dos llamadas encadenadas**: la segunda usa el `id` que devolvió la
  primera. Por eso hacen falta tres vueltas del bucle: buscar, consultar y responder.
- En la 4 el modelo no puede llamar a una herramienta que no está en `tools`. Aun así, el bucle
  devuelve `{"error": "La herramienta … no existe."}` si llegara a pasar, en vez de lanzar un `KeyError`.

---

## P4. El mismo asistente con Claude y con Gemini

He portado el bucle a **los dos** proveedores. Ambos importan `SISTEMA` y `PREGUNTAS` de
`s2_chat_herramientas.py`, usan las mismas herramientas, la misma traza (`ejecutar_herramienta`
es común) y el mismo límite de 5 vueltas. Diferencias de formato que hay que resolver:

| | OpenAI (Responses) | Claude (Messages) | Gemini (Chat Completions) |
| --- | --- | --- | --- |
| Instrucciones | `instructions=` | `system=` | primer mensaje `role: system` |
| Llamada del modelo | item `function_call` | bloque `tool_use` en `content` | `message.tool_calls` |
| Argumentos | texto JSON | **dict** ya parseado | texto JSON |
| Devolver resultado | item `function_call_output` + `call_id` | bloque `tool_result` + `tool_use_id`, todos en un mensaje `user` | un mensaje `role: tool` por llamada |
| Tokens | `input_tokens` / `output_tokens` | `input_tokens` / `output_tokens` | `prompt_tokens` / `completion_tokens` |

### Comparación (las cuatro preguntas de P3)

| Pregunta | Proveedor | Llamadas a herramientas | Tokens entrada | Tokens salida | Calidad de la respuesta final |
| --- | --- | ---: | ---: | ---: | --- |
| 1. Pendientes Bar La Esquina | OpenAI | 2 | 1.041 | 91 | Correcta, concisa |
| | Claude | 2 | 3.519 | 242 | Correcta |
| | Gemini | 2 | 1.084 | 320 | Correcta |
| 2. Stock descafeinado | OpenAI | 1 | 597 | 49 | Correcta (45 uds.) |
| | Claude | 1 | 2.153 | 104 | Correcta, añade el precio |
| | Gemini | 1 | 586 | 152 | Correcta, añade el precio |
| 3. Bar Inexistente | OpenAI | 1 | 563 | 58 | Correcta, ofrece reintentar |
| | Claude | 1 | 2.137 | 198 | Correcta pero larga (lista de 3 posibles causas) |
| | Gemini | 1 | 566 | 155 | Correcta y directa |
| 4. Borra el pedido 1003 | OpenAI | 0 | 263 | 44 | Rechaza y ofrece alternativas |
| | Claude | 0 | 1.015 | 135 | Rechaza y enumera sus herramientas |
| | Gemini | 0 | 255 | 165 | Rechaza y deriva a administración |
| **Total** | OpenAI | 4 | **2.464** | **242** | |
| | Claude | 4 | **8.824** | 679 | |
| | Gemini | 4 | 2.491 | **792** | |

**Conclusiones**

- **Comportamiento idéntico**: los tres llaman a las mismas herramientas, en el mismo orden y con
  los mismos argumentos, y las cuatro respuestas usan los datos reales de la BD (verificado:
  pedido 1004 de 98 €, 45 unidades de CAF-003). Con herramientas bien descritas, el proveedor
  apenas cambia *qué* se hace.
- **Claude gasta ~3,6× más tokens de entrada** con la misma conversación: unos 750 tokens más
  por llamada (1.015 frente a 263 en la pregunta 4, que no usa herramientas). Es el coste fijo de
  cómo Anthropic presenta las herramientas al modelo (su prompt de sistema para herramientas y el
  formato de las definiciones), y se paga en cada vuelta. En la pregunta 1, con tres vueltas, se
  nota mucho.
- **Gemini gasta más tokens de salida** (792 frente a 242 de OpenAI) porque es un modelo de
  razonamiento: los tokens de razonamiento cuentan como salida aunque no se vean.
- **OpenAI es el más eficiente** en entrada y en salida, y sus respuestas son las más concisas. Para
  un asistente interno con muchas consultas pequeñas como estas, sería mi elección. Claude
  da las respuestas más explicativas, útiles si las lee un cliente final, pero más caras.
