"""Sesión 4 · P1. La misma conversación de 12 turnos con distintos MANTENER y UMBRAL_TOKENS.

Reproduce el bucle de s4_compactar.py (sin input()) y mide, por configuración:
tokens de entrada de cada turno, compactaciones, coste total (incluido el resumen)
y si los datos del primer turno sobreviven. Uso: python s4_experimentos_compactar.py"""
import json
import urllib.request

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
# Datos del primer turno que deberían sobrevivir hasta la última respuesta
DATOS_TURNO_1 = {"nombre": ["Marta"], "hotel": ["Prado"], "cantidad": ["30"],
                 "café": ["Etiopía", "Etiopia"], "día": ["martes"], "hora": ["9:00", "9 h", "las 9"]}

CONFIGURACIONES = [  # (MANTENER, UMBRAL_TOKENS)
    (6, 1000),          # la del kit
    (2, 1000),          # mantener muy poco
    (10, 1000),         # mantener mucho
    (6, 500),           # compactar antes
    (6, 3000),          # compactar más tarde
    (6, 10**9),         # nunca compactar (referencia)
    (5, 1000),          # MANTENER impar: ¿qué pasa?
]


class Contador:
    """Envuelve el cliente de Anthropic para sumar el uso de TODAS las llamadas (también el resumen)."""

    def __init__(self, llm):
        self._llm, self.entrada, self.salida, self.llamadas_resumen = llm, 0, 0, 0
        self.messages = self

    def create(self, **kw):
        r = self._llm.messages.create(**kw)
        self.entrada += r.usage.input_tokens
        self.salida += r.usage.output_tokens
        self.llamadas_resumen += kw.get("system", "").startswith("Resume")
        return r


def conversar(mantener: int, umbral: int) -> dict:
    sc.MANTENER, sc.UMBRAL_TOKENS = mantener, umbral  # compactar() lee las constantes del módulo
    contador = Contador(sc.llm.__class__(max_retries=3)) if not isinstance(sc.llm, Contador) else sc.llm
    contador.entrada = contador.salida = contador.llamadas_resumen = 0
    sc.llm = contador
    historial, tokens_historial, por_turno, respuesta = [], 0, [], ""
    for n, texto in enumerate(TURNOS, 1):
        compactado = False
        if len(historial) > sc.MANTENER and tokens_historial > sc.UMBRAL_TOKENS:
            historial = sc.compactar(historial)
            compactado = True
        historial.append({"role": "user", "content": texto})
        try:
            r = contador.create(model=sc.MODELO, max_tokens=800, system=sc.SISTEMA,
                                messages=historial)
        except Exception as e:
            return {"error": f"turno {n}: {type(e).__name__}: {e}", "por_turno": por_turno}
        tokens_historial = r.usage.input_tokens + r.usage.output_tokens
        respuesta = "".join(b.text for b in r.content if b.type == "text")
        historial.append({"role": "assistant", "content": respuesta})
        por_turno.append((r.usage.input_tokens, compactado,
                          [m["role"][0] for m in historial]))  # secuencia de roles: u/a
    sobreviven = {k: any(v.lower() in respuesta.lower() for v in vs)
                  for k, vs in DATOS_TURNO_1.items()}
    return {"por_turno": por_turno, "entrada": contador.entrada, "salida": contador.salida,
            "resumenes": contador.llamadas_resumen, "sobreviven": sobreviven,
            "respuesta_final": respuesta}


def precio_modelo(modelo: str) -> tuple[float, float]:
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20) as f:
        p = next(m["pricing"] for m in json.load(f)["data"] if m["id"] == modelo)
    return float(p["prompt"]), float(p["completion"])


if __name__ == "__main__":
    p_in, p_out = precio_modelo(sc.MODELO)
    filas = []
    for mantener, umbral in CONFIGURACIONES:
        print(f"\n{'=' * 78}\nMANTENER={mantener} · UMBRAL_TOKENS={umbral}\n{'=' * 78}")
        res = conversar(mantener, umbral)
        for n, (t_in, comp, roles) in enumerate(res["por_turno"], 1):
            marca = "  (historial compactado)" if comp else ""
            print(f"  turno {n:2}: {t_in:5} tokens de entrada · {len(roles):2} mensajes{marca}")
        if "error" in res:
            print(f"  ERROR en {res['error']}")
            filas.append((mantener, umbral, None))
            continue
        if mantener % 2:  # enseñamos el orden de roles tras compactar
            print("  roles tras el último turno:", "".join(res["por_turno"][-1][2]))
        print(f"\n  Respuesta al turno 12:\n  {res['respuesta_final']}\n")
        print(f"  Datos del turno 1 que sobreviven: {res['sobreviven']}")
        filas.append((mantener, umbral, res))

    print(f"\n{'=' * 78}\nRESUMEN\n{'=' * 78}")
    print(f"{'MANTENER':>8} {'UMBRAL':>10} {'compact.':>8} {'entrada':>8} {'salida':>7} "
          f"{'USD':>8} {'turno 12':>8}  datos del turno 1")
    for mantener, umbral, res in filas:
        if res is None:
            print(f"{mantener:8} {umbral:10}   ERROR")
            continue
        usd = res["entrada"] * p_in + res["salida"] * p_out
        ok = sum(res["sobreviven"].values())
        perdidos = [k for k, v in res["sobreviven"].items() if not v]
        print(f"{mantener:8} {umbral:10} {res['resumenes']:8} {res['entrada']:8} {res['salida']:7} "
              f"{usd:8.4f} {res['por_turno'][-1][0]:8}  {ok}/6 {'(pierde: ' + ', '.join(perdidos) + ')' if perdidos else ''}")
