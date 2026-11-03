# Notificaciones y distribución — 25/10/2026

## Uso

MotorDesk se mantiene en http://127.0.0.1:8000 en la instalación existente.
Si la pestaña estaba abierta, recargue para obtener la interfaz actualizada.

En Notificaciones, **Editar correo o Telegram** abre el directorio de clientes.
El icono de edición de cada mensaje abre directamente el contacto correspondiente.
Correo y Telegram están visibles; WhatsApp y los interruptores por canal se
encuentran en Opciones de envío. Los cambios se aplican al pulsar Guardar.
Cancelar, incluso después de pulsar Desvincular, no modifica datos persistidos.
Guardar actualiza el cliente y el destino de sus mensajes pendientes sin duplicarlos.

Telegram necesita el ID numérico del chat y un bot configurado en el servidor;
un nombre @usuario no sustituye ese identificador. Sin proveedor configurado,
los mensajes permanecen pendientes y se pueden consultar/copiar.

## Un ZIP, dos modalidades

`MotorDesk-Windows-Runtime-x64.zip` incluye la interfaz compilada, backend,
CPython firmado, dependencias y catálogo de referencia.

- `MotorDesk.cmd`: funcionamiento local con SQLite, sin instalar Python,
  Flutter ni Docker. Asistente inicial para taller y administrador.
- `MotorDesk-Docker.cmd`: requiere Docker Desktop instalado y abierto.
  Solicita una contraseña propia en la primera ejecución; construye la imagen
  y abre el puerto 8010. La primera construcción requiere internet.
- `Detener-Docker.cmd`: detiene esa instalación Docker, sin borrar el volumen.
- `Respaldar.cmd` y `Restaurar.cmd`: copias de la instalación local SQLite.
  Para PostgreSQL se conserva el procedimiento pg_dump/pg_restore técnico.

Local y Docker mantienen bases independientes; alternar lanzadores no transfiere
registros. El paquete técnico incluye código, migraciones, scripts y configuración.
No se incluyen datos ni credenciales del taller real. La prueba en una segunda PC
o VM Windows limpia sigue pendiente: el ZIP se verificó en una carpeta independiente
con PATH reducido en este equipo.

## Comprobaciones de esta revisión

- 25 pruebas backend: contactos, preferencias, flujo sin portal e importación
  incremental de clientes/vehículos con conflictos; aprobadas.
- 21 pruebas de interfaz/responsividad; aprobadas.
- 3 pruebas de edición/cancelación de contacto; aprobadas (dos incluidas en las 21).
- Compilación web release sin CDN obligatorio; aprobada.
- ZIP sin Docker: runtime propio con PATH reducido, catálogo, registros, reinicio,
  integridad y respaldo/restauración; aprobado.
- Compose incluido en el paquete: construcción real, migración 0015, login,
  cliente, vehículo, orden, reinicio, pg_dump y pg_restore; aprobado con datos sintéticos.

Evidencia en `build/notifications-*-20261025.log`. No se realizaron envíos reales
a contactos ni se certifica aquí el cierre de los 60 requisitos del prompt maestro.
La nueva API `/registry-transfer` solo intercambia clientes/vehículos (formato
`motordesk-registry`, versión 1), no importa órdenes académicas ni cuentas.


## Flujo principal automático (25 de octubre de 2026)

Desde Nuevo cliente se avanza al vehículo con su propietario seleccionado y luego a servicios y creación de orden. Al confirmar la orden se abre su detalle. Ingresar vehículo también continúa a la orden; si no existen clientes, empieza por el cliente. Cancelar detiene la secuencia y conserva los registros ya guardados. Editar registros existentes no inicia esta secuencia.

Se usan los identificadores devueltos por la API, sin deducirlos a partir de cambios en las listas. Pruebas del recorrido y cancelación en móvil y escritorio: `build/customer-flow-final-tests.log` (11 aprobadas junto a las de recepción); suite completa previa al ajuste final del encabezado: 134 aprobadas.
