# MotorDesk Local — instalación y uso

**Distribución recomendada: `MotorDesk-Windows-Runtime-x64.zip`.** Incluye el intérprete CPython original con firma válida, las dependencias y la interfaz local. Se probó el ZIP descomprimido con PATH reducido, sin utilizar el Python del proyecto. El ejecutable PyInstaller anterior continúa bloqueado y no es la vía recomendada. No cambie políticas de seguridad.


MotorDesk Local utiliza Flutter Web, la misma API FastAPI y SQLite persistente. No requiere Docker, API externas ni internet para operar. PostgreSQL y Compose se mantienen como modalidad de servidor. No hay sincronización automática entre instalaciones.

## Windows, usuario final

El mismo ZIP ofrece dos opciones:

- **MotorDesk.cmd:** recomendada para uso individual. Incluye Python y SQLite;
  no requiere instalar Python, Flutter ni Docker. Tras descomprimir puede operar sin internet.
- **MotorDesk-Docker.cmd:** opción con PostgreSQL para quien tenga Docker Desktop
  instalado y abierto. La primera construcción necesita internet para imágenes y
  dependencias; solicita una contraseña propia. Abre http://127.0.0.1:8010.
  `Detener-Docker.cmd` detiene los servicios sin borrar los datos.

Son instalaciones independientes: local usa `%LOCALAPPDATA%\MotorDesk`, y Docker
el volumen del proyecto `motordesk-portable`. No se mezclan ni sincronizan los datos.
La configuración privada de Docker queda en `%LOCALAPPDATA%\MotorDeskDocker`.
No envíe esas carpetas de datos ni contraseñas con el ZIP de distribución.

En **Notificaciones → Editar correo o Telegram** puede buscar al cliente, cambiar
su contacto y guardar. También puede usar el icono de edición de cada mensaje.
Telegram requiere el ID numérico del chat y que el cliente haya iniciado el bot;
no acepta un nombre `@usuario`. Sin proveedor configurado los mensajes se conservan pendientes.

Descomprima **toda** la carpeta del ZIP `MotorDesk-Windows-Runtime-x64.zip` en una carpeta propia y ejecute `MotorDesk.cmd`. Conserve todas las carpetas: `runtime` contiene Python y librerías; `backend`, la API; `build/web`, la interfaz. El asistente en el navegador solicita el nombre del taller, correo y contraseña personal de al menos 12 caracteres; el usuario es `admin`. Se incluyen ocho plantillas de mantenimiento orientativas; configure precios y compruebe especificaciones del fabricante antes de utilizarlas. No se incluyen clientes reales ni credenciales universales.

El navegador se abre cuando el servidor está disponible en http://127.0.0.1:8000. Mantenga la consola abierta mientras trabaja; cierre con Ctrl+C. Los datos permanecen en `%LOCALAPPDATA%\MotorDesk`. Cambiar o borrar la carpeta del programa no borra esos datos. No abra dos instancias sobre la misma carpeta. Para usar otro puerto: `MotorDesk.cmd --port 8010`.

El asistente inicial del navegador configura nombre y administrador con un enlace local de un solo uso; los datos de marca y preferencias se ajustan posteriormente en la aplicación. Las integraciones son opcionales y se configuran posteriormente por archivo. `--no-browser` conserva la configuración por consola para servidores sin interfaz gráfica.

La primera ejecución prepara el catálogo de referencia incluido; puede tardar más que los arranques posteriores. No requiere red. No sobrescribe un catálogo existente. Las licencias, atribuciones y fuentes originales están en `backend/app/resources/catalog`. Los precios y existencias se registran en el taller.

Desde Administración puede configurar el impuesto de nuevas órdenes. Los clientes sin portal pueden autorizar el servicio base presencialmente: el administrador registra la constancia desde la orden.

## Operación diaria

1. Ingrese como administrador. Registre clientes y vehículos desde Registro.
2. Configure las plantillas y sus precios. Cree una orden y seleccione el vehículo y las actividades.
3. Registre recepción, aprobación y asignación; complete el checklist y revisión antes de entregar.
4. Consulte historial y Notificaciones. Sin proveedor, los mensajes permanecen pendientes; no equivalen a envíos confirmados.
5. Exporte el JSON académico con la función existente de exportación. Es distinto del respaldo operativo.

## Respaldo y restauración

Cierre MotorDesk y ejecute `Respaldar.cmd`. El respaldo JSON se escribe en la carpeta de datos con fecha y hora. También puede usar `Respaldar.cmd --file "D:\Copias\taller.json"`. Nunca se reemplaza un archivo existente. La carpeta de destino debe existir.

`Restaurar.cmd` solicita una carpeta NUEVA y un archivo de respaldo. La restauración valida formato, versión, tablas, columnas, restricciones y claves foráneas en una base temporal antes de publicar el resultado. No fusiona ni sobrescribe una instalación existente. Abra después `MotorDesk.cmd --data-dir "D:\TallerRecuperado"`. Verifique sus datos antes de decidir qué instalación conservar. La importación operativa JSON reproduce los registros y sus identificadores; importar dos veces al mismo destino es rechazado.

Incluye clientes, vehículos, órdenes, checklist, fotografías en base64, historial, catálogos, stock, permisos, auditoría y configuración. Conserva hashes de contraseñas, nunca contraseñas en claro. Excluye dispositivos autorizados, tokens de activación y mensajes de credenciales temporales; regenere estos últimos después de restaurar. Los mensajes normales pendientes se vuelven a cifrar con la nueva clave. No contiene `server.key`, JWT ni credenciales SMTP/Telegram. Proteja el respaldo: contiene información personal del taller. El JSON académico no sirve como copia operativa ni se importa como tal.

## Integraciones posteriores

Copie `integrations.example.json` a la carpeta de datos como `integrations.json`, rellene únicamente los proveedores que utilice y reinicie. SMTP requiere host, remitente y credenciales cuando corresponda. Telegram requiere token y el chat_id del cliente. WhatsApp conserva enlaces de redacción; no hay proveedor de envío implementado. No marque un enlace abierto como envío confirmado. Guarde este archivo fuera del código y de los paquetes. Restrinja el acceso a la carpeta de datos a su cuenta de Windows.

Los fallos de proveedores no impiden guardar las operaciones. El worker utiliza el mismo registro al reintentar. SMTP y Telegram no garantizan exactamente una entrega si el proveedor acepta el mensaje y el proceso cae antes de confirmar en la base; revise el destinatario antes de reintentar un resultado ambiguo.

## Paquete técnico

Windows: Python 3.14 y Flutter compatible con `pubspec.lock` previamente instalados. Desde la raíz:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.lock
flutter pub get
flutter build web --release --no-web-resources-cdn
.\MotorDesk.cmd
```

La preparación descarga dependencias; una vez empaquetado no se necesitan estas herramientas en el taller. Para reconstruir la distribución recomendada ejecute `scripts/package-runtime-windows.ps1 -OutputDirectory dist/MotorDesk-Runtime-nueva`. El script verifica la firma del intérprete base y la de su copia. No necesita PyInstaller ni un certificado propio. El paquete no está firmado como un instalador: la firma corresponde al intérprete original. No compile con `ENABLE_BROWSER_DEMO=true`: ese motor es solo demostrativo, está deshabilitado por defecto y no sustituye la API al perder conexión.

Linux: se proporciona `sh scripts/start-local.sh`, con `.venv/bin/python` y la web compilada. El backend y el ZIP técnico se probaron en Linux x64 dentro de un contenedor sin red, incluyendo HTTP, reinicio, respaldo y restauración. No se ha probado una distribución de escritorio Linux ni un instalador gráfico.

## Actualización y esquema

Detenga el servidor, cree un respaldo, conserve la versión anterior y descomprima el nuevo programa en otra carpeta. Use una copia restaurada para comprobar la actualización antes de utilizar los datos originales. SQLite inicia con baseline local versión 1, correspondiente a los modelos de esta entrega. Se rechazan bases sin versión o con una versión distinta; no se ejecutan sobre SQLite las migraciones históricas específicas de PostgreSQL. Futuras modificaciones del esquema necesitan una nueva migración local explícita y pruebas de preservación. No se convierte automáticamente la base PostgreSQL existente.

## Docker y red local

La modalidad PostgreSQL mantiene `scripts/configure.ps1`, `compose.yaml` y Alembic. Compile la web sin CDN y ejecute `docker compose up --build -d`. La descarga y construcción de imágenes requieren internet inicialmente. Los modelos de IA se excluyen por defecto; habilite `--build-arg INCLUDE_EMBEDDINGS=true` únicamente si desea hornearlos en la imagen; operar con imágenes y volúmenes preparados no. `docker compose logs --tail 80 api` muestra logs; `docker compose ps` muestra salud. Los puertos se configuran con `MOTORDESK_PORT` y `MOTORDESK_DB_PORT`; ambos enlazan solo loopback por defecto. Respalde PostgreSQL con `pg_dump` y restaure en una base nueva con la misma versión y extensiones; el respaldo JSON local está limitado a SQLite.

El lanzador local atiende solo 127.0.0.1. Acceso LAN requiere configurar un servidor central, firewall, TLS y orígenes explícitos; los dispositivos comparten esa base, no sincronizan instalaciones. No se habilita publicación de red automáticamente.

## Problemas frecuentes

- Puerto ocupado: cierre otra instancia o use `--port 8010`.
- Falta interfaz: use el ZIP completo o compile Flutter Web como se indica arriba.
- Error de conexión en el navegador: compruebe la consola; reintente. No se activa una base ficticia.
- Esquema incompatible: use la versión que creó los datos; no cambie manualmente `user_version`.
- Notificación pendiente: revise preferencias del cliente, credenciales y conectividad; reanude desde Notificaciones.
- Restauración rechazada: utilice una carpeta sin `motordesk.db`, con una copia operativa de esta versión.

Consulte `portabilidad_resultados.md` para las comprobaciones realmente ejecutadas y las pendientes.
