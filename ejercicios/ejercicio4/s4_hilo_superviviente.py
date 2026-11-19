"""Sesión 4 · P2. ¿Qué pasa si el hilo actual se borra desde dentro de la herramienta?"""
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool

import s4_memoria_langchain as m


@tool
def olvidar_todo(runtime: ToolRuntime[m.Contexto]) -> str:
    """Borra todos los datos del cliente. Úsala si pide olvidar sus datos."""
    for hilo in m.hilos_del_cliente(runtime.context.cliente_id):
        m.checkpointer.delete_thread(hilo)
    print("   dentro de la herramienta, hilos del cliente 9:", sorted(m.hilos_del_cliente("9")))
    return "Datos eliminados."


agente = create_agent(model=m.MODELO, tools=[olvidar_todo], checkpointer=m.checkpointer,
                      context_schema=m.Contexto,
                      system_prompt="Si el cliente pide olvidar sus datos, usa olvidar_todo.")
config = {"configurable": {"thread_id": "9-prueba"}}
contexto = m.Contexto(cliente_id="9")

agente.invoke({"messages": [{"role": "user", "content": "Hola, prefiero entregas los lunes."}]},
              config, context=contexto)
print("antes del olvido:", sorted(m.hilos_del_cliente("9")))
agente.invoke({"messages": [{"role": "user", "content": "Olvidad mis datos."}]}, config, context=contexto)
mensajes = agente.get_state(config).values["messages"]
print("después de invoke:", sorted(m.hilos_del_cliente("9")), "· mensajes en el hilo:", len(mensajes))
print("mensajes que sobreviven:", [type(x).__name__ for x in mensajes])
m.checkpointer.delete_thread("9-prueba")
