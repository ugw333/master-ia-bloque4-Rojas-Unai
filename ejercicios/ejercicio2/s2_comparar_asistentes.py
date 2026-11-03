"""Sesión 2 · P4. Compara el asistente con herramientas en OpenAI, Claude y Gemini.

Las cuatro preguntas de P3 en los tres proveedores; imprime la traza y la tabla de P4."""
from s2_chat_claude import preguntar_claude
from s2_chat_gemini import preguntar_gemini
from s2_chat_herramientas import PREGUNTAS, nuevas_metricas, preguntar

PROVEEDORES = [("OpenAI", preguntar), ("Claude", preguntar_claude), ("Gemini", preguntar_gemini)]

if __name__ == "__main__":
    filas = []
    for i, pregunta in enumerate(PREGUNTAS, 1):
        for nombre, fn in PROVEEDORES:
            print(f"\n=== P{i} · {nombre}: {pregunta}")
            m = nuevas_metricas()
            print(f"RESPUESTA: {fn(pregunta, metricas=m)}")
            filas.append((i, nombre, m))

    print("\n" + "=" * 78)
    print(f"{'Preg.':5} {'Proveedor':9} {'vueltas':>7} {'herram.':>7} {'tok entrada':>11} "
          f"{'tok salida':>10}  herramientas llamadas")
    for i, nombre, m in filas:
        print(f"P{i:<4} {nombre:9} {m['vueltas']:7} {len(m['herramientas']):7} "
              f"{m['tokens_entrada']:11} {m['tokens_salida']:10}  {' → '.join(m['herramientas'])}")
    print("\nTotales:")
    for nombre, _ in PROVEEDORES:
        ms = [m for _, n, m in filas if n == nombre]
        print(f"  {nombre:7} {sum(len(m['herramientas']) for m in ms):3} herramientas · "
              f"{sum(m['tokens_entrada'] for m in ms):6} tokens entrada · "
              f"{sum(m['tokens_salida'] for m in ms):5} tokens salida")
