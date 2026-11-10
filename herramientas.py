
import requests
from langchain_core.tools import tool
from catalogo import catalogo


@tool
def buscar_productos(
    nombre: str = "",
    talla: str = "",
    color: str = ""
) -> dict:
    """Busca ropa por nombre, talla y color en el catálogo simulado."""

    palabras = [p.lower().rstrip("s") for p in nombre.split()]

    encontrados = [
        p for p in catalogo
        if all(
            w in [x.lower().rstrip("s") for x in p["nombre"].split()]
            for w in palabras
        )
        and (not talla or p["talla"].lower() == talla.lower())
        and (not color or p["color"].lower() == color.lower())
    ]

    return {
        "productos": encontrados,
        "mensaje": "Coincidencias encontradas" if encontrados else "Sin coincidencias"
    }


@tool
def consultar_stock(producto_id: str, cantidad: int = 1) -> dict:
    """Verifica disponibilidad de un producto sin modificar el inventario."""

    if cantidad <= 0:
        return {"disponible": False, "mensaje": "La cantidad debe ser positiva"}

    producto = next(
        (p for p in catalogo if p["id"] == producto_id.upper()),
        None
    )

    if not producto:
        return {"disponible": False, "mensaje": "Producto inexistente"}

    return {
        "producto": producto["nombre"],
        "stock": producto["stock"],
        "cantidad_solicitada": cantidad,
        "disponible": producto["stock"] >= cantidad
    }


@tool
def consultar_destino(ciudad: str) -> dict:
    """Consulta localidades bolivianas mediante la API pública Open-Meteo."""

    if len(ciudad.strip()) < 2:
        return {"encontrado": False, "mensaje": "Indica una ciudad válida"}

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

        lugares = respuesta.json().get("results", [])

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

    except (requests.RequestException, ValueError) as e:
        return {
            "encontrado": False,
            "mensaje": f"API no disponible: {type(e).__name__}"
        }
