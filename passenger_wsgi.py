import os
import sys
import traceback
import logging

# Configurar logging
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), 'app_debug.log'),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Agregar rutas al path
app_dir = os.path.join(os.path.dirname(__file__), 'Siprot_back')
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, app_dir)

# Cambiar directorio de trabajo para que los imports relativos funcionen
os.chdir(app_dir)

from main import app

import asyncio
from io import BytesIO

ALLOWED_ORIGIN = 'https://siprot.nativoweb.com'

CORS_HEADERS = [
    ('Access-Control-Allow-Origin', ALLOWED_ORIGIN),
    ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, PATCH'),
    ('Access-Control-Allow-Headers', 'Accept, Accept-Language, Content-Language, Content-Type, Authorization, X-Requested-With, Origin'),
    ('Access-Control-Allow-Credentials', 'true'),
]


def application(environ, start_response):
    method = environ.get('REQUEST_METHOD', 'GET')
    path = environ.get('PATH_INFO', '/')
    logger.info(f"Request: {method} {path}")

    # Responder preflight OPTIONS directamente
    if method == 'OPTIONS':
        start_response('200 OK', CORS_HEADERS)
        return [b'']

    try:
        async def run():
            scope = {
                'type': 'http',
                'asgi': {'version': '3.0'},
                'http_version': '1.1',
                'method': method,
                'path': path,
                'query_string': environ.get('QUERY_STRING', '').encode('utf-8'),
                'root_path': '',
                'scheme': environ.get('wsgi.url_scheme', 'https'),
                'server': (environ.get('SERVER_NAME', 'localhost'), int(environ.get('SERVER_PORT', '443'))),
                'client': (environ.get('REMOTE_ADDR', '127.0.0.1'), 0),
                'headers': [],
            }

            for key, value in environ.items():
                if key.startswith('HTTP_'):
                    header_name = key[5:].lower().replace('_', '-').encode('utf-8')
                    scope['headers'].append((header_name, value.encode('utf-8')))
                elif key == 'CONTENT_TYPE':
                    scope['headers'].append((b'content-type', value.encode('utf-8')))
                elif key == 'CONTENT_LENGTH':
                    scope['headers'].append((b'content-length', value.encode('utf-8')))

            # Leer body de forma segura
            try:
                content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
            except (ValueError, TypeError):
                content_length = 0

            if content_length > 0:
                body = environ['wsgi.input'].read(content_length)
            else:
                body = b''

            status_code = 200
            response_headers = []
            response_body = BytesIO()

            async def receive():
                return {'type': 'http.request', 'body': body}

            async def send(message):
                nonlocal status_code, response_headers
                if message['type'] == 'http.response.start':
                    status_code = message['status']
                    response_headers = [
                        (k.decode('utf-8'), v.decode('utf-8'))
                        for k, v in message.get('headers', [])
                    ]
                elif message['type'] == 'http.response.body':
                    response_body.write(message.get('body', b''))

            await app(scope, receive, send)
            return status_code, response_headers, response_body.getvalue()

        loop = asyncio.new_event_loop()
        status_code, headers, body = loop.run_until_complete(run())
        loop.close()

        # Agregar headers CORS a todas las respuestas
        headers.extend(CORS_HEADERS)

        logger.info(f"Response: {status_code} for {method} {path}")
        start_response(f'{status_code}', headers)
        return [body]

    except Exception as e:
        logger.error(f"Error processing {method} {path}: {str(e)}")
        logger.error(traceback.format_exc())
        error_headers = [('Content-Type', 'application/json')] + CORS_HEADERS
        start_response('500', error_headers)
        return [f'{{"error": "{str(e)}"}}'.encode('utf-8')]
