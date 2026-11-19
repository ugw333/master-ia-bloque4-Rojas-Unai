"""Sesión 4 · P3. Las preferencias van en el prompt antes de cada llamada.

Uso:  python s4_memoria_dinamica.py <cliente_id> <hilo>"""
import sys

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, SummarizationMiddleware, dynamic_prompt

from s4_memoria_langchain import (MODELO, Contexto, checkpointer, olvidar_preferencias,
                                  recordar_preferencia, store)

SISTEMA = """Eres el asistente comercial de Tostadero Retiro.
Cuando el cliente exprese una preferencia estable, guárdala con recordar_preferencia.
Si pide que olvides sus datos, usa olvidar_preferencias y confírmalo."""


@dynamic_prompt
def con_preferencias(request: ModelRequest) -> str:
    cliente_id = request.runtime.context.cliente_id
    prefs = request.runtime.store.search(("clientes", cliente_id))
    if not prefs:
        return SISTEMA + "\n\nEste cliente no tiene preferencias guardadas."
    lineas = "\n".join(f"- {p.key}: {p.value['valor']}" for p in prefs)
    return SISTEMA + f"\n\nPreferencias guardadas de este cliente:\n{lineas}"


agente = create_agent(
    model=MODELO,
    tools=[recordar_preferencia, olvidar_preferencias],
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
            break
