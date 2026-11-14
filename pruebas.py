"""Diez casos de integración ejecutados con el agente real."""

import json
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage
from catalogo import catalogo


casos = [
    {
        "consulta": "¿Tienes blusas negras talla M?",
        "debe_usar": ["buscar_productos"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "buscar_productos", "producto_id": "ROP001"},
    },
    {
        "consulta": "Busca un vestido rojo talla M y verifica si hay 2 unidades.",
        "debe_usar": ["buscar_productos", "consultar_stock"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "consultar_stock", "argumentos": {"producto_id": "ROP004", "cantidad": 2}, "resultado": {"stock": 3, "cantidad_solicitada": 2, "disponible": True}},
    },
    {
        "consulta": "Busca la ciudad de Cochabamba en Bolivia.",
        "debe_usar": ["consultar_destino"],
        "no_debe_usar": ["consultar_stock"],
        "esperado": {"herramienta": "consultar_destino", "argumentos": {"ciudad": "Cochabamba"}, "ciudad": "Cochabamba"},
    },
    {
        "consulta": "¿Hay una chaqueta denim talla S disponible?",
        "debe_usar": ["buscar_productos"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "buscar_productos", "producto_id": "ROP005", "stock": 0},
    },
    {
        "consulta": "¿Tienes zapatos deportivos talla M?",
        "debe_usar": ["buscar_productos"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "buscar_productos", "nombre_contiene": "zapato", "resultado": {"productos": []}},
    },
    {
        "consulta": "Busca una camiseta básica blanca talla XS e indica su precio y stock.",
        "debe_usar": ["buscar_productos"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "buscar_productos", "producto_id": "ROP006"},
    },
    {
        "consulta": "Consulta el stock del producto ROP004 para 10 unidades. ¿Alcanza?",
        "debe_usar": ["consultar_stock"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "consultar_stock", "argumentos": {"producto_id": "ROP004", "cantidad": 10}, "resultado": {"stock": 3, "cantidad_solicitada": 10, "disponible": False}},
    },
    {
        "consulta": "Consulta el stock del producto ROP999 para 1 unidad.",
        "debe_usar": ["consultar_stock"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "consultar_stock", "argumentos": {"producto_id": "ROP999"}, "resultado": {"disponible": False}, "error_contiene": "inexistente"},
    },
    {
        "consulta": "Consulta el stock del producto ROP004 con cantidad solicitada igual a 0.",
        "debe_usar": ["consultar_stock"],
        "no_debe_usar": ["consultar_destino"],
        "esperado": {"herramienta": "consultar_stock", "argumentos": {"producto_id": "ROP004", "cantidad": 0}, "resultado": {"disponible": False}, "error_contiene": "cantidad"},
    },
    {
        "consulta": "Busca mediante Open-Meteo la ciudad ZzxqvInventada987654 en Bolivia.",
        "debe_usar": ["consultar_destino"],
        "no_debe_usar": ["buscar_productos", "consultar_stock"],
        "esperado": {"herramienta": "consultar_destino", "argumentos": {"ciudad": "ZzxqvInventada987654"}, "resultado": {"encontrado": False, "ubicaciones": []}},
    },
]


def registrar_llamadas(mensajes):
    """Relaciona las llamadas reales con sus resultados mediante tool_call_id."""
    respuestas = {m.tool_call_id: m for m in mensajes if isinstance(m, ToolMessage)}
    llamadas = []
    for mensaje in mensajes:
        if not isinstance(mensaje, AIMessage):
            continue
        for llamada in mensaje.tool_calls:
            respuesta = respuestas.get(llamada["id"])
            contenido = respuesta.content if respuesta is not None else None
            try:
                datos = json.loads(contenido) if isinstance(contenido, str) else contenido
            except (ValueError, TypeError):
                datos = None
            llamadas.append({
                "id": llamada["id"], "herramienta": llamada["name"],
                "argumentos": llamada["args"], "resultado": contenido,
                "datos": datos, "estado": getattr(respuesta, "status", None),
            })
    return llamadas


def evaluar_esperado(esperado, llamadas):
    candidatas = [c for c in llamadas if c["herramienta"] == esperado["herramienta"]]
    if not candidatas:
        return "FALLO", "No se llamó a la herramienta necesaria para comprobar el resultado."
    motivos = []
    incierto = False
    for llamada in candidatas:
        argumentos = llamada["argumentos"]
        if any(argumentos.get(k) != v for k, v in esperado.get("argumentos", {}).items()):
            motivos.append("Los argumentos no corresponden a la consulta esperada.")
            continue
        if esperado.get("nombre_contiene", "") not in argumentos.get("nombre", "").casefold():
            motivos.append("La búsqueda no corresponde al producto solicitado.")
            continue
        datos = llamada["datos"]
        if not isinstance(datos, dict):
            incierto = True
            motivos.append("No hay un resultado estructurado verificable para la llamada.")
            continue
        mensaje = datos.get("mensaje", "")
        if isinstance(mensaje, str) and mensaje.startswith("ERROR:"):
            if "error_contiene" not in esperado:
                incierto = True
                motivos.append("La herramienta devolvió un error: " + mensaje)
                continue
        elif "error_contiene" in esperado:
            motivos.append("No se devolvió el ERROR: esperado.")
            continue
        if "error_contiene" in esperado and esperado["error_contiene"] not in mensaje.casefold():
            motivos.append("El error no corresponde a la condición esperada.")
            continue
        if any(type(datos.get(k)) is not type(v) or datos.get(k) != v for k, v in esperado.get("resultado", {}).items()):
            motivos.append("El resultado no cumple los valores esperados.")
            continue
        if "producto_id" in esperado:
            producto = next(p for p in catalogo if p["id"] == esperado["producto_id"])
            if producto not in datos.get("productos", []):
                motivos.append("No se encontró el producto con sus datos del catálogo.")
                continue
            if "stock" in esperado and producto["stock"] != esperado["stock"]:
                motivos.append("El producto no tiene el stock esperado.")
                continue
        if "ciudad" in esperado:
            ubicaciones = datos.get("ubicaciones")
            if datos.get("encontrado") is not True or not isinstance(ubicaciones, list) or not any(
                isinstance(u, dict) and u.get("ciudad", "").casefold() == esperado["ciudad"].casefold()
                for u in ubicaciones
            ):
                motivos.append("La API no devolvió la localidad esperada.")
                continue
        return "OK", "El resultado real de la herramienta cumple la condición esperada."
    return ("NO VERIFICABLE" if incierto else "FALLO"), " ".join(dict.fromkeys(motivos))


def main():
    ruta = Path(__file__).with_name("resultados_pruebas.txt")
    filas = []
    # Importar este módulo no crea el agente ni ejecuta consultas.
    try:
        from agente import agente
        error_inicio = None
    except Exception as error:
        agente = None
        error_inicio = f"{type(error).__name__}: {error}"

    with ruta.open("w", encoding="utf-8") as archivo:
        def emitir(texto=""):
            print(texto, flush=True)
            archivo.write(texto + chr(10))
            archivo.flush()

        emitir("EVALUACIÓN REAL DEL AGENTE - " + datetime.now(timezone.utc).isoformat())
        emitir("Se evalúan selección y resultados de herramientas; no la exactitud semántica integral de la respuesta final.")
        for numero, caso in enumerate(casos, 1):
            emitir(f"--- CASO {numero} ---")
            emitir("Consulta: " + caso["consulta"])
            emitir("Debe usar: " + ", ".join(caso["debe_usar"]))
            emitir("No debe usar: " + ", ".join(caso["no_debe_usar"]))
            emitir("Condición esperada: " + json.dumps(caso["esperado"], ensure_ascii=False))
            seleccion = cumplimiento = general = "NO VERIFICABLE"
            try:
                if error_inicio:
                    raise RuntimeError(error_inicio)
                resultado = agente.invoke(
                    {"messages": [{"role": "user", "content": caso["consulta"]}]},
                    config={"recursion_limit": 15},
                )
                mensajes = resultado["messages"]
                llamadas = registrar_llamadas(mensajes)
                utilizadas = {c["herramienta"] for c in llamadas}
                seleccion = "OK" if (set(caso["debe_usar"]) <= utilizadas and not set(caso["no_debe_usar"]) & utilizadas) else "FALLO"
                for llamada in llamadas:
                    emitir("Llamada real: " + json.dumps(llamada, ensure_ascii=False, default=str))
                if not llamadas:
                    emitir("Sin llamadas a herramientas registradas.")
                cumplimiento, motivo = evaluar_esperado(caso["esperado"], llamadas)
                final = mensajes[-1] if mensajes else None
                emitir("Respuesta final: " + str(getattr(final, "content", "")))
                if not isinstance(final, AIMessage) or final.tool_calls or not final.content:
                    cumplimiento = "FALLO"
                    motivo += " No se produjo una respuesta final del agente."
                if seleccion == "FALLO" or cumplimiento == "FALLO":
                    general = "FALLO"
                elif cumplimiento == "OK":
                    general = "OK"
            except Exception as error:
                motivo = f"Ejecución no verificable: {type(error).__name__}: {error}. No se dispone de una traza completa de llamadas."
            emitir(f"Selección: {seleccion} | Resultado esperado: {cumplimiento} | General: {general}")
            emitir("Motivo: " + motivo)
            filas.append((numero, seleccion, cumplimiento, general))

        emitir("=== TABLA RESUMEN ===")
        emitir(f"{'Caso':<6} | {'Selección':<15} | {'Resultado esperado':<18} | {'General':<15}")
        for numero, seleccion, cumplimiento, general in filas:
            emitir(f"{numero:<6} | {seleccion:<15} | {cumplimiento:<18} | {general:<15}")
        for indice, etiqueta in [(1, "Selección"), (2, "Resultado esperado"), (3, "General")]:
            aciertos = sum(f[indice] == "OK" for f in filas)
            fallos = sum(f[indice] == "FALLO" for f in filas)
            no_verificables = sum(f[indice] == "NO VERIFICABLE" for f in filas)
            emitir(f"{etiqueta}: {aciertos}/{len(filas)} = {aciertos / len(filas) * 100:.1f}% de cumplimiento; {fallos} fallos; {no_verificables} no verificables.")
        emitir("Los porcentajes usan los diez casos como denominador; los no verificables no cuentan como aciertos.")
        emitir("Resultados guardados en: " + str(ruta))
    return 0 if all(f[3] == "OK" for f in filas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
