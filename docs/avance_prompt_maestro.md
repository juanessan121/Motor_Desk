# Validación del prompt maestro — 23/10/2026

Esta entrega es un avance verificable, no una declaración de cumplimiento de los
60 requisitos. La matriz `matriz_prompt_maestro.md` distingue lo probado de lo pendiente.

## Correcciones

- Exportación completa reservada a administración; un mecánico no puede extraer clientes ajenos.
- Consulta, archivo y reintento de notificaciones limitados al taller propietario.
- Notificaciones vinculadas al cliente aunque no tenga cuenta; preferencias de canal respetadas al reanudar.
- Autorización presencial de servicio base para clientes sin portal: revisión de orden,
  nota obligatoria, administrador responsable y total autorizado en auditoría.
- Cálculo central en `pricing.py`, Decimal y redondeo HALF_UP. El total operativo,
  avisos y exportación usan la misma fórmula. El cierre congela la liquidación;
  las órdenes abiertas se identifican como estimaciones. Las liquidaciones ya
  cerradas conservan su instantánea, sin recalcular datos históricos.
- Tasa editable desde Administración, aplicada a nuevas órdenes. El valor inicial
  heredado no constituye una certificación de la tasa legal aplicable.
- El JSON no atribuye fechas inventadas a etapas intermedias ni inventa diagnósticos.
  Nuevas transiciones registran estado anterior/nuevo, fecha, usuario y motivo.
- Validación adicional de referencias y duplicados mediante
  `backend/scripts/validate_workshop_json.py`; no importa ni modifica datos.

## Base de datos y referencias

PostgreSQL: migración 0015 añade `notifications.customer_id`, conserva el vínculo
de usuario existente y permite mensajes sin usuario. Ejecutada en un volumen
sintético nuevo hasta 0015, con reinicio, pg_dump y pg_restore comprobados.
No se migró ni restauró la base real del taller.

SQLite: versión local 2; migración explícita desde v1, en transacción, con
comprobación de esquema y claves foráneas. Prueba de conservación de una notificación
existente y de sus intentos. Los respaldos v1 admiten conversión del vínculo de
cliente al restaurar a un destino nuevo.

La instalación local nueva incluye fuentes originales de referencia y licencias
en `backend/app/resources/catalog`. La prueba real cargó 164 marcas, 2644 modelos,
6790 generaciones, 30535 motores y 1521 nombres de piezas. Son conteos de esta
importación normalizada, no cantidades prometidas por los repositorios.
No representan stock, precios ni compatibilidad específica verificada.
Se omiten especificaciones extendidas y embeddings para no hacerlos obligatorios.
Una instalación con catálogo existente no se sobrescribe al arrancar.

Fuentes verificadas:

- [Vehículos y licencia ODbL](https://github.com/gor3a/vehicle-makes-models/blob/main/LICENSE-DATA).
- [Piezas y licencia MIT](https://github.com/lifeofcapo/car-api/blob/main/LICENSE).
- [Logotipos](https://github.com/filippofilip95/car-logos-dataset): el repositorio
  advierte que cada imagen conserva los derechos de sus titulares. No se añade
  una redistribución de imágenes en esta entrega; la interfaz conserva fallback.

## Evidencia

- Backend completo Windows: **232 aprobadas, 3 omitidas**, `build/master-backend-tests.log`.
- Backend Linux sin red: **232 aprobadas, 3 omitidas**, `build/master-linux-tests.log`.
- Flutter: **130 aprobadas**; incluye tamaños móvil/escritorio y acciones de taller.
- Compilación web release sin CDN obligatorio: `build/master-flutter-build.log`.
- Flujo sin portal: autorización, checklist, revisión, entrega, total final,
  historial y tres mensajes pendientes, en `test_master_regressions.py`.
- PostgreSQL 0015: `build/master-docker-smoke.log`.
- Lanzador desde código con catálogos, reinicio, respaldo/restauración:
  `build/master-source-catalog.log`.
- Arranque completo Linux **sin red**, con catálogo, operaciones, reinicio y restauración: aprobado, `build/master-linux-offline-smoke.log`.
- JSON sintético no vacío: esquema, formatos y relaciones válidos.
- ZIP con runtime firmado: **aprobado**, `build/master-runtime-smoke.log`; incluye selectores de catálogo, reinicio y restauración. Prueba en este equipo con PATH reducido.
- Análisis Flutter: 17 avisos de API obsoleta y 1 import sin uso; no se presenta como análisis sin incidencias.

Las pruebas automatizadas de API/widgets no sustituyen un recorrido manual de
todas las pantallas. Sigue pendiente una segunda PC o VM Windows limpia,
proveedores externos reales autorizados y el resto de puntos parciales de la matriz.
Los resultados de los paquetes anteriores en `portabilidad_resultados.md`
corresponden a su versión; no certifican automáticamente el nuevo código.

## Pendientes prioritarios

Importación incremental académica con prevalidación y conflictos; historial completo
de demoras/ETA; desglose de repuestos y ajustes de costos; autorización presencial
de cotizaciones adicionales; filtros e historial de notificaciones; guardar una
tarea manual como actividad reutilizable; comprobación manual integral y de concurrencia.
