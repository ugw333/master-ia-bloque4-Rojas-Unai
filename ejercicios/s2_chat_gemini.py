"""Sesión 2. Function calling con Gemini (Chat Completions vía OpenRouter)."""
import json
import os

import openai
from dotenv import load_dotenv

from herramientas import FUNCIONES, para_chat

load_dotenv()


cliente = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
)

SISTEMA = (
    "Eres el asistente interno de Tostadero Retiro. Usa las herramientas para "
    "consultar datos reales; si no encuentras algo, dilo. No inventes cifras."
)


def preguntar_gemini(pregunta: str, max_vueltas: int = 5) -> str:
    entrada: list = [
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content": pregunta}
    ]
    
    for vuelta in range(max_vueltas):
        r = cliente.chat.completions.create(
            model=os.environ.get("GEMINI_MODEL", "google/gemini-3.8-flash"),
            messages=entrada,
            tools=para_chat(),
        )


        usage = r.usage
        print(f"[Vuelta {vuelta + 1}] Tokens -> Prompt: {usage.prompt_tokens} | Completion: {usage.completion_tokens} | Total: {usage.total_tokens}")
        
        mensaje_respuesta = r.choices[0].message
        entrada.append(mensaje_respuesta)
        
        tool_calls = mensaje_respuesta.tool_calls
        if not tool_calls:

            return mensaje_respuesta.content
            
        for tool_call in tool_calls:
            nombre_funcion = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            if nombre_funcion in FUNCIONES:
                resultado = FUNCIONES[nombre_funcion](**args)
            else:
                resultado = f"Error: Función {nombre_funcion} no encontrada."
                
            print(f"  -> {nombre_funcion}({args}) = {str(resultado)[:80]}")
            
            entrada.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(resultado, ensure_ascii=False),
            })
            
    return "No he podido completar la consulta en el número de pasos permitido."


if __name__ == "__main__":
    print("=== Pregunta 1 ===")
    print(preguntar_gemini("¿Qué pedidos pendientes tiene el Bar La Esquina y cuánto suman?"))
    print("\n=== Pregunta 2 ===")
    print(preguntar_gemini("¿Cuánto stock queda de descafeinado?"))