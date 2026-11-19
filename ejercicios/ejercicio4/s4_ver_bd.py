"""Sesión 4 · P2. Qué hay guardado en hilos.db (checkpointer) y memoria.db (store).

Lee las bases de datos con sqlite3 directamente, sin pasar por LangChain, para comprobar
el olvido. Uso: python s4_ver_bd.py"""
import json
import sqlite3
from pathlib import Path


def ver_hilos():
    if not Path("hilos.db").exists():
        print("hilos.db: no existe")
        return
    con = sqlite3.connect("hilos.db")
    filas = con.execute("SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id "
                        "ORDER BY thread_id").fetchall()
    escrituras = dict(con.execute("SELECT thread_id, COUNT(*) FROM writes GROUP BY thread_id"))
    print(f"hilos.db · tabla checkpoints ({len(filas)} hilos):")
    for thread_id, n in filas:
        print(f"   {thread_id:15} {n:3} checkpoints · {escrituras.get(thread_id, 0):3} escrituras")
    huerfanos = set(escrituras) - {t for t, _ in filas}
    if huerfanos:
        print(f"   escrituras sin checkpoint: {sorted(huerfanos)}")


def ver_memoria():
    if not Path("memoria.db").exists():
        print("memoria.db: no existe")
        return
    con = sqlite3.connect("memoria.db")
    filas = con.execute("SELECT prefix, key, value FROM store ORDER BY prefix, key").fetchall()
    print(f"memoria.db · tabla store ({len(filas)} elementos):")
    for prefix, clave, valor in filas:
        print(f"   {prefix:12} {clave:25} {json.loads(valor)}")


if __name__ == "__main__":
    ver_hilos()
    ver_memoria()
