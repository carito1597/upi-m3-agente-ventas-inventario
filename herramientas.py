
import unicodedata

import requests
from langchain_core.tools import tool
from catalogo import catalogo


def _normalizar(texto: str) -> str:
    """Unifica espacios, mayúsculas y tildes sin alterar los datos originales."""
    texto = unicodedata.normalize("NFD", texto.casefold())
    return " ".join(
        "".join(c for c in texto if not unicodedata.combining(c)).split()
    )


def _variantes(palabra: str) -> set[str]:
    variantes = {palabra}
    if len(palabra) > 3 and palabra.endswith("s"):
        variantes.add(palabra[:-1])
        if palabra.endswith("es"):
            variantes.add(palabra[:-2])
    return variantes


def _color_normalizado(color: str) -> str:
    equivalencias = {
        "negra": "negro", "blanca": "blanco", "roja": "rojo",
        "morada": "morado", "amarilla": "amarillo",
    }
    palabras = []
    for palabra in _normalizar(color).split():
        if palabra.endswith(("as", "os")):
            palabra = palabra[:-1]
        elif palabra.endswith("es") and palabra[:-2] in {"azul", "gris", "marron"}:
            palabra = palabra[:-2]
        elif palabra.endswith("s") and palabra != "gris":
            palabra = palabra[:-1]
        palabras.append(equivalencias.get(palabra, palabra))
    return " ".join(palabras)


@tool
def buscar_productos(
    nombre: str = "",
    talla: str = "",
    color: str = ""
) -> dict:
    """Busca ropa por nombre, talla y color en el catálogo simulado."""

    if not all(isinstance(valor, str) for valor in (nombre, talla, color)):
        return {"productos": [], "mensaje": "ERROR: Los filtros deben ser texto"}

    palabras = [_variantes(p) for p in _normalizar(nombre).split()]
    talla = _normalizar(talla)
    color = _color_normalizado(color)

    encontrados = [
        p for p in catalogo
        if all(
            any(w & _variantes(x) for x in _normalizar(p["nombre"]).split())
            for w in palabras
        )
        and (not talla or _normalizar(p["talla"]) == talla)
        and (not color or _color_normalizado(p["color"]) == color)
    ]

    return {
        "productos": encontrados,
        "mensaje": "Coincidencias encontradas" if encontrados else "Sin coincidencias"
    }


@tool
def consultar_stock(producto_id: str, cantidad: int = 1) -> dict:
    """Verifica disponibilidad de un producto sin modificar el inventario."""

    if type(cantidad) is not int or cantidad <= 0:
        return {"disponible": False, "mensaje": "ERROR: La cantidad debe ser un entero positivo"}

    if not isinstance(producto_id, str) or not producto_id.strip():
        return {"disponible": False, "mensaje": "ERROR: Indica un identificador válido"}

    producto_id = producto_id.strip().upper()

    producto = next(
        (p for p in catalogo if p["id"] == producto_id.upper()),
        None
    )

    if not producto:
        return {"disponible": False, "mensaje": "ERROR: Producto inexistente"}

    return {
        "producto": producto["nombre"],
        "stock": producto["stock"],
        "cantidad_solicitada": cantidad,
        "disponible": producto["stock"] >= cantidad
    }


@tool
def consultar_destino(ciudad: str) -> dict:
    """Consulta localidades bolivianas mediante la API pública Open-Meteo."""

    if not isinstance(ciudad, str) or len(ciudad.strip()) < 2:
        return {"encontrado": False, "mensaje": "ERROR: Indica una ciudad válida"}

    ciudad = " ".join(ciudad.split())

    try:
        respuesta = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": ciudad,
                "count": 5,
                "language": "es",
                "countryCode": "BO"
            },
            timeout=10
        )
        respuesta.raise_for_status()

        datos = respuesta.json()
        if not isinstance(datos, dict) or datos.get("error"):
            raise ValueError("Respuesta inesperada")
        lugares = datos.get("results", [])
        if not isinstance(lugares, list):
            raise ValueError("Lista de localidades inválida")
        for lugar in lugares:
            if not isinstance(lugar, dict):
                raise ValueError("Localidad inválida")
            if not isinstance(lugar.get("name"), str) or not lugar["name"].strip():
                raise ValueError("Nombre de localidad inválido")
            if "admin1" in lugar and (
                not isinstance(lugar["admin1"], str) or not lugar["admin1"].strip()
            ):
                raise ValueError("Departamento inválido")

        return {
            "encontrado": bool(lugares),
            "ubicaciones": [
                {
                    "ciudad": x["name"],
                    "departamento": x.get("admin1", "No indicado")
                }
                for x in lugares
            ],
            "fuente": "Open-Meteo"
        }

    except requests.Timeout:
        return {"encontrado": False, "mensaje": "ERROR: Se agotó el tiempo de espera de Open-Meteo"}
    except requests.HTTPError:
        return {"encontrado": False, "mensaje": "ERROR: Open-Meteo devolvió un error HTTP"}
    except requests.RequestException:
        return {"encontrado": False, "mensaje": "ERROR: No se pudo conectar con Open-Meteo"}
    except ValueError:
        return {
            "encontrado": False,
            "mensaje": "ERROR: Open-Meteo devolvió JSON inválido o una estructura inesperada"
        }


def _error_validacion(error) -> str:
    """También presenta los errores de argumentos del decorador como ERROR:."""
    return "ERROR: Argumentos inválidos para la herramienta"


for _herramienta in (buscar_productos, consultar_stock, consultar_destino):
    _herramienta.handle_validation_error = _error_validacion
