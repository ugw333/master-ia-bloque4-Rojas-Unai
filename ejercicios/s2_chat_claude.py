"""Sesión 2. Function calling con Claude (Anthropic Messages API)."""
import json
import os

import anthropic
from dotenv import load_dotenv

from herramientas import FUNCIONES, para_claude

load_dotenv()
cliente = anthropic.Anthropic()

SISTEMA = (
    "Eres el asistente interno de Tostadero Retiro. Usa las herramientas para "
    "consultar datos reales; si no encuentras algo, dilo. No inventes cifras."
)


def preguntar_claude(pregunta: str, max_vueltas: int = 5) -> str:
    mensajes: list = [{"role": "user", "content": pregunta}]
    
    for vuelta in range(max_vueltas):
        r = cliente.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-3-5-haiku-20241022"),
            max_tokens=1024,
            system=SISTEMA,
            tools=para_claude(),
            messages=mensajes,
        )
        

        usage = r.usage
        print(f"[Vuelta {vuelta + 1}] Tokens -> Input: {usage.input_tokens} | Output: {usage.output_tokens}")

        mensajes.append({"role": "assistant", "content": r.content})
        
        tool_uses = [block for block in r.content if block.type == "tool_use"]
        
        if not tool_uses:
            # Sin llamadas pendientes: extraer y retornar el texto de la respuesta final
            textos = [block.text for block in r.content if block.type == "text"]
            return "".join(textos)
            
        tool_results = []
        for tool_use in tool_uses:
            nombre_funcion = tool_use.name
            args = tool_use.input
            
            if nombre_funcion in FUNCIONES:
                resultado = FUNCIONES[nombre_funcion](**args)
            else:
                resultado = f"Error: Función {nombre_funcion} no encontrada."
                
            print(f"  -> {nombre_funcion}({args}) = {str(resultado)[:80]}")
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(resultado, ensure_ascii=False),
            })
            
        mensajes.append({
            "role": "user",
            "content": tool_results,
        })
        
    return "No he podido completar la consulta en el número de pasos permitido."


if __name__ == "__main__":
    print("=== Pregunta 1 ===")
    print(preguntar_claude("¿Qué pedidos pendientes tiene el Bar La Esquina y cuánto suman?"))
    print("\n=== Pregunta 2 ===")
    print(preguntar_claude("¿Cuánto stock queda de descafeinado?"))