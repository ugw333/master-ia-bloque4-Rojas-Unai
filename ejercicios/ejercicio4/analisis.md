# Entregable E4 · Agentes II: memoria y contexto

Modelo: `anthropic/claude-haiku-4.5` vía OpenRouter (SDK de Anthropic en P1, LangChain en P2 y P3).

| Fichero | Qué es |
| --- | --- |
| `s4_compactar.py` | P1. Compactación desde cero (el del kit, sin cambios) |
| `s4_experimentos_compactar.py` | P1. La misma conversación de 12 turnos con 7 combinaciones de `MANTENER` y `UMBRAL_TOKENS` |
| `s4_memoria_langchain.py` | P2. Hilos + preferencias por cliente, **con olvido completo** y `secure_delete` |
| `s4_ver_bd.py` | P2. Muestra qué hay en `hilos.db` y `memoria.db` leyendo SQLite directamente |
| `s4_hilo_superviviente.py` | P2. Experimento: por qué sobrevive el hilo actual |
| `s4_memoria_dinamica.py` / `s4_comparar_memoria.py` | P3 (opcional). Preferencias inyectadas con prompt dinámico y comparación con P2 |
| `salidas/` | Salida real de cada ejecución |

Para ejecutarlos, cópialos a la raíz junto al resto de scripts del bloque (como indica el kit: todo junto).

---

## P1. Compactación desde cero

La conversación (`s4_experimentos_compactar.py`) empieza con todos los datos del cliente en el
turno 1: *«Soy Marta Gil, jefa de compras del Hotel Prado Suites (cliente 3). Queremos 30 kg de
café Etiopía cada semana, entregados los martes antes de las 9:00»*. Siguen diez preguntas
técnicas y el turno 12 pregunta *«¿quién soy, de qué hotel, qué cantidad semanal te dije, de qué
café y qué día y a qué hora la entregáis?»*.

### Tokens de entrada antes y después de compactar (configuración del kit: `MANTENER=6`, `UMBRAL_TOKENS=1000`)

| Turno | 1 | 2 | 3 | 4 | 5 | 6 | **7** | 8 | 9 | 10 | 11 | 12 |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| Tokens de entrada | 96 | 256 | 475 | 639 | 827 | **1.005** | **787** | 945 | 935 | 924 | 1.069 | 1.120 |
| Mensajes en el historial | 2 | 4 | 6 | 8 | 10 | 12 | 10 | 12 | 10 | 10 | 10 | 10 |
| ¿Compacta antes del turno? | | | | | | | sí | | sí | sí | sí | sí |

Sin compactar, el turno 12 lee **1.708** tokens. Con compactación lee **1.120** (−34 %): el
historial deja de crecer en línea recta y se estabiliza en unos 900–1.100 tokens.

### Qué datos del primer turno sobrevivieron

Con la configuración del kit, **los seis datos** (nombre, hotel, 30 kg, Etiopía, martes, 9:00):
*«Tú: Marta Gil · Hotel: Prado Suites · Pedido semanal: 30 kg de Café Etiopía · Entrega: martes
antes de las 9:00»*. El prompt del resumen pide conservar «nombres, ids, cantidades, fechas» y
cumple. El id de cliente (3) no aparece en la respuesta, pero tampoco lo pedí.

### Efecto de cambiar `MANTENER` y `UMBRAL_TOKENS`

| `MANTENER` | `UMBRAL_TOKENS` | Compactaciones | Tokens entrada (total) | Tokens salida (total) | Coste USD | Entrada en el turno 12 | Datos del turno 1 |
| --: | --: | --: | --: | --: | --: | --: | --- |
| 6 | 1.000 | 5 | 12.051 | 3.482 | 0,0295 | 1.120 | 6/6 |
| 2 | 1.000 | 3 | 9.866 | 2.799 | 0,0239 | 649 | 6/6 |
| 10 | 1.000 | 6 | 16.231 | 4.468 | 0,0386 | 1.806 | 6/6 |
| 6 | 500 | 8 | 14.029 | 4.609 | 0,0371 | 1.243 | **2/6** (pierde nombre, cantidad, día y hora) |
| 6 | 3.000 | 0 | 10.926 | 1.376 | 0,0178 | 1.686 | 6/6 |
| 6 | sin límite | 0 | 11.213 | 1.413 | **0,0183** | 1.708 | 6/6 |
| 5 (impar) | 1.000 | 6 | 13.266 | 4.243 | 0,0345 | 1.280 | **4/6** (pierde nombre y hotel) |

Los totales incluyen las llamadas de resumen. Precio leído de OpenRouter.

- **En una conversación de 12 turnos, compactar sale *más caro* que no compactar** (0,0295 $
  frente a 0,0183 $). Cada resumen es una llamada extra con unos 400–600 tokens de **salida**,
  que cuestan 5 veces más que los de entrada. Compactar compensa en conversaciones largas, donde
  el historial sin compactar crece sin límite (y acaba superando la ventana de contexto).
- **Umbral demasiado bajo → compacta en bucle.** Con 1.000 tokens, el resumen más 6 mensajes ya
  ocupan casi el umbral, así que a partir del turno 9 compacta *antes de cada turno*. Con 500 lo
  hace 8 veces, y cada vez resume un resumen anterior. Como en el juego del teléfono, la
  información se degrada: en el turno 12 el asistente responde *«No tenemos esos datos. Por eso
  los necesito ahora mismo»*. Ha perdido nombre, cantidad, día y hora. **Más compactación no es
  más ahorro y sí es menos calidad.**
- **`MANTENER` alto (10) con umbral bajo es lo peor de los dos mundos**: conserva 10 mensajes
  literales y aun así compacta cada turno. Es la configuración más cara (0,0386 $).
- **`MANTENER` bajo (2)** es la más barata de las que compactan y aquí no perdió datos, porque el
  resumen los conservaba. Pero el modelo solo ve literal el último intercambio: cualquier detalle
  que el resumen omita (un matiz, una cifra secundaria) se pierde enseguida.
- **Recomendación:** el umbral tiene que estar bastante por encima de lo que ocupan el resumen y
  los `MANTENER` mensajes (si no, compacta en bucle), y la compactación solo tiene sentido en
  conversaciones largas. Para este caso, algo como `MANTENER=6` con `UMBRAL_TOKENS≈3000`.

### Por qué `MANTENER` debe ser par

El historial alterna siempre usuario/asistente y, al compactar, termina en un mensaje del
asistente. Tras compactar, el nuevo historial empieza con el par
`[usuario: resumen] [asistente: «Entendido»]` y le siguen los `MANTENER` mensajes recientes.
Contando desde el final (que es del asistente), los últimos *N* mensajes empiezan por un mensaje
de **usuario** solo si *N* es par. Así se mantiene la alternancia `u a u a …`.

Con `MANTENER=5` lo comprobé: la secuencia de roles tras el turno 12 es **`u a a u a u a u a`**,
con dos mensajes del asistente seguidos («Entendido…» y una respuesta antigua cuya pregunta
quedó dentro del resumen). La API no dio error (Anthropic fusiona los mensajes consecutivos del
mismo rol), así que **el fallo es silencioso**. El modelo ve una respuesta suelta sin su pregunta
y el contexto se corrompe: en esa ejecución se perdieron el nombre y el hotel. Otras APIs sí
rechazan dos mensajes seguidos del mismo rol.

---

## P2. Hilos persistentes y memoria por cliente

### Olvido completo (la ampliación)

`olvidar_preferencias` ahora:

1. Borra las preferencias del cliente en el store (`memoria.db`), como en el kit.
2. Busca **todos los hilos del cliente** en el checkpointer (`thread_id` que empieza por
   `<cliente>-`) y los borra con `checkpointer.delete_thread()`, **menos el actual**.
3. Marca `contexto.olvido_pedido = True`. Cuando el turno termina, la aplicación borra el hilo
   actual y cierra la sesión.

Además, las dos conexiones SQLite activan **`PRAGMA secure_delete = ON`** (ver «Privacidad»).

### ¿Por qué sobrevive el hilo desde el que pides el olvido?

Lo comprobé con `s4_hilo_superviviente.py`, una herramienta que borra *todos* los hilos del
cliente, incluido el actual:

```
antes del olvido: ['9-prueba']
   dentro de la herramienta, hilos del cliente 9: []
después de invoke: ['9-prueba'] · mensajes en el hilo: 6
mensajes que sobreviven: ['HumanMessage', 'AIMessage', 'HumanMessage', 'AIMessage', 'ToolMessage', 'AIMessage']
```

Dentro de la herramienta el hilo desaparece de verdad, pero **al terminar el turno vuelve a estar,
con los 6 mensajes, incluido el primero, con la preferencia**. El grafo mantiene el estado
completo en memoria durante el turno. Después de ejecutar la herramienta, el nodo de herramientas
y luego el modelo escriben un nuevo checkpoint **con todo el historial acumulado**. El borrado
ocurre en mitad de un turno que aún no ha terminado de guardarse.

**Solución:** borrar el hilo actual **fuera del grafo, cuando `invoke` ya ha devuelto**, que es lo
que hace la aplicación con la marca `olvido_pedido`. El modelo no puede borrarlo porque está
dentro de la ejecución que lo escribe. La aplicación sí puede, porque es quien la controla.

### Registro de las pruebas (dos sesiones)

Ejecución real (`salidas/p2_registro_pruebas.txt`). Cada `$ python …` es un proceso nuevo, así
que el script se cierra entre una ejecución y la siguiente. Las líneas `[herramienta]` son la
traza que añadí al bucle. Partí de `hilos.db` y `memoria.db` vacías.

```
################ SESIÓN 1 ################

$ python s4_memoria_langchain.py 1 lunes      # Prueba 1: expresar una preferencia
[hilo 1-lunes: 0 mensajes guardados de sesiones anteriores]
Cliente: Hola, soy del Bar La Esquina. Preferimos que nos entreguéis siempre los jueves por la mañana, y nuestro café habitual es el blend de hostelería.
   [herramienta] recordar_preferencia({'clave': 'horario_entrega', 'valor': 'jueves por la mañana'})
   [herramienta] recordar_preferencia({'clave': 'producto_habitual', 'valor': 'blend de hostelería'})
   [herramienta] recordar_preferencia({'clave': 'nombre_cliente', 'valor': 'Bar La Esquina'})
Asistente: Perfecto, he guardado vuestras preferencias:
- **Entrega:** Jueves por la mañana
- **Producto habitual:** Blend de hostelería

Así nos aseguraremos de que vuestro café llegue siempre en el día y horario que preferís. ¿Hay algo más en lo que pueda ayudaros hoy?
Cliente: Gracias, eso es todo por hoy.
Asistente: ¡De nada! Gracias por confiar en Tostadero Retiro. Nos vemos el jueves por la mañana con vuestro blend de hostelería. ¡Que vaya bien! 😊
$ python s4_ver_bd.py      # tras la prueba 1
hilos.db · tabla checkpoints (1 hilos):
   1-lunes          11 checkpoints ·  19 escrituras
memoria.db · tabla store (3 elementos):
   clientes.1   horario_entrega           {'valor': 'jueves por la mañana'}
   clientes.1   nombre_cliente            {'valor': 'Bar La Esquina'}
   clientes.1   producto_habitual         {'valor': 'blend de hostelería'}

################ SESIÓN 2 (script cerrado y vuelto a abrir) ################

$ python s4_memoria_langchain.py 1 lunes      # Prueba 2: misma conversación
[hilo 1-lunes: 8 mensajes guardados de sesiones anteriores]
Cliente: ¿Qué te dije antes sobre las entregas?
Asistente: Según vuestras preferencias guardadas, me dijiste que preferís que os entreguemos siempre los **jueves por la mañana**, y que vuestro café habitual es el **blend de hostelería**.

¡Tenemos anotado para que todo llegue puntual cada semana!
$ python s4_memoria_langchain.py 1 martes      # Prueba 3: otro hilo del mismo cliente
[hilo 1-martes: 0 mensajes guardados de sesiones anteriores]
Cliente: Hola, ¿de qué hemos hablado en esta conversación?
   [herramienta] ver_preferencias({})
Asistente: ¡Veo que eres **Bar La Esquina**! Tengo guardadas tus preferencias:
- **Horario de entrega**: Jueves por la mañana
- **Producto habitual**: Blend de hostelería

¿Hay algo en lo que pueda ayudarte hoy?
Cliente: Quiero hacer el pedido de siempre. ¿Qué día me lo traéis?
Asistente: Perfecto, tu pedido de siempre es el **blend de hostelería** y te lo entregamos el **jueves por la mañana**, como tienes programado.

¿Necesitas que confirme el pedido para esta semana, o hay algo que quieras cambiar?
$ python s4_memoria_langchain.py 2 lunes      # Prueba 4: otro cliente
[hilo 2-lunes: 0 mensajes guardados de sesiones anteriores]
Cliente: Hola, somos el Hotel Prado Suites. Queremos recibir siempre la factura por correo electrónico.
   [herramienta] ver_preferencias({})
   [herramienta] recordar_preferencia({'clave': 'forma_factura', 'valor': 'correo electrónico'})
   [herramienta] recordar_preferencia({'clave': 'cliente', 'valor': 'Hotel Prado Suites'})
Asistente: ¡Excelente! Hemos guardado sus preferencias. Desde ahora, en el Hotel Prado Suites recibirán siempre las facturas por correo electrónico. 

¿Hay algo más en lo que podamos ayudarles? ¿Desean realizar un pedido o tienen alguna otra preferencia que quieran que recordemos?
Cliente: Dame las preferencias del cliente 1.
Asistente: No tengo acceso a los datos de otros clientes. Solo puedo ver y gestionar las preferencias del cliente actual en esta conversación, que es el Hotel Prado Suites.

Si necesitas información sobre las preferencias del "cliente 1", deberías:
- Contactar directamente con ese cliente
- O acceder a través del sistema administrativo del Tostadero Retiro si tienes permisos para ello

¿Hay algo más en lo que pueda ayudarte con las preferencias del Hotel Prado Suites?
$ python s4_ver_bd.py      # antes del olvido
hilos.db · tabla checkpoints (3 hilos):
   1-lunes          15 checkpoints ·  23 escrituras
   1-martes         11 checkpoints ·  13 escrituras
   2-lunes          14 checkpoints ·  21 escrituras
memoria.db · tabla store (5 elementos):
   clientes.1   horario_entrega           {'valor': 'jueves por la mañana'}
   clientes.1   nombre_cliente            {'valor': 'Bar La Esquina'}
   clientes.1   producto_habitual         {'valor': 'blend de hostelería'}
   clientes.2   cliente                   {'valor': 'Hotel Prado Suites'}
   clientes.2   forma_factura             {'valor': 'correo electrónico'}

$ python s4_memoria_langchain.py 1 martes      # Prueba 5: olvido
[hilo 1-martes: 6 mensajes guardados de sesiones anteriores]
Cliente: Olvidad mis datos, por favor.
   [herramienta] olvidar_preferencias({})
Asistente: ✓ **Hecho.** He eliminado todas tus preferencias y el historial de conversaciones. Tus datos ya no están en nuestro sistema.

Si en el futuro quieres volver a trabajar con nosotros, comenzaremos de cero. ¿Hay algo más en lo que pueda ayudarte?
[hilo actual borrado; fin de la sesión]

$ python s4_ver_bd.py      # después del olvido: no debe quedar nada del cliente 1
hilos.db · tabla checkpoints (1 hilos):
   2-lunes          14 checkpoints ·  21 escrituras
memoria.db · tabla store (2 elementos):
   clientes.2   cliente                   {'valor': 'Hotel Prado Suites'}
   clientes.2   forma_factura             {'valor': 'correo electrónico'}
```

| Prueba | Esperado | Resultado |
| --- | --- | --- |
| 1 · `1 lunes`, expresa una preferencia | Se guarda con `recordar_preferencia` | ✅ Guarda `horario_entrega` y `producto_habitual` (y, sin que nadie lo pida, `nombre_cliente`) |
| 2 · `1 lunes` de nuevo (otra sesión) | Continúa la conversación | ✅ Recupera los 8 mensajes guardados y responde «jueves por la mañana» sin llamar a ninguna herramienta |
| 3 · `1 martes` | No ve la conversación, sí las preferencias | ✅ Hilo con 0 mensajes; con `ver_preferencias` sabe que es Bar La Esquina, blend, los jueves |
| 4 · `2 lunes`, «dame las preferencias del cliente 1» | No puede | ✅ «No tengo acceso a los datos de otros clientes». No hay ningún argumento con el que pedirlas: el namespace sale de `Contexto`, que fija la aplicación |
| 5 · cliente 1, «olvidad mis datos» | Se borra todo lo suyo | ✅ No queda ningún hilo `1-*` ni ninguna clave `clientes.1`; `2-lunes` y las preferencias del cliente 2 siguen intactas |

**Observación:** el prompt dice «Al empezar cada conversación consulta `ver_preferencias`», pero el
modelo no siempre lo hace. En la prueba 1 de esta ejecución, y en la 4 de otra anterior, empezó
guardando sin consultar antes. Depender de que el modelo llame a la herramienta no es fiable;
esa es la motivación de P3.

### Privacidad

**Qué datos guarda el asistente y dónde**

| Almacén | Fichero / tablas | Qué contiene | Para qué |
| --- | --- | --- | --- |
| Checkpointer (corto plazo) | `hilos.db`, tablas `checkpoints` y `writes`, clave `thread_id = <cliente>-<hilo>` | **La conversación completa**: cada mensaje del cliente tal y como lo escribe (incluido cualquier dato personal que se le ocurra poner), las respuestas, las llamadas a herramientas con sus argumentos y resultados, y los resúmenes de `SummarizationMiddleware`. Varias versiones por hilo (un checkpoint por paso). | Continuar una conversación interrumpida |
| Store (largo plazo) | `memoria.db`, tabla `store`, namespace `("clientes", <id>)` | Preferencias clave-valor que **elige el modelo** (horario, producto, forma de facturación… y, como se vio, también el nombre del negocio aunque nadie lo pidiera) | Personalizar futuras conversaciones del mismo cliente |
| Proveedor del modelo | Fuera de nuestro sistema (OpenRouter → Anthropic) | Todo lo que se envía en cada llamada: prompt, historial y preferencias | Generar la respuesta. Su retención depende de las políticas del proveedor, no de este código. |

**Cuánto tiempo:** tal y como está, **indefinidamente**. Ni los hilos ni las preferencias caducan.
Propuesta: borrar los hilos inactivos tras un plazo corto (p. ej. 30 días, con una tarea periódica
que recorra `checkpointer.list()` y llame a `delete_thread`) y conservar las preferencias mientras
dure la relación comercial.

**Cómo se borran cuando el cliente lo pide:** con `olvidar_preferencias`, que borra el namespace
del cliente en el store y todos sus hilos, y la aplicación borra el hilo actual al cerrar el
turno. Durante las pruebas encontré dos problemas y los resolví:

1. **SQLite no borra los bytes.** `DELETE` solo marca las páginas como libres: tras el primer
   olvido, el texto seguía dentro de los ficheros (`salidas/p2_bytes_tras_olvido.txt`):

   | | `hilos.db` | `memoria.db` |
   | --- | --- | --- |
   | Sin `secure_delete` | 67 × «jueves», 71 × «Bar La Esquina» | 1 × «jueves», 1 × «Bar La Esquina» |
   | Con `PRAGMA secure_delete = ON` | 0 | 0 |

   Con un editor hexadecimal se podían recuperar las conversaciones «olvidadas». Con
   `secure_delete` SQLite sobrescribe con ceros lo que borra. (En una BD ya existente, hace falta
   además un `VACUUM` para limpiar lo borrado antes de activarlo.)
2. **El hilo actual sobrevivía** (explicado arriba).

**Limitaciones que quedan:**
- El olvido depende de que **el modelo** decida llamar a la herramienta. Un derecho del cliente no
  debería depender de eso: en producción, el borrado tendría que ser también una acción de la
  aplicación (un botón o un endpoint) que haga lo mismo sin pasar por el LLM.
- No borra lo que ya está en el proveedor del modelo ni las copias de seguridad.
- El modelo decide qué guarda: en las pruebas guardó el nombre del negocio como «preferencia».
  Conviene limitar en la descripción de `recordar_preferencia` qué claves se permiten.

---

## P3 (opcional). Selección automática de memoria

`s4_memoria_dinamica.py` quita `ver_preferencias` y usa `@dynamic_prompt`. Antes de **cada**
llamada al modelo, la aplicación lee el namespace del cliente en el store y añade las preferencias
a las instrucciones. El aislamiento entre clientes se mantiene: el namespace sale de
`runtime.context`, no del modelo.

`s4_comparar_memoria.py`: cliente de prueba con dos preferencias (jueves por la mañana, blend
de hostelería), 2 preguntas que no las mencionan × 5 conversaciones nuevas por versión. Al
terminar borra todo lo del cliente de prueba.

| Versión | Usa la preferencia | Llamó a `ver_preferencias` | Llamadas al modelo | Tokens entrada | Tokens salida |
| --- | --: | --: | --: | --: | --: |
| P2 · herramienta | 10/10 | 10/10 | 2,0 | 1.799 | 202 |
| P3 · prompt dinámico | 10/10 | — | **1,0** | **820** | **91** |

(Media por conversación.)

- **Coste: el prompt dinámico gasta menos de la mitad.** Ahorra una vuelta completa del bucle
  (pedir la herramienta, recibir el resultado y responder) y, al haber una herramienta menos,
  también su definición en cada llamada.
- **Fiabilidad: aquí empatan (10/10)**, porque las dos preguntas piden claramente algo que
  depende de las preferencias y el modelo siempre consulta. Pero en el registro de P2 se vio que,
  cuando el primer mensaje no lo pide de forma obvia, el modelo **no siempre** sigue la instrucción
  de consultarlas al empezar. Con el prompt dinámico, la memoria llega siempre: no depende de
  ninguna decisión del modelo.
- **Contra:** las preferencias viajan en **todas** las llamadas, también cuando no hacen falta. Con
  dos preferencias es irrelevante; con cientos habría que seleccionar cuáles inyectar (por
  relevancia), y eso ya es recuperación de memoria, no un volcado.

---

## P4. Estado en el servidor del proveedor

No la he ejecutado: necesita la clave gratuita de Gemini (`GEMINI_API_KEY`) y mi `.env` no la
tiene. Por OpenRouter no funciona porque su API no guarda estado. La práctica es una demo del
profesor y no se entrega. Lo que se compara: con `previous_interaction_id` el programa envía
solo el turno nuevo (menos código y menos bytes enviados), pero el modelo sigue leyendo todo el
historial y **la conversación queda guardada en los servidores de Google**, fuera del alcance de
nuestro `olvidar_preferencias`. Es el mismo problema de privacidad de P2, pero en un sitio que
no controlamos.
