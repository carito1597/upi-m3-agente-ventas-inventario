"""Lee casos.json y evalúa al agente real en terminal, sin guardar informes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent

def cargar_casos(ruta):
    casos = json.loads(ruta.read_text(encoding='utf-8-sig'))
    if not isinstance(casos, list) or len(casos) != 5:
        raise ValueError('El archivo debe contener exactamente cinco casos.')
    herramientas = {'buscar_productos', 'consultar_stock', 'consultar_destino'}
    for numero, caso in enumerate(casos, 1):
        if not isinstance(caso, dict) or not isinstance(caso.get('consulta'), str) or not caso['consulta'].strip():
            raise ValueError(f'Caso {numero}: falta una consulta válida.')
        for clave in ['debe_usar', 'no_debe_usar']:
            valores = caso.get(clave)
            if not isinstance(valores, list) or not all(isinstance(x, str) and x in herramientas for x in valores):
                raise ValueError(f'Caso {numero}: {clave} debe ser una lista de herramientas válidas.')
        if set(caso['debe_usar']) & set(caso['no_debe_usar']):
            raise ValueError(f'Caso {numero}: una herramienta no puede ser obligatoria y prohibida.')
        if 'error_esperado' in caso and (not isinstance(caso['error_esperado'], str) or not caso['error_esperado'].startswith('ERROR:')):
            raise ValueError(f'Caso {numero}: el error esperado debe empezar con ERROR:.')
    if not any(c.get('error_esperado') for c in casos):
        raise ValueError('Incluye al menos un caso de error esperado.')
    return casos


def limpiar(texto):
    for nombre, valor in os.environ.items():
        if any(p in nombre.upper() for p in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD')) and len(valor) >= 8:
            texto = texto.replace(valor, '[OCULTO]')
    return re.sub(r'\b(?:gsk_|sk-)[A-Za-z0-9_-]+', '[OCULTO]', texto)

def evaluar(caso, llamadas, respuesta, error=None):
    solicitadas = {c['herramienta'] for c in llamadas}
    ejecutadas = {c['herramienta'] for c in llamadas if c['recibio_resultado']}
    motivos = []
    faltan = set(caso['debe_usar']) - ejecutadas
    prohibidas = set(caso['no_debe_usar']) & solicitadas
    if faltan:
        motivos.append('Faltan herramientas obligatorias ejecutadas: ' + ', '.join(sorted(faltan)))
    if prohibidas:
        motivos.append('Se solicitaron herramientas prohibidas: ' + ', '.join(sorted(prohibidas)))
    for c in llamadas:
        datos = c['resultado']
        mensaje = datos.get('mensaje', '') if isinstance(datos, dict) else str(datos)
        esperado = (caso.get('error_esperado') == mensaje and c['herramienta'] == 'consultar_stock'
                    and c['argumentos'].get('producto_id', '').strip().upper() == 'ROP999'
                    and c['argumentos'].get('cantidad', 1) == 1
                    and isinstance(datos, dict) and datos.get('disponible') is False)
        if not c['recibio_resultado'] or c.get('estado') == 'error' or (mensaje.startswith('ERROR:') and not esperado):
            motivos.append('Llamada incompleta o con error: ' + c['herramienta'])
    if caso.get('error_esperado'):
        coincide = any(c['recibio_resultado'] and c['herramienta'] == 'consultar_stock'
            and c['argumentos'].get('producto_id', '').strip().upper() == 'ROP999'
            and c['argumentos'].get('cantidad', 1) == 1 and isinstance(c['resultado'], dict)
            and c['resultado'].get('mensaje') == caso['error_esperado']
            and c['resultado'].get('disponible') is False for c in llamadas)
        if not coincide:
            motivos.append('No se obtuvo el error esperado de producto inexistente para ROP999 y cantidad 1.')
        texto = str(respuesta).casefold()
        if not re.search(r'inexistente|no existe|no se encontr|no encontr|no est[aá] (?:en|registrado)', texto):
            motivos.append('La respuesta no comunica explícitamente que el producto no existe o no se encontró.')
        if re.search(r'agotad|sin stock|sin existencias', texto):
            motivos.append('La respuesta confunde un producto inexistente con uno agotado.')
    if not respuesta:
        motivos.append('No se produjo una respuesta final no vacía.')
    if error:
        motivos.append('Error de ejecución: ' + error)
    return {'estado': 'FALLIDO' if motivos else 'APROBADO', 'motivos': motivos or ['Herramientas obligatorias ejecutadas, ninguna prohibida, respuesta final y ausencia de errores inesperados; error esperado verificado cuando corresponde.']}

def extraer(mensajes):
    from langchain_core.messages import AIMessage, ToolMessage
    resultados = {m.tool_call_id: m for m in mensajes if isinstance(m, ToolMessage)}
    llamadas = []
    for m in mensajes:
        if isinstance(m, AIMessage):
            for c in m.tool_calls:
                r = resultados.get(c['id'])
                contenido = r.content if r is not None else None
                try:
                    contenido = json.loads(contenido) if isinstance(contenido, str) else contenido
                except ValueError:
                    pass
                llamadas.append({'id': c['id'], 'herramienta': c['name'], 'argumentos': c['args'],
                                 'recibio_resultado': r is not None, 'resultado': contenido,
                                 'estado': getattr(r, 'status', None)})
    return llamadas

def ejecutar(numero, caso, *, detalle=False, total=None):
    from langchain_core.messages import AIMessage, ToolMessage
    mensajes = []
    registro = {'caso': numero, 'fecha_utc': datetime.now(timezone.utc).isoformat(), **caso,
                'llamadas': [], 'respuesta': '', 'error': None, 'estado': 'EN CURSO'}
    titulos = ['Búsqueda de blusa', 'Disponibilidad de dos vestidos', 'Consulta de localidad',
               'Búsqueda sin coincidencias', 'Producto inexistente']
    encabezado = f'CASO {numero}'
    if total is not None:
        encabezado += f' DE {total}'
        if 1 <= numero <= len(titulos):
            encabezado += ' · ' + titulos[numero - 1]
    print('\n' + encabezado, flush=True)
    print('─' * 65)
    print(limpiar('Pregunta:\n' + caso['consulta']), flush=True)
    if detalle and caso.get('error_esperado'):
        print('Error esperado: ' + caso['error_esperado'])
    try:
        from agente import agente
        for evento in agente.stream({'messages': [{'role': 'user', 'content': caso['consulta']}]},
                                    config={'recursion_limit': 15}, stream_mode='updates'):
            for datos in evento.values():
                if isinstance(datos, dict):
                    nuevos = datos.get('messages', [])
                    for mensaje in nuevos if detalle else []:
                        if isinstance(mensaje, AIMessage):
                            for llamada in mensaje.tool_calls:
                                print(limpiar('SOLICITUD REAL: ' + llamada['name'] + ' | ID: ' + llamada['id']
                                    + ' | Argumentos: ' + json.dumps(llamada['args'], ensure_ascii=False)), flush=True)
                        elif isinstance(mensaje, ToolMessage):
                            print(limpiar('RESULTADO REAL | ID: ' + mensaje.tool_call_id + ' | ' + str(mensaje.content)), flush=True)
                    mensajes.extend(nuevos)
                    registro['llamadas'] = extraer(mensajes)
        final = mensajes[-1] if mensajes else None
        if isinstance(final, AIMessage) and not final.tool_calls:
            registro['respuesta'] = final.content
            if isinstance(final.content, str) and 'Model call limits exceeded' in final.content:
                registro['error'] = 'El middleware detuvo la ejecución al alcanzar el límite de llamadas al modelo.'
    except Exception as error:
        registro['error'] = limpiar(f'{type(error).__name__}: {error}')
    registro.update(evaluar(caso, registro['llamadas'], registro['respuesta'], registro['error']))
    print(limpiar('\nRespuesta del agente:\n' + str(registro['respuesta'] or '(sin respuesta final)')), flush=True)
    ejecutadas = {c['herramienta'] for c in registro['llamadas'] if c['recibio_resultado']}
    nombres = list(dict.fromkeys(['buscar_productos', 'consultar_stock', 'consultar_destino']
                                + [c['herramienta'] for c in registro['llamadas']]))
    print(f'\n{"Herramienta":<23} {"Criterio":<17} ¿Se ejecutó?')
    print('─' * 55)
    for nombre in nombres:
        criterio = ('debe_usar' if nombre in caso['debe_usar'] else
                    'no_debe_usar' if nombre in caso['no_debe_usar'] else 'opcional')
        print(f'{nombre:<23} {criterio:<17} {"Sí" if nombre in ejecutadas else "No"}')
    print('\nResultado: ' + registro['estado'], flush=True)
    if registro['estado'] == 'FALLIDO':
        for motivo in registro['motivos']:
            print(limpiar('Motivo: ' + motivo))
    elif caso.get('error_esperado'):
        print('El agente recibió y explicó el error esperado de producto inexistente.')
    return registro

def errores_recibidos(registro):
    """Obtiene mensajes de error reales, no el texto de los criterios."""
    errores = []
    for llamada in registro['llamadas']:
        if not llamada['recibio_resultado']:
            continue
        datos = llamada['resultado']
        mensaje = datos.get('mensaje', '') if isinstance(datos, dict) else datos
        if isinstance(mensaje, str) and mensaje.startswith('ERROR:'):
            errores.append((llamada['herramienta'], llamada['argumentos'], mensaje))
    return errores


def tipo_caso(registro):
    if registro.get('error_esperado'):
        return 'Error esperado'
    if 'consultar_destino' in registro['debe_usar']:
        return 'Consulta a API pública'
    if any(c['recibio_resultado'] and isinstance(c['resultado'], dict)
           and c['resultado'].get('productos') == [] for c in registro['llamadas']):
        return 'Búsqueda sin coincidencias'
    return 'Consulta normal'


def mostrar_resumen(filas):
    aprobados = sum(r['estado'] == 'APROBADO' for r in filas)
    porcentaje = aprobados / len(filas) * 100
    print('\n=== RESUMEN ===')
    print(f'{"Caso":<8} {"Tipo de caso":<29} Resultado')
    print('─' * 55)
    for r in filas:
        print(f'{r["caso"]:<8} {tipo_caso(r):<29} {r["estado"]}')
    for r in filas:
        if not r.get('error_esperado'):
            continue
        print(f'\nCASO DE ERROR EVALUADO: {r["caso"]}')
        print(limpiar('  Pregunta: ' + r['consulta']))
        print(limpiar('  Error esperado: ' + r['error_esperado']))
        errores = errores_recibidos(r)
        if errores:
            for herramienta, argumentos, mensaje in errores:
                print('  Herramienta: ' + herramienta)
                print(limpiar('  Argumentos: ' + json.dumps(argumentos, ensure_ascii=False)))
                print(limpiar('  Error recibido: ' + mensaje))
        else:
            print('  Error recibido: ninguno registrado; el error esperado no se ha demostrado.')
        print(limpiar('  Respuesta del agente: ' + str(r['respuesta'] or '(sin respuesta final)')))
        if r['estado'] == 'APROBADO' and any(e[2] == r['error_esperado'] for e in errores):
            print('  Manejo del error: CORRECTO según los criterios automáticos.')
        else:
            print('  Manejo del error: NO VERIFICADO como correcto; revisa los motivos del caso.')
    print(f'\nAprobados: {aprobados}/{len(filas)} | Fallidos: {len(filas)-aprobados}')
    print(f'Cumplimiento: {aprobados} / {len(filas)} × 100 = {porcentaje:.1f} %')
    print('APROBADO significa que cumplió los criterios; un error esperado bien manejado también aprueba.')
    return 0 if aprobados == len(filas) else 1


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detalle', action='store_true', help='Mostrar llamadas, argumentos y resultados completos')
    parser.add_argument('--casos', type=Path, default=BASE/'casos.json')
    parser.add_argument('--ver-casos', action='store_true', help='Mostrar preguntas y criterios sin consumir API')
    parser.add_argument('--ejecutar', action='store_true', help='Ejecutar; pide confirmación si falta --autorizar-api')
    parser.add_argument('--autorizar-api', action='store_true', help='Confirmar consumo de Groq sin pregunta interactiva')
    args = parser.parse_args()
    try:
        casos = cargar_casos(args.casos)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.ver_casos:
        for n, caso in enumerate(casos, 1):
            print(f'Caso {n}: ' + caso['consulta'])
            print('  debe_usar: ' + ', '.join(caso['debe_usar']))
            print('  no_debe_usar: ' + ', '.join(caso['no_debe_usar']))
            if caso.get('error_esperado'):
                print('  error_esperado: ' + caso['error_esperado'])
        return 0
    if not args.autorizar_api:
        try:
            respuesta = input('Se ejecutarán cinco consultas reales con Groq y pueden consumir créditos. ¿Continuar? [s/N]: ')
        except (EOFError, KeyboardInterrupt):
            respuesta = ''
        if respuesta.strip().casefold() not in ['s', 'si', 'sí']:
            print('Cancelado. No se ejecutaron consultas ni se calculó un porcentaje.')
            return 0
    from dotenv import load_dotenv
    load_dotenv(BASE/'.env')
    print('EVALUACIÓN REAL - ' + datetime.now(timezone.utc).isoformat(), flush=True)
    print('Cada caso inicia una consulta nueva. Se evalúan herramientas y errores esperados; no toda la calidad semántica de las respuestas.')
    filas = [ejecutar(n, caso, detalle=args.detalle, total=len(casos)) for n, caso in enumerate(casos, 1)]
    return mostrar_resumen(filas)

if __name__ == '__main__':
    raise SystemExit(main())
