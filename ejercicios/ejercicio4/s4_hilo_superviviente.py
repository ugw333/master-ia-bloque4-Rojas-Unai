"""¿Por qué sobrevive el hilo actual si se borra desde dentro de la herramienta?"""
import sys
sys.path.insert(0, ".")
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
import s4_memoria_langchain as m

@tool
def olvidar_todo(runtime: ToolRuntime[m.Contexto]) -> str:
    """Borra todos los datos del cliente, incluido el hilo actual. Úsala si pide olvidar sus datos."""
    for t in m.hilos_del_cliente(runtime.context.cliente_id):  # SIN excluir el actual
        m.checkpointer.delete_thread(t)
    print(f"   dentro de la herramienta, hilos del cliente 9: {sorted(m.hilos_del_cliente('9'))}")
    return "Datos eliminados."

agente = create_agent(model=m.MODELO, tools=[olvidar_todo], checkpointer=m.checkpointer,
                      context_schema=m.Contexto,
                      system_prompt="Si el cliente pide olvidar sus datos, usa olvidar_todo.")
cfg = {"configurable": {"thread_id": "9-prueba"}}
ctx = m.Contexto(cliente_id="9")
agente.invoke({"messages": [{"role": "user", "content": "Hola, prefiero entregas los lunes."}]}, cfg, context=ctx)
print("antes del olvido:", sorted(m.hilos_del_cliente("9")))
estado = agente.invoke({"messages": [{"role": "user", "content": "Olvidad mis datos."}]}, cfg, context=ctx)
print("después de invoke:", sorted(m.hilos_del_cliente("9")),
      "· mensajes en el hilo:", len(agente.get_state(cfg).values.get("messages", [])))
print("mensajes que sobreviven:", [type(x).__name__ for x in agente.get_state(cfg).values["messages"]])
m.checkpointer.delete_thread("9-prueba")
