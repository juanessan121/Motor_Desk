> Informe de la versión previa al prompt maestro. Para el código y paquetes actualizados consulte `avance_prompt_maestro.md` y `matriz_prompt_maestro.md`.

# Verificación de MotorDesk — 23 de octubre de 2026

## Resultado de esta continuación

La distribución recomendada es **MotorDesk-Windows-Runtime-x64.zip**: CPython original firmado, dependencias, backend y web local. Se inicia con `MotorDesk.cmd`, sin instalar Python, Flutter ni Docker en el equipo receptor. El primer inicio abre un asistente en el navegador para crear taller y administrador. La firma corresponde al intérprete; no se afirma que todo el ZIP sea un instalador firmado.

El paquete PyInstaller anterior quedó bloqueado por Control de aplicaciones. Se mantiene como artefacto histórico y no es la distribución recomendada. No se deshabilitaron controles de Windows ni se modificaron los binarios firmados de Python.

## Evidencia

| Prueba | Resultado |
| --- | --- |
| Suite backend Windows de la entrega anterior | 218 aprobadas, 3 omitidas |
| Pruebas locales adicionales Windows | 8 aprobadas: arranque, persistencia, respaldo/restauración, exclusión de secretos, bloqueo de instancia, asistente HTTP y SMTP real de ensayo |
| Las mismas pruebas locales en Linux sin red | 8 aprobadas |
| Suite backend final en Linux sin red | **221 aprobadas, 3 omitidas** |
| Suite Flutter de la entrega anterior | 129 aprobadas + 1 prueba adicional contra activación del modo simulado |
| ZIP Windows con runtime incluido | Descomprimido en ruta con espacios; PATH reducido a System32 y sin PYTHONPATH/PYTHONHOME; inicialización, login, cliente, vehículo, orden, notificaciones pendientes, JSON, reinicio y restauración correctos; lanzador CMD y rutas internas de Python/librerías comprobados |
| ZIP técnico en Linux sin red | Extraído en carpeta temporal, web montada solo lectura; recorrido HTTP completo, reinicio, respaldo y restauración correctos |
| Docker desde cero | Dockerfile principal construido desde `python:3.14-slim`, dependencias fijadas, sin modelos ONNX obligatorios |
| Docker con base vacía | Migraciones hasta 0014; salud, login, cliente, vehículo, orden y avisos pendientes correctos |
| Reinicio y respaldo PostgreSQL | Volumen conservado; `pg_dump` restaurado con `pg_restore` en otra base, orden comprobada |
| Entregable académico | JSON con datos sintéticos validado contra el schema del repositorio |
| Firma CPython distribuido | Authenticode válido antes y después de copiar el intérprete |

La suite completa inicial en Linux detectó una dependencia oculta de desarrollo: `jsonschema` no estaba declarada. Se añadieron esta dependencia y sus dependencias transitivas con versiones fijas al lockfile; la imagen final se reconstruyó con ellas y superó la suite completa. Los logs de la ejecución están en `build/` y no se distribuyen como datos del taller.

## Protección y funcionamiento

- Una sola API y los mismos modelos para SQLite/PostgreSQL. No se migró la base existente ni se modificó el `.env` privado.
- El motor demostrativo del navegador permanece deshabilitado por defecto y no se activa por una caída de conexión.
- El asistente escucha únicamente en 127.0.0.1, emplea un token aleatorio de un solo uso, rechaza orígenes ajenos y caduca a los quince minutos. No carga recursos de internet ni registra contraseñas o tokens en logs.
- Los respaldos se publican solo después de escribir y sincronizar un JSON completo. No reemplazan archivos existentes. En Windows se utiliza renombrado exclusivo para no exigir enlaces duros en memorias USB.
- La restauración valida en una base temporal y publica únicamente el resultado íntegro en un destino nuevo. No fusiona instalaciones ni sustituye automáticamente una base existente.
- Se conservan hashes de contraseñas, pero se excluyen las claves del servidor, las credenciales de proveedores, dispositivos y accesos temporales. Los mensajes normales se vuelven a cifrar al restaurar.
- Ocho plantillas orientativas, precios por configurar. Catálogos manuales/importados y búsqueda textual local. Modelos semánticos opcionales: `INCLUDE_EMBEDDINGS=true` al construir Docker.
- SMTP probado con un servidor de ensayo local que habla el protocolo real. No se enviaron mensajes a personas ni se utilizaron cuentas externas.

## Matriz académica disponible

| Fase | JSON | Evidencia |
| --- | --- | --- |
| Clientes | `clientes` | Registro, persistencia y schema |
| Vehículos | `vehiculos` | Propietario, persistencia y schema |
| Mantenimiento | `mantenimientos` | Orden, actividades, precios, checklist y pruebas del taller |
| Seguimiento | `seguimiento_estados` | Exportación y pruebas de transiciones |
| Notificaciones | `notificaciones` | Pendientes sin proveedor, SMTP local, trazabilidad y schema |

`ejemplo_academico_sintetico.json` no contiene datos reales ni accesos temporales. Este informe precede al prompt maestro de 60 puntos recibido posteriormente. Su evaluación actualizada está en `matriz_prompt_maestro.md`.

## Límites pendientes

1. El ZIP Windows funciona con su propio runtime en este equipo, pero **falta probarlo en otra PC o una VM Windows limpia**. Windows Sandbox no está instalado y no hay certificados de firma propios disponibles; ninguno es necesario para el runtime oficial ya firmado. No se certifica aún el funcionamiento en todas las políticas corporativas o versiones de Windows.
2. Linux se verificó en un contenedor x64 sin red, no en un escritorio Linux ni con instalador gráfico.
3. Telegram y SMTP con cuentas externas reales requieren un entorno de ensayo autorizado. WhatsApp conserva la gestión manual; no tiene proveedor de envío implementado.
4. La configuración posterior de integraciones es por archivo. No hay sincronización entre instalaciones; acceso LAN significa compartir un servidor con permisos y red configurados explícitamente.
5. SMTP/Telegram no garantizan exactamente una entrega si el proceso cae después de la aceptación externa. Copiar un mensaje no lo marca enviado.
6. SQLite tiene baseline local v1 y rechaza esquemas incompatibles. Futuras versiones necesitan migraciones locales explícitas; no se convierte PostgreSQL automáticamente.
7. No se redistribuyen catálogos externos sin revisar sus licencias. La importación operativa JSON restaura un respaldo completo; no interpreta el JSON académico como una copia operativa.

## Reproducción

```powershell
.venv\Scripts\python -m pytest backend/tests -q --basetemp=build/pytest-nuevo
flutter test
flutter build web --release --no-web-resources-cdn
powershell -File scripts/package-runtime-windows.ps1 -OutputDirectory dist/MotorDesk-Runtime-nueva
.venv\Scripts\python scripts/test_portable_package.py --runtime --package dist/MotorDesk-Windows-Runtime-x64.zip --output 'build/prueba Windows nueva'
docker build --pull --no-cache -t motordesk-validacion -f backend/Dockerfile backend
.venv\Scripts\python scripts/prepare_docker_portability.py --directory build/docker-nuevo --project motordesk-test-nuevo --image motordesk-validacion
docker compose -p motordesk-test-nuevo --env-file build/docker-nuevo/test.env -f build/docker-nuevo/compose.yaml up -d --wait
.venv\Scripts\python scripts/test_docker_portability.py --directory build/docker-nuevo
```

Las pruebas Docker usan datos, claves y volúmenes sintéticos independientes. El arranque de Docker Desktop también puede iniciar servicios existentes por su política de reinicio; no se actualizó ni restauró la base del taller. Se conservaron los cambios previos sin confirmar y no se crearon commits.
