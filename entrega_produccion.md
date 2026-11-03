# MotorDesk — entrega del 3 de noviembre de 2026

## Instalación local

1. Instala **Python 3.14 de 64 bits**, con el lanzador `py`, desde https://www.python.org/downloads/.
2. Extrae **todo** el ZIP en una carpeta propia; no ejecutes dentro del ZIP.
3. Abre `MotorDesk.cmd`. La primera instalación requiere Internet para descargar las dependencias fijadas en `requirements.lock`.
4. El asistente inicial permite crear el taller y su administrador. No existe una contraseña universal.

El ZIP incluye backend, web compilada y catálogo completo de vehículos y términos de repuestos. Python y las dependencias se instalan aparte; el espacio instalado y las descargas iniciales superan 10 MB. Tras instalar, el núcleo funciona sin conexión; los mensajes externos requieren conexión y credenciales propias.

La modalidad local escucha solamente en `127.0.0.1:8000`. Los datos y claves quedan en `%LOCALAPPDATA%\MotorDesk`; conserva esa carpeta y los respaldos fuera del ZIP. Antes de actualizar, cierra MotorDesk y crea un respaldo. Extrae cada entrega en una carpeta nueva: los datos del taller permanecen fuera de la aplicación.

## Docker / PostgreSQL

Con Docker Desktop abierto y Python 3.14 instalado, ejecuta `MotorDesk-Docker.cmd`. La primera construcción requiere Internet. El lanzador solicita una contraseña propia y genera secretos aleatorios fuera de la aplicación. La dirección es `http://127.0.0.1:8010`. `Detener-Docker.cmd` detiene los servicios sin borrar el volumen.

Las modalidades local y Docker tienen bases independientes y no sincronizan datos automáticamente.

## Respaldo local

Con el servidor local cerrado, desde la carpeta extraída:

```powershell
py -3.14 -I iniciar.py --action backup --file C:\Respaldos\motordesk.json
py -3.14 -I iniciar.py --action check
```

La restauración exige un destino nuevo: después de instalar dependencias, usa ` .venv\Scripts\python.exe -I app\backend\local_entry.py restore --file C:\Respaldos\motordesk.json --data-dir C:\MotorDeskRestaurado`. Arranca con el mismo `--data-dir`. No reemplaces una base existente sin verificar primero el respaldo y la restauración.

## Alcance de la entrega

Incluye el recorrido cliente → vehículo → orden. Las autorizaciones de costos, cantidades de inventario y entregas siguen siendo decisiones explícitas del usuario. La ampliación de todos los demás botones de creación a recorridos encadenados no está terminada.

La entrega se valida para ejecución local y Docker con datos sintéticos. No constituye una certificación de cumplimiento tributario, de todos los requisitos académicos ni de operación a escala. Antes de exponerla a Internet se necesita un destino de despliegue, HTTPS en un proxy, restricciones de acceso, respaldos externos y supervisión. El paquete no publica puertos en todas las interfaces.

Consulta `docs/validacion_entrega_20261103.md` en el repositorio para resultados y límites de las pruebas. No se incluyen datos de clientes, credenciales, exportaciones reales ni respaldos. Las licencias y fuentes de los catálogos están en `app/backend/app/resources/catalog`; los avisos de dependencias de Flutter están en `app/build/web/assets/NOTICES`.
