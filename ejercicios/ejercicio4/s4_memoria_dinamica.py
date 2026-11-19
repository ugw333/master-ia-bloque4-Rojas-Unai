"""Sesión 4 · P3 (opcional). Selección automática de memoria con prompt dinámico.

En P2 el modelo tiene que acordarse de llamar a ver_preferencias. Aquí la aplicación lee
el store antes de CADA llamada al modelo y mete las preferencias en las instrucciones.
Mismos almacenes, contexto y herramientas de escritura que s4_memoria_langchain.py.

Uso:  python s4_memoria_dinamica.py <cliente_id> <hilo>"""
import sys

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, SummarizationMiddleware, dynamic_prompt

from s4_memoria_langchain import (MODELO, Contexto, checkpointer, olvidar_preferencias,
                                  recordar_preferencia, store)

SISTEMA_BASE = """Eres el asistente comercial de Tostadero Retiro.
Cuando el cliente exprese una preferencia estable, guárdala con recordar_preferencia.
Si pide que olvides sus datos, usa olvidar_preferencias y confírmalo."""


@dynamic_prompt
def con_preferencias(request: ModelRequest) -> str:
    cliente_id = request.runtime.context.cliente_id  # el namespace sigue fijándolo la aplicación
    prefs = {i.key: i.value["valor"] for i in request.runtime.store.search(("clientes", cliente_id))}
    if not prefs:
        return SISTEMA_BASE + "\n\nEste cliente no tiene preferencias guardadas."
    lineas = "\n".join(f"- {clave}: {valor}" for clave, valor in prefs.items())
    return SISTEMA_BASE + f"\n\nPreferencias guardadas de este cliente (tenlas en cuenta):\n{lineas}"


agente = create_agent(
    model=MODELO,
    tools=[recordar_preferencia, olvidar_preferencias],  # ver_preferencias ya no hace falta
    context_schema=Contexto,
    checkpointer=checkpointer,
    store=store,
    middleware=[con_preferencias,
                SummarizationMiddleware(model=MODELO, trigger=("tokens", 3000),
                                        keep=("messages", 10))],
)

if __name__ == "__main__":
    cliente_id, hilo = sys.argv[1], sys.argv[2]
    config = {"configurable": {"thread_id": f"{cliente_id}-{hilo}"}}
    contexto = Contexto(cliente_id=cliente_id)
    while texto := input("Cliente: ").strip():
        estado = agente.invoke({"messages": [{"role": "user", "content": texto}]},
                               config, context=contexto)
        print("Asistente:", estado["messages"][-1].text)
        if contexto.olvido_pedido:
            checkpointer.delete_thread(config["configurable"]["thread_id"])
            print("[hilo actual borrado; fin de la sesión]")
            break
