"""Sesión 4 · P3. Fiabilidad y coste: memoria por herramienta (P2) vs prompt dinámico (P3).

Guarda unas preferencias para un cliente de prueba y abre N conversaciones nuevas con cada
versión. Mide si la respuesta usa las preferencias, cuántas llamadas al modelo hace y
cuántos tokens gasta. Al final borra todo lo del cliente de prueba.
Uso: python s4_comparar_memoria.py"""
from s4_memoria_dinamica import agente as agente_dinamico
from s4_memoria_langchain import Contexto, agente as agente_herramienta, checkpointer, hilos_del_cliente, store

CLIENTE = "99"  # cliente de prueba: no toca los datos de los clientes reales
PREFERENCIAS = {"horario_entrega": "jueves por la mañana", "producto_habitual": "blend de hostelería"}
N = 5
PREGUNTAS = [  # ninguna nombra la preferencia: hay que recordarla
    "Quiero el pedido de siempre. ¿Qué me traéis y qué día?",
    "Hola, ¿cuándo me llega el próximo pedido?",
]


def una_conversacion(agente, thread_id: str, pregunta: str) -> dict:
    estado = agente.invoke({"messages": [{"role": "user", "content": pregunta}]},
                           {"configurable": {"thread_id": thread_id}},
                           context=Contexto(cliente_id=CLIENTE))
    ias = [m for m in estado["messages"] if m.type == "ai"]
    texto = estado["messages"][-1].text.lower()
    return {
        "llamadas": len(ias),
        "entrada": sum(m.usage_metadata["input_tokens"] for m in ias if m.usage_metadata),
        "salida": sum(m.usage_metadata["output_tokens"] for m in ias if m.usage_metadata),
        "usa_dia": "jueves" in texto,
        "usa_producto": "blend" in texto,
        "llamo_ver": any(c["name"] == "ver_preferencias" for m in ias for c in m.tool_calls),
    }


if __name__ == "__main__":
    for clave, valor in PREFERENCIAS.items():
        store.put(("clientes", CLIENTE), clave, {"valor": valor})
    try:
        resultados = {}
        for nombre, agente in [("P2 · herramienta ver_preferencias", agente_herramienta),
                               ("P3 · prompt dinámico", agente_dinamico)]:
            filas = []
            for q, pregunta in enumerate(PREGUNTAS):
                for i in range(N):
                    r = una_conversacion(agente, f"{CLIENTE}-{nombre[:2]}-{q}-{i}", pregunta)
                    filas.append(r)
                    print(f"{nombre} · pregunta {q + 1} · intento {i + 1}: {r}")
            resultados[nombre] = filas

        print("\n" + "=" * 78)
        print(f"{'Versión':36} {'acierta':>8} {'llamó ver':>9} {'llamadas':>8} {'entrada':>8} {'salida':>7}")
        for nombre, filas in resultados.items():
            n = len(filas)
            acierta = sum(f["usa_dia"] or f["usa_producto"] for f in filas)
            print(f"{nombre:36} {acierta:>5}/{n} {sum(f['llamo_ver'] for f in filas):>6}/{n} "
                  f"{sum(f['llamadas'] for f in filas) / n:8.1f} "
                  f"{sum(f['entrada'] for f in filas) / n:8.0f} {sum(f['salida'] for f in filas) / n:7.0f}")
        print("(llamadas y tokens: media por conversación)")
    finally:  # limpieza: el cliente de prueba no deja rastro
        for item in store.search(("clientes", CLIENTE)):
            store.delete(("clientes", CLIENTE), item.key)
        for t in hilos_del_cliente(CLIENTE):
            checkpointer.delete_thread(t)
