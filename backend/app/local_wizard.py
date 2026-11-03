"""Asistente local efímero: solo loopback, token único y sin recursos externos."""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import time
from urllib.parse import parse_qs
import webbrowser

FORM = '''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Configurar MotorDesk</title>
<style>body{font:17px system-ui;background:#f4f2ee;color:#202b36;margin:0;padding:24px}main{max-width:560px;margin:4vh auto;background:white;border-radius:18px;padding:32px;box-shadow:0 10px 40px #101b2e15}h1{font-size:30px}label{display:block;margin:18px 0 6px}input{box-sizing:border-box;width:100%;padding:12px;border:1px solid #8996a8;border-radius:8px;font:inherit}button{margin-top:24px;background:#2563eb;color:white;border:0;border-radius:8px;padding:14px 20px;font:inherit;width:100%}.error{color:#a12a26}small{display:block;line-height:1.6;color:#526174}fieldset{border:0;padding:0}input:focus,button:focus{outline:3px solid #90b5ff;outline-offset:2px}</style>
<main><small>MOTORDESK · CONFIGURACIÓN INICIAL</small><h1>Prepara tu taller</h1>
<p>Tu información se guarda en este equipo. Puedes comenzar sin internet ni servicios de mensajería.</p>
<p class="error" role="alert">{error}</p>
<form method="post" action="/{token}" autocomplete="on"><fieldset>
<label for="name">Nombre del taller</label><input id="name" name="name" required maxlength="100" autocomplete="organization">
<label for="email">Correo del administrador</label><input id="email" name="email" type="email" required maxlength="254" autocomplete="email">
<label for="password">Contraseña personal</label><input id="password" name="password" type="password" required minlength="12" maxlength="256" autocomplete="new-password">
<label for="confirm">Repite la contraseña</label><input id="confirm" name="confirm" type="password" required minlength="12" maxlength="256" autocomplete="new-password">
<p><small>Usuario de acceso: <strong>admin</strong>. Se preparan ocho plantillas de mantenimiento; configura sus precios antes de usarlas. Las preferencias e integraciones pueden ajustarse después.</small></p>
<button type="submit">Crear taller y continuar</button></fieldset></form></main></html>'''


def create_server(factory):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Ni el token ni datos de configuración se escriben en logs.

        def reply(self, status, message='', form=False):
            content = (FORM.replace('{token}', token).replace('{error}', escape(message)) if form else
                       '<!doctype html><html lang="es"><meta charset="utf-8"><title>MotorDesk</title><p>' + escape(message) + '</p></html>').encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(content)

        def permitted(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            return (self.headers.get('Host') == expected and
                    secrets.compare_digest(self.path, '/' + token) and
                    not self.server.completed and time.monotonic() < self.server.expires)

        def do_GET(self):
            if not self.permitted():
                self.reply(404, 'Asistente no disponible.'); return
            self.reply(200, form=True)

        def do_POST(self):
            if not self.permitted():
                self.reply(403, 'Solicitud no autorizada.'); return
            origin = self.headers.get('Origin')
            if origin and origin != f'http://127.0.0.1:{self.server.server_port}':
                self.reply(403, 'Origen no autorizado.'); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    self.reply(400, 'Formulario no válido.'); return
                values = parse_qs(self.rfile.read(length).decode('utf-8'), max_num_fields=4)
                if set(values) != {'name', 'email', 'password', 'confirm'} or any(len(v) != 1 for v in values.values()):
                    self.reply(400, 'Complete todos los campos.', form=True); return
                values = {key: value[0] for key, value in values.items()}
                if values['password'] != values['confirm']:
                    self.reply(422, 'Las contraseñas no coinciden.', form=True); return
                from .local import setup
                setup(factory, values['name'], values['email'], values['password'])
            except ValueError:
                # Pydantic puede incluir el valor original: no devolver entradas sensibles.
                self.reply(422, 'Revise el nombre, el correo y la contraseña (12 a 256 caracteres).', form=True); return
            except Exception:
                self.reply(500, 'No se pudo guardar la configuración. Revise la consola y vuelva a intentarlo.', form=True); return
            self.server.completed = True
            self.reply(200, 'Taller creado. Puede cerrar esta pestaña; MotorDesk se abrirá automáticamente.')

    class LocalServer(HTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(5)
            return connection, address

    server = LocalServer(('127.0.0.1', 0), Handler)
    server.timeout = 1
    server.completed = False
    server.expires = time.monotonic() + 900
    return server, f'http://127.0.0.1:{server.server_port}/{token}'


def run_wizard(factory):
    server, url = create_server(factory)
    with server:
        print('Configuración inicial. Abra este enlace si el navegador no se abre:\n' + url)
        webbrowser.open(url)
        while not server.completed and time.monotonic() < server.expires:
            server.handle_request()
        if not server.completed:
            raise RuntimeError('El asistente caducó. Inicie MotorDesk otra vez para continuar.')
