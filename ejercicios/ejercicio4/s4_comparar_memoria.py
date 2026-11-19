"""Sesión 4 · P3. Preferencias por herramienta (P2) contra prompt dinámico (P3)."""
from s4_memoria_dinamica import agente as agente_dinamico
from s4_memoria_langchain import Contexto, agente as agente_herramienta, checkpointer, hilos_del_cliente, store

CLIENTE = "99"
N = 5
PREGUNTAS = ["Quiero el pedido de siempre. ¿Qué me traéis y qué día?",
             "Hola, ¿cuándo me llega el próximo pedido?"]


def probar(agente, hilo: str, pregunta: str) -> dict:
    estado = agente.invoke({"messages": [{"role": "user", "content": pregunta}]},
                           {"configurable": {"thread_id": hilo}}, context=Contexto(CLIENTE))
    ias = [m for m in estado["messages"] if m.type == "ai"]
    texto = estado["messages"][-1].text.lower()
    return {"llamadas": len(ias),
            "entrada": sum(m.usage_metadata["input_tokens"] for m in ias),
            "salida": sum(m.usage_metadata["output_tokens"] for m in ias),
            "acierta": "jueves" in texto or "blend" in texto,
            "llamo_ver": any(c["name"] == "ver_preferencias" for m in ias for c in m.tool_calls)}


if __name__ == "__main__":
    store.put(("clientes", CLIENTE), "horario_entrega", {"valor": "jueves por la mañana"})
    store.put(("clientes", CLIENTE), "producto_habitual", {"valor": "blend de hostelería"})
    try:
        print("Versión               acierta  llamó ver  llamadas  entrada  salida")
        for nombre, agente in [("P2 herramienta", agente_herramienta),
                               ("P3 prompt dinámico", agente_dinamico)]:
            rs = [probar(agente, f"{CLIENTE}-{nombre[:2]}-{q}-{i}", p)
                  for q, p in enumerate(PREGUNTAS) for i in range(N)]
            n = len(rs)
            print(f"{nombre:20} {sum(r['acierta'] for r in rs):5}/{n} {sum(r['llamo_ver'] for r in rs):7}/{n} "
                  f"{sum(r['llamadas'] for r in rs) / n:9.1f} {sum(r['entrada'] for r in rs) / n:8.0f} "
                  f"{sum(r['salida'] for r in rs) / n:7.0f}")
    finally:
        for item in store.search(("clientes", CLIENTE)):
            store.delete(("clientes", CLIENTE), item.key)
        for hilo in hilos_del_cliente(CLIENTE):
            checkpointer.delete_thread(hilo)
