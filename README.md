# Agente Inteligente de Ventas e Inventario para una Tienda de Ropa

**Módulo 3 – Diseño y Orquestación de Agentes Inteligentes**  
**Integrante:** Carolina Andrea Villalobos Montaño

## 1. Problema y usuarios

Las pequeñas tiendas de ropa necesitan consultar rápidamente productos, tallas, colores y existencias para atender a sus clientes.

Este proyecto desarrolla un agente inteligente que ayuda a vendedores y propietarios a consultar un catálogo simulado, verificar disponibilidad y buscar localidades bolivianas mediante una API pública.

El prototipo utiliza cinco productos ficticios y no registra ventas ni modifica inventario.

## 2. Arquitectura

Se utiliza un **agente ReAct**, desarrollado con LangChain y LangGraph, conectado al modelo `openai/gpt-oss-20b` mediante Groq.

El agente interpreta cada consulta, selecciona las herramientas necesarias, analiza sus resultados y responde al usuario.

**Flujo general:**

Usuario → Agente ReAct → Herramientas → Agente → Respuesta

El agente puede repetir el ciclo de consulta cuando necesita información adicional.

## 3. Los cinco primitivos

| Primitivo | Implementación |
|---|---|
| Instrucciones | System prompt que define el rol, uso de herramientas, prohibiciones y manejo de errores. |
| Herramientas | `buscar_productos`, `consultar_stock` y `consultar_destino`. |
| Memoria | Mantiene mensajes y resultados durante una ejecución. No implementa memoria persistente entre conversaciones. |
| Estado | Los mensajes del agente incluyen los argumentos y resultados de las herramientas. |
| Control | `ModelCallLimitMiddleware` limita las llamadas al modelo; adicionalmente se utiliza `recursion_limit=15`. |

### Herramientas

- **buscar_productos:** recibe nombre, talla y color. Devuelve productos coincidentes o un mensaje sin coincidencias.
- **consultar_stock:** recibe identificador y cantidad. Devuelve disponibilidad; contempla cantidades inválidas y productos inexistentes.
- **consultar_destino:** recibe una ciudad y consulta la API real de geocodificación de Open-Meteo. Devuelve localidades encontradas o información del error.

El agente no realiza cobros, registra pedidos ni modifica inventario. Estas operaciones requerirían autorización humana si se implementaran posteriormente.

## 4. Estructura del proyecto

```text
proyecto_m3/
├── agente.py
├── herramientas.py
├── catalogo.py
├── pruebas.py
├── resultados_pruebas.txt
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 5. Instalación y ejecución

**Requisitos:** Python 3.12, conexión a internet y una API Key de Groq.

Clonar el repositorio y acceder a su carpeta:

```bash
git clone URL_DEL_REPOSITORIO
cd proyecto_m3
```

Crear el entorno virtual:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instalar las dependencias:

```powershell
python -m pip install -r requirements.txt
```

Crear un archivo `.env` tomando como referencia `.env.example`:

```dotenv
GROQ_API_KEY=tu_clave_de_groq
```

Ejecutar el agente:

```powershell
python agente.py
```

Ejecutar las pruebas:

```powershell
python pruebas.py
```

**Seguridad:** la clave real se almacena únicamente en `.env`, archivo excluido de Git mediante `.gitignore`.

## 6. Control de ejecución

Se implementó `ModelCallLimitMiddleware` con `run_limit=5` y `exit_behavior="end"`.

Para demostrar su funcionamiento, se cambió temporalmente el límite a `run_limit=1`. El agente se detuvo y devolvió:

```text
Model call limits exceeded: run limit (1/1)
```

Después se restauró el límite a cinco llamadas.

## 7. Resultados de pruebas

Se evaluaron cinco consultas, verificando las herramientas que el agente debía y no debía utilizar.

| Caso | Consulta | Debe usar | No debe usar | Resultado |
|---|---|---|---|---|
| 1 | Blusas negras talla M | buscar_productos | consultar_destino | Correcto |
| 2 | Vestido rojo talla M, 2 unidades | buscar_productos, consultar_stock | consultar_destino | Correcto |
| 3 | Ciudad de Cochabamba | consultar_destino | consultar_stock | Correcto |
| 4 | Chaqueta denim talla S | buscar_productos | consultar_destino | Correcto |
| 5 | Zapatos deportivos talla M | buscar_productos | consultar_destino | Correcto |

**Aciertos: 5/5 — Porcentaje: 100 %.**

El caso 5 representa un producto inexistente en el catálogo simulado.

La evaluación mide el cumplimiento de las herramientas esperadas y prohibidas, no la exactitud integral de las respuestas.

Los resultados detallados se encuentran en `resultados_pruebas.txt`.

## 8. Reflexión

El agente utilizó las herramientas esperadas en los cinco casos evaluados.  
La consulta de stock permitió comprobar disponibilidad sin modificar el inventario.  
La API de Open-Meteo permitió consultar localidades reales de Bolivia.  
Se incorporó un middleware para limitar las llamadas al modelo.  
La prueba con un límite de una llamada confirmó que el control detiene la ejecución.  
El porcentaje obtenido fue del 100 % en selección de herramientas.  
Como mejora futura, convendría evitar respuestas que ofrezcan servicios no implementados, como seguimiento de reposición o confirmación de envíos.

## 9. Demostración en video

Enlace: pendiente de incorporar.