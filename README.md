# MotorDesk · Taller conectado

## Entrega ligera (máximo 10 MB)

Descarga `MotorDesk-Final-10MB.zip` desde [Releases](https://github.com/juanessan121/Motor_Desk/releases).
Incluye la aplicación y el catálogo completo; requiere Python 3.14 x64 e Internet para instalar dependencias la primera vez.
Consulta [instalación y alcance](docs/entrega_produccion.md) y [validación de la entrega](docs/validacion_entrega_20261103.md).
La modalidad local es de un solo equipo; Docker utiliza PostgreSQL. La exposición pública a Internet requiere desplegar y configurar HTTPS por separado.

Para reconstruir el ZIP desde este repositorio: `flutter pub get`, `flutter build web --release --no-web-resources-cdn` y `python scripts/package_lightweight.py`.
El empaquetador rechaza archivos privados y entregas mayores de 10.000.000 bytes.

Panel administrativo Flutter Web y aplicación de clientes Flutter Android, con **una única API FastAPI y persistencia PostgreSQL (servidor) o SQLite (instalación local)**. El mismo código Flutter decide qué espacio mostrar por el rol autenticado, no por la plataforma. No hay datos de muestra precargados ni conexión directa de Flutter a la base.

## MotorDesk Local, sin Docker

Consulte [instalación, respaldo y distribución](docs/instalacion_local.md) y [resultados de portabilidad](docs/portabilidad_resultados.md). El lanzador `MotorDesk.cmd` inicia SQLite y FastAPI; el paquete `MotorDesk-Windows-Runtime-x64.zip` incluye CPython firmado, dependencias e interfaz y se inicia con su `MotorDesk.cmd`. El primer inicio abre un asistente local en el navegador. Los datos reales nunca cambian automáticamente a una simulación del navegador al perder la conexión.

## 1. Arranque servidor: PostgreSQL + API + Web

Requisitos: Docker Desktop iniciado y Flutter estable con Dart 3.11 o posterior. Agregue Flutter a `PATH` según su instalación.

Desde la raíz, en PowerShell:

```powershell
# Solo la primera vez. No sobrescribe un .env existente.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/configure.ps1

flutter pub get
flutter build web --release
docker compose up --build -d
```

- **Panel:** http://localhost:8000
- **API / Swagger (solo desarrollo):** http://localhost:8000/docs; deshabilitado en producción
- **Salud real de la base:** http://localhost:8000/api/v1/health
- **Usuario inicial:** `admin`. Su contraseña aleatoria está en `ADMIN_PASSWORD` de `.env`; se exige cambiarla al entrar.
- En **Protege tu cuenta**, el primer campo corresponde a esa contraseña temporal. Escribe una contraseña nueva de al menos 12 caracteres y repítela en el tercer campo. Los campos siguen editables después de una validación o un error del servidor; `Volver al inicio de sesión` permite salir sin cambiar datos.
- La imagen ejecuta `alembic upgrade head` y el bootstrap idempotente. Reiniciar no reemplaza el administrador ni sus contraseñas.
- PostgreSQL conserva la información en el volumen `app_web_1_workshop_data`. Detener con `docker compose stop` **no** borra los datos.

```powershell
docker compose logs --tail 80 api
docker compose ps
```

Para desarrollar Flutter con hot reload y la misma API:

```powershell
flutter run -d edge --web-port 8080 --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

Los puertos Docker están vinculados a `127.0.0.1`, no a toda la red. Para un teléfono físico se debe publicar una API HTTPS accesible desde el teléfono. El emulador Android puede utilizar `10.0.2.2` en debug.

## 2. Arquitectura y archivos editables

```text
lib/
  main.dart                         # SystemChrome / edge-to-edge
  app.dart                          # Providers, tema global, sesión y roles
  core/
    config/
      app_config_model.dart         # Contrato JSON, flags, colores y serialización
      theme_controller.dart         # Lectura, caché pública, publicación y ThemeData
    network/api_client.dart         # REST, Bearer, fotos privadas, SSE y errores
    models/entities.dart            # Cliente, vehículo, catálogo y orden
    state/workshop_controller.dart  # Sesión en memoria, refresco y eventos
  features/
    auth/login_page.dart            # Login y cambio obligatorio de contraseña
    dashboard/                      # Sidebar adaptable y resumen con datos reales
    registry/                       # CRUD y formularios de clientes/vehículos/catálogos
    orders/                         # Checklist, cotizaciones, evidencias y entrega
    branding/branding_page.dart     # Editor visual, selector HSV, logo y permisos
    notifications/                  # Estado de proveedores y reintentos
    customer/customer_home.dart     # Slivers, navegación y pull-to-refresh Android/Web
  shared/                           # Tablas con búsqueda/orden/páginas y diálogos
backend/
  app/
    main.py                         # API, CORS, archivos Web y cabeceras
    settings.py                     # Variables de entorno y controles de producción
    models.py                       # Esquema ORM y relaciones
    schemas.py                      # Validación de entradas y dinero decimal
    security.py                     # Argon2id, JWT, cifrado y limitación de intentos
    dependencies.py                 # Transacciones, roles y dispositivo autenticado
    auth_routes.py
    registry_routes.py
    config_routes.py
    order_routes.py
    operations_routes.py
    serializers.py                  # DTO sin hashes ni payloads privados
    branding.py                     # Contrato y precedencia de flags
    events.py                       # Invalidaciones SSE autenticadas
    notifications.py                # Outbox persistente, Telegram y SMTP
    bootstrap.py                    # Administrador y JSON inicial
  migrations/versions/0001_initial_schema.py
  migrations/versions/0002_query_indexes.py
  schema.sql                        # DDL completo PostgreSQL, incluidas FK circulares
  scripts/export_schema.py          # Regeneración reproducible del DDL
  tests/                            # Flujos de negocio y aislamiento por cuenta
compose.yaml
scripts/configure.ps1
.env.example
pubspec.yaml
android/app/build.gradle.kts
android/app/src/main/AndroidManifest.xml
android/app/src/debug/AndroidManifest.xml
web/index.html
```

`pubspec.lock` fija las versiones Flutter resueltas. `backend/requirements.txt` declara rangos compatibles; `backend/requirements.lock` registra el entorno Python validado. No guardes `.env`, claves de firma ni tokens de proveedores en Git.

## 3. Base central y relaciones

| Tabla | Responsabilidad |
|---|---|
| `users` | Usuario único, correo único, hash Argon2id, rol, revocación y contraseña temporal |
| `customers` | Cédula única, nombre, apellido, dirección, teléfono, correo y canal de contacto |
| `vehicles` | Varios vehículos por cliente, placa/VIN únicos y kilometraje |
| `ownership_history` | Propietario anterior/nuevo, actor y fecha del traspaso |
| `maintenance_catalogs`, `catalog_tasks` | Precio base decimal y lista ordenada de tareas |
| `maintenance_versions` | Versiones de plantillas, intervalos y condiciones; las órdenes guardan su propia copia |
| `work_orders` | Vehículo, pagador, datos de cobro congelados, precio base y estado |
| `checklist_items` | Copia de tareas; responsable y fecha de finalización |
| `extra_quotes`, `quote_options` | Variantes con precio, decisión y opción elegida |
| `intake_photos` | JPEG privado en BYTEA, descripción, autor y fecha |
| `app_configurations` | JSON global, por usuario o por dispositivo, con revisión |
| `devices` | Instalaciones registradas al autenticar, vinculadas al token |
| `notifications` | Outbox cifrado, estado, intentos, próximo intento y error seguro |
| `inbox_events` | Mensajes privados visibles en la app, nunca contraseñas |
| `part_requests`, `stock_items`, `stock_movements` | Solicitudes por actividad, existencia física y entregas sin doble descuento |

La instalación y actualización se hacen con **Alembic hasta head**. [`backend/schema.sql`](backend/schema.sql) es una instantánea histórica, no sustituye las migraciones actuales; no debe ejecutarse además de ellas ni marcarse como esquema actual. Las FK de consulta tienen índices y un índice parcial único impide dos órdenes abiertas por vehículo incluso fuera de la API.

Los precios usan `NUMERIC(12,2)` / `Decimal`, se transmiten como cadenas y no dependen de cálculos de punto flotante del teléfono. Moneda de esta entrega: USD; los importes son valores de servicio, **no facturación tributaria ni integración con SRI**.

### Reglas de negocio implementadas

1. Crear cliente genera usuario y contraseña aleatoria, guarda solo el hash de autenticación y encola el envío cifrado en la misma transacción. No devuelve la contraseña al navegador.
2. Una orden abierta por vehículo. Se copian nombre, tareas y precio del catálogo: editar el catálogo no reescribe órdenes anteriores.
3. Las actividades admiten pendiente, en proceso, completada, no aplica y atención. Solo las aplicables cuentan en el avance. Se requiere aceptación del pagador para ejecutar; las órdenes nuevas terminan en revisión administrativa antes de quedar listas. No puede haber autorizaciones ni solicitudes de material pendientes. Repetir un check no duplica el aviso.
4. Solo el cliente pagador puede aprobar/rechazar una cotización de su orden. Una aprobación añade una tarea de instalación y suma exactamente la variante elegida. No se puede responder dos veces ni elegir una variante de otra cotización.
5. Nueva cotización reabre una orden lista; las órdenes entregadas/canceladas no admiten modificaciones.
6. Archivar clientes/vehículos/catálogos conserva las referencias históricas. No se desactiva a un cliente ni se traspasa/archiva un vehículo con órdenes abiertas.
7. Tras un traspaso, el nuevo propietario consulta el historial técnico resumido, **no** fotos, facturas, contacto o aprobaciones del anterior. El pagador original conserva sus órdenes.
8. Fotos de hasta 5 MB, máximo 12 por orden. El servidor comprueba la imagen, limita dimensiones, reorienta, reduce a 1920 px y elimina EXIF al convertir a JPEG. La descarga requiere autorización.

### Flujo operativo y paquetes por kilometraje

- **Mantenimientos**: crear/editar/duplicar plantillas, actividades, intervalos y condiciones. «Cargar plantillas de referencia» agrega de forma idempotente cinco servicios y paquetes de 5.000/10.000/20.000 km. No son programas oficiales del fabricante ni tienen precios inventados: hay que revisar sus condiciones y configurar el precio antes de usarlos.
- **Nueva orden**: buscar vehículo/propietario → elegir uno o varios servicios → confirmar. Permite registrar cliente y vehículo sin salir del flujo. Copia versiones, tareas y precio; ofrece sugerencias por kilometraje e historial conocido.
- **Orden**: responsables, checklist, solicitudes de material, cotizaciones, revisión y entrega en el mismo detalle. El mecánico solo recibe sus actividades; el cliente conserva las aprobaciones de costos.
- **Catálogo automotriz → Repuestos → Existencias físicas**: entradas reales y movimientos de inventario. El catálogo de referencia no es stock. «Revisar propuestas» sigue siendo una cola separada.
- **Vehículos → Vista del taller**: SVG con geometría guardada. Si falta un plano, ofrece configuración; no crea posiciones ni bahías ficticias al abrirse.

Diagnóstico, archivos, migraciones 0011/0012, respaldo, pruebas y límites:
[informe de optimización](docs/optimizacion_flujos_motordesk.md).

## 4. Motor Server-Driven UI

El documento global inicial es:

```json
{
  "schema_version": 1,
  "revision": 1,
  "branding": {
    "name": "MotorDesk",
    "tagline": "Tu taller, conectado.",
    "welcome": "Cuidamos lo que te mueve",
    "logo": "",
    "colors": {
      "primary": "#2563EB",
      "secondary": "#0D9488",
      "background": "#F4F6FA",
      "surface": "#FFFFFF"
    }
  },
  "features": {
    "vehicles": true,
    "maintenance": true,
    "quotes": true,
    "photos": true,
    "history": true
  }
}
```

- `GET /api/v1/public/config`: identidad pública para login; no contiene clientes ni overrides privados.
- `GET /api/v1/config`: configuración efectiva de la cuenta/dispositivo autenticado.
- `PUT /api/v1/config/global`: configuración completa con `expected_revision`, no con `revision`. Un conflicto devuelve 409 para evitar sobrescribir otra edición.
- `GET/PUT /api/v1/config/users/{user_id}`: `{ "features": { "photos": false } }`.
- `GET /api/v1/devices` y `PUT /api/v1/config/devices/{id}`: permisos de una instalación registrada.

La precedencia es **global AND cuenta AND dispositivo**. Un permiso de cuenta no puede reactivar un módulo bloqueado globalmente. La API también comprueba los permisos, no solo los widgets. El JWT del cliente queda vinculado al dispositivo; omitir/cambiar `X-Device-Id` no elude sus flags. El identificador es de instalación, no una atestación de hardware ni una herramienta MDM: una nueva instalación se registra como un dispositivo nuevo.

El código de publicación y reconstrucción, compartido por Web y Android, es:

```dart
// AppConfigModel.parseColor valida seis dígitos y añade alfa opaco.
final color = Color(int.parse('FF${hex.replaceFirst('#', '')}', radix: 16));

// ThemeController.save publica el borrador con control de revisión.
await api.request('PUT', '/config/global', body: draft.toSaveJson());

// ThemeController.refresh obtiene el JSON efectivo y notifica a MaterialApp.
await themeController.refresh();
// MaterialApp(theme: themeController.theme, ...)
// if (themeController.config.enabled('photos')) ...
```

El editor incluye colores Hex/HSV, imágenes PNG/JPEG/WebP Base64 de hasta 256 KB y 2048 px por lado o URL HTTPS, textos y vista previa Android. Para URL remota, el alojamiento de imágenes debe permitir su origen mediante CORS; Base64 evita esa dependencia. El nombre del lanzador y el icono nativo Android pertenecen al APK y no cambian con este JSON.

### Actualización sin polling móvil

- Al autenticar, al volver a primer plano y con pull-to-refresh se carga estado.
- `/api/v1/events` mantiene un canal SSE Bearer autenticado. Envía solo invalidaciones, no documentos privados. Los cambios de órdenes se dirigen al cliente correspondiente y al equipo del taller; no obligan a refrescar a otros clientes. El cliente agrupa ráfagas y descarga datos al recibir un evento.
- Solo se vuelve a descargar el JSON de marca cuando cambia configuración, al conectar o con actualización explícita.
- Heartbeats de transporte cada 20 segundos; reconexión exponencial 2–60 s. No hay un temporizador consultando órdenes.
- **SSE funciona con la aplicación abierta. No es FCM ni push nativo en segundo plano**. Con la app cerrada, esta entrega notifica por Telegram/email y sincroniza al abrirla.
- El broker SSE es local al proceso: desplegar con **un worker Uvicorn** como en Compose. Para varias réplicas es necesario un broker compartido (por ejemplo Redis Pub/Sub).

## 5. Telegram y SMTP reales

En `.env`, configura al menos un canal y reinicia con `docker compose up -d --force-recreate api`.

**Telegram**: crea un bot con BotFather, guarda `TELEGRAM_BOT_TOKEN`, pide al cliente iniciar el bot (`/start`) y registra su `chat_id` numérico en el formulario. Selecciona Telegram como canal. Un bot no puede iniciar una conversación por número telefónico.

**Email**: configura `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS=true`. Para Gmail utiliza contraseña de aplicación y una cuenta con verificación en dos pasos. La gratuidad y límites dependen del proveedor.

Los mensajes sin proveedor, destino o conexión quedan **en pausa**, sin reintentos continuos ni eventos que recarguen la pantalla. El lápiz del envío permite corregir correo, canal y chat_id del cliente desde **Notificaciones**, actualizando también su ficha y los envíos aún pendientes, sin regenerar contraseñas. Tras corregir el servidor se puede reanudar explícitamente; también se reevalúan los pausados una vez al iniciar la API. Las claves del proveedor permanecen en `.env`, nunca en Flutter. Los demás errores transitorios tienen hasta cinco reintentos con espera. **No se simula éxito**: la entrega externa es *al menos una vez* y puede duplicarse si el proveedor acepta pero se pierde la confirmación.

Las credenciales temporales del outbox se cifran con una clave derivada de `SECRET_KEY`, se borran después de enviar o a las 24 horas. Regenerar acceso invalida sesiones y mensajes de credenciales anteriores. Si cambias `SECRET_KEY`, invalida los JWT y los mensajes cifrados pendientes; drena o regenera estos últimos antes de rotarla. No hay contraseñas en el inbox ni en el listado del panel.

## 6. Android, Web y seguridad de plataforma

- `AndroidManifest.xml` principal incluye Internet y estado de red. HTTP está bloqueado en release; solo el manifiesto **debug** admite tráfico sin TLS para desarrollo.
- Se utiliza el selector nativo del sistema. **No se piden permisos amplios de almacenamiento ni cámara** porque Android solo consulta evidencia y el taller carga fotos con el selector. No se necesita `MANAGE_EXTERNAL_STORAGE`.
- `main.dart` configura barras transparentes y edge-to-edge. `--dart-define=IMMERSIVE_MODE=true` solicita modo inmersivo; Android 15/16 puede imponer edge-to-edge según target SDK y no permite ocultación permanente de barras. Se usa `SafeArea` para proteger controles.
- `android/app/build.gradle.kts`: JDK 17+ (JDK 21 recomendado), minSdk al menos 23 y versiones SDK administradas por Flutter. Conserva el namespace existente para no romper el proyecto.
- Para firma propia, crea `android/key.properties` con `storeFile`, `storePassword`, `keyAlias`, `keyPassword`. Sin ese archivo, release usa firma debug **solo para QA**, no distribución en Play.
- `web/index.html`: viewport adaptativo, idioma español, arranque accesible y manifiesto PWA. CORS **se configura en el servidor**, no mediante permisos de HTML.
- Bearer JWT de dos horas por defecto, solo en memoria Flutter (no localStorage). Recargar la Web exige autenticarse de nuevo. Cambiar contraseña o salir revoca sesiones previas.

```powershell
# Emulador Android, API local en Docker:
flutter devices
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1

# APK para una API HTTPS desplegada (sustituye el dominio por el tuyo):
flutter build apk --release --dart-define=API_BASE_URL=https://taller.example.com/api/v1
```

El APK release debe compilarse con la URL real HTTPS; no existe un endpoint comercial preconfigurado. Para preparar este equipo, instala Android SDK Command-line Tools desde Android Studio y acepta las licencias. Si Java no está en PATH, el JDK existente puede seleccionarse por terminal sin alterar configuración global:

```powershell
$env:JAVA_HOME = 'RUTA_DE_SU_JDK_21' # Sustituya por la carpeta de su JDK 21
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
```

## 7. API local sin Docker

La instalación autónoma usa el lanzador `MotorDesk.cmd`, SQLite persistente y Python 3.14 en desarrollo. Consulte [la guía local](docs/instalacion_local.md). El ejecutable empaquetado incluye Python; su validación está detallada en [resultados](docs/portabilidad_resultados.md).

Para un servidor PostgreSQL sin Docker, prepare PostgreSQL con pgvector, configure `.env` y ejecute desde `backend`: `python -m alembic upgrade head`, `python -m app.bootstrap` y `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. No aplique estas migraciones PostgreSQL a SQLite. Las bases y los procedimientos de actualización son independientes; las reglas de negocio son compartidas.

## 8. Pruebas y verificación

```powershell
flutter analyze
flutter test
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

La suite API usa una base SQLite en memoria aislada por prueba por defecto. Para ejecutar la misma suite sobre PostgreSQL:

```powershell
$line = Get-Content .env | Where-Object { $_ -like 'DATABASE_URL=*' }
$env:TEST_DATABASE_URL = $line.Substring('DATABASE_URL='.Length)
.\.venv\Scripts\python.exe -m pytest backend/tests -q
Remove-Item Env:TEST_DATABASE_URL
```

Se crea y elimina **un esquema aleatorio de pruebas**, no tus tablas de taller. Usa una base de pruebas en entornos compartidos. Las pruebas de entrega interceptan el proveedor para no enviar mensajes reales.

Cobertura: autenticación, cambios/revocación, credenciales cifradas, rollback de duplicados, roles, aislamiento entre clientes, precedencia de flags, binding de dispositivo, revisiones, importes, checklist, aprobaciones/rechazos, notificación idempotente, traspaso privado, fotos y reintentos. Flutter prueba configuración, publicación, validaciones y layouts responsivos.

### Verificación de esta entrega

- 28 pruebas API aprobadas sobre PostgreSQL 17, incluidas aprobaciones y altas de órdenes concurrentes.
- 32 pruebas Flutter aprobadas: JSON, tema, errores, permisos reactivos, layouts móvil/escritorio y regresiones de edición/cambio de contraseña.
- Flutter Web release compilado en `build/web`.
- APK Android debug compilado en `build/app/outputs/flutter-apk/app-debug.apk` con JDK 21; no se ha certificado su ejecución en un dispositivo físico ni firmado para distribución.
- Navegación Web y conexión SSE verificadas con la API real. La cuenta temporal de verificación se retiró; se conserva únicamente el administrador inicial.
- Los proveedores se interceptan en las pruebas. No se han enviado correos/Telegram reales sin sus credenciales.

## 9. Antes de publicar en Internet

Configura HTTPS con tu proxy/dominio, `ENVIRONMENT=production`, orígenes CORS HTTPS exactos, secretos propios, SMTP/Telegram y firma Android. Mantén PostgreSQL fuera de Internet, copia la base/volumen de forma periódica y prueba restauraciones. No aumentes los workers SSE sin broker compartido. Esta entrega no incluye FCM en segundo plano, facturación fiscal, alta de empleados desde UI, despliegue a una nube ni una auditoría de seguridad independiente.
