"""Sesión 4 · P1. La misma conversación con distintos MANTENER y UMBRAL_TOKENS."""
import s4_compactar as sc

TURNOS = [
    "Hola, soy Marta Gil, jefa de compras del Hotel Prado Suites (cliente 3). Queremos 30 kg "
    "de café Etiopía cada semana, entregados los martes antes de las 9:00.",
    "¿Qué diferencia hay entre vuestro Etiopía y el blend de hostelería?",
    "¿Y el descafeinado es de especialidad?",
    "Para el desayuno usamos una cafetera de dos grupos. ¿Nos aguanta 300 cafés diarios?",
    "¿Qué molino recomendáis para ese volumen?",
    "¿Hacéis formación de baristas para nuestro personal?",
    "¿Qué temperatura de agua recomendáis para el Etiopía en espresso?",
    "¿Cómo debemos guardar el café en grano para que no pierda aroma?",
    "¿Cada cuánto hay que limpiar los grupos de la cafetera?",
    "¿Tenéis alguna opción de café ecológico?",
    "Perfecto. Por cierto, ¿podéis enviar las facturas por correo electrónico?",
    "Recuérdame, por favor: ¿quién soy, de qué hotel, qué cantidad semanal te dije, de qué café "
    "y qué día y a qué hora la entregáis?",
]
DATOS = {"nombre": ["marta"], "hotel": ["prado"], "cantidad": ["30"],
         "café": ["etiopía", "etiopia"], "día": ["martes"], "hora": ["9:00", "9 h", "las 9"]}
PRUEBAS = [(6, 1000), (2, 1000), (10, 1000), (6, 500), (6, 3000), (6, 10**9), (5, 1000)]
PRECIO = (1.0, 5.0)  # claude-haiku-4.5 en OpenRouter, USD por millón (entrada, salida)

uso = {"entrada": 0, "salida": 0}
crear = sc.llm.messages.create


def crear_contando(**kw):
    r = crear(**kw)
    uso["entrada"] += r.usage.input_tokens
    uso["salida"] += r.usage.output_tokens
    return r


sc.llm.messages.create = crear_contando


def conversar(mantener: int, umbral: int):
    sc.MANTENER, sc.UMBRAL_TOKENS = mantener, umbral
    uso["entrada"] = uso["salida"] = 0
    historial, tokens, compactaciones = [], 0, 0
    for n, texto in enumerate(TURNOS, 1):
        if len(historial) > mantener and tokens > umbral:
            historial = sc.compactar(historial)
            compactaciones += 1
            print("   (historial compactado)")
        historial.append({"role": "user", "content": texto})
        r = sc.llm.messages.create(model=sc.MODELO, max_tokens=800, system=sc.SISTEMA,
                                   messages=historial)
        tokens = r.usage.input_tokens + r.usage.output_tokens
        respuesta = "".join(b.text for b in r.content if b.type == "text")
        historial.append({"role": "assistant", "content": respuesta})
        print(f"  turno {n:2}: {r.usage.input_tokens:5} tokens de entrada · {len(historial)} mensajes")
    print("  roles:", "".join(m["role"][0] for m in historial))
    print(f"\n  Respuesta al turno 12:\n  {respuesta}\n")
    perdidos = [k for k, vs in DATOS.items() if not any(v in respuesta.lower() for v in vs)]
    return compactaciones, tokens, perdidos


if __name__ == "__main__":
    tabla = []
    for mantener, umbral in PRUEBAS:
        print(f"\n=== MANTENER={mantener} · UMBRAL_TOKENS={umbral}")
        compactaciones, tokens, perdidos = conversar(mantener, umbral)
        usd = (uso["entrada"] * PRECIO[0] + uso["salida"] * PRECIO[1]) / 1e6
        tabla.append((mantener, umbral, compactaciones, uso["entrada"], uso["salida"], usd, perdidos))

    print("\nMANTENER  UMBRAL  compact.  entrada  salida     USD  datos perdidos")
    for mantener, umbral, c, ent, sal, usd, perdidos in tabla:
        print(f"{mantener:8} {umbral:7} {c:9} {ent:8} {sal:7} {usd:7.4f}  {', '.join(perdidos) or '-'}")
