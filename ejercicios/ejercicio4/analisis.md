# E4 · Memoria y contexto

## P1. Compactación

Hice una conversación de 12 turnos. En el primero di todos los datos (Marta Gil, Hotel Prado Suites, 30 kg de Etiopía, martes antes de las 9:00) y en el último le pregunté por ellos.

Con la configuración del kit (`MANTENER=6`, `UMBRAL_TOKENS=1000`) los tokens de entrada suben hasta 1.005 en el turno 6, bajan a 787 al compactar y se quedan en unos 900-1.100. Sin compactar, el turno 12 llega a 1.708. Los seis datos del primer turno sobrevivieron.

Probando otros valores (salida completa en `salidas/p1_compactacion.txt`):

- **Umbral 500:** compacta 8 veces y cada vez resume el resumen anterior. Al final perdió el nombre, la cantidad, el día y la hora.
- **Umbral 3000:** no llega a compactar y es lo más barato.
- **MANTENER 10:** compacta en todos los turnos y es lo más caro.
- **MANTENER 2:** barato y no perdió nada, pero el modelo solo ve literal el último intercambio.

Lo que más me sorprendió: en una conversación corta compactar sale más caro (0,030 $ frente a 0,018 $), porque cada resumen es una llamada extra con bastante salida. Solo compensa en conversaciones largas, y con el umbral bien por encima de lo que ocupan el resumen y los mensajes que se guardan.

**Por qué MANTENER tiene que ser par:** después de compactar, el historial empieza por el par resumen (usuario) + «Entendido» (asistente). Lo que viene detrás tiene que empezar por usuario, y como el historial termina siempre en asistente, eso solo pasa si cojo un número par de mensajes. Lo probé con 5: quedaron dos mensajes del asistente seguidos. La API no dio error, pero el modelo perdió el nombre y el hotel.

## P2. Hilos y memoria por cliente

Las cinco pruebas salieron como se esperaba. El registro completo de las dos sesiones está en `salidas/p2_registro_pruebas.txt`:

1. `1 lunes`: guardó «jueves por la mañana» y «blend de hostelería».
2. `1 lunes` otra vez: recordó la conversación.
3. `1 martes`: conversación nueva, pero sabía las preferencias.
4. `2 lunes` pidiendo los datos del cliente 1: «No tengo acceso a los datos de otros clientes».
5. «Olvidad mis datos»: no queda nada del cliente 1 y el cliente 2 sigue intacto.

Para el olvido completo, `olvidar_preferencias` borra también los hilos del cliente con `delete_thread`. El hilo desde el que pides el olvido sobrevive porque LangChain lo vuelve a guardar al acabar el turno, con todos los mensajes (lo comprobé en `salidas/p2_hilo_superviviente.txt`). Lo resolví marcándolo y borrándolo desde la aplicación cuando `invoke` ya ha terminado.

## Privacidad

- **`hilos.db`:** la conversación entera de cada hilo, con todo lo que escriba el cliente. Sirve para retomar conversaciones.
- **`memoria.db`:** las preferencias de cada cliente, separadas por su id. Sirven para personalizar. Ojo: el modelo también guardó el nombre del negocio sin que nadie se lo pidiera.
- **Proveedor del modelo:** todo lo que se envía pasa por OpenRouter y Anthropic, y eso no lo controlamos.
- **Cuánto tiempo:** ahora mismo, para siempre. Lo razonable sería borrar los hilos al mes y guardar las preferencias mientras sea cliente.
- **Cómo se borra:** con «olvidad mis datos». Encontré un problema: SQLite no borra los bytes, y tras el olvido seguía apareciendo «Bar La Esquina» 71 veces dentro de `hilos.db`. Con `PRAGMA secure_delete = ON` quedan 0.
- **Lo que falta:** el borrado depende de que el modelo llame a la herramienta. En un caso real tendría que haber también un botón que lo haga sin pasar por el modelo.

## P3 (opcional)

Metí las preferencias en el prompt antes de cada llamada en vez de esperar a que el modelo llame a `ver_preferencias`. Las dos versiones acertaron 10 de 10, pero la nueva hace una llamada en vez de dos y gasta menos de la mitad de tokens (820 frente a 1.799). Además, no depende de que el modelo se acuerde de consultar.
