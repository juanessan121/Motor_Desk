# Matriz de cumplimiento del prompt maestro — 23/10/2026

Evaluación conservadora. “Funciona” refiere al alcance y evidencia de la columna final, no a certificación productiva. Esta revisión amplía la auditoría anterior de portabilidad.

| Nº | Requisito | Estado actual | Evidencia / pendiente |
|---|---|---|---|
| 1 | Analizar el proyecto antes de modificarlo | Funciona parcialmente | Stack y módulos inspeccionados: Flutter/Dart, FastAPI/Python, SQLAlchemy, PostgreSQL y SQLite. Falta recorrido manual completo. |
| 2 | Ejecutar un diagnóstico funcional | Funciona parcialmente | API, widgets y arranque local probados. No equivale a probar cada pantalla manualmente. |
| 3 | Elaborar una matriz inicial de problemas | Funciona correctamente | Matriz de 60 requisitos con evidencia y pendientes; prioridades debajo. |
| 4 | Conservar la implementación existente | Funciona correctamente | Cambios incrementales; no se borraron registros ni se reemplazó el stack. |
| 5 | Establecer una arquitectura modular | Funciona parcialmente | Rutas separadas por dominio; pricing.py centraliza cálculo. Continúa el controlador Flutter amplio. |
| 6 | Revisar los roles del sistema | Funciona correctamente | Roles admin, mechanic y customer existentes y cubiertos por pruebas. |
| 7 | Implementar permisos efectivos | Funciona parcialmente | Corregidos export general accesible a mecánicos y archivo de mensajes entre talleres; suite de permisos. |
| 8 | Completar el registro de clientes | Funciona parcialmente | Campos de identidad/contacto, unicidad y WhatsApp independiente; varios campos aún admiten vacío. |
| 9 | Permitir gestionar varios vehículos por cliente | Funciona correctamente | Relación propietario/vehículos e historial, pruebas de transferencia y aislamiento. |
| 10 | Resolver la creación de cuentas de acceso | Funciona correctamente | Cliente sin portal, habilitación posterior, activación y contraseña temporal individual probados. |
| 11 | Garantizar seguridad de credenciales | Funciona correctamente | Argon2, cambio obligatorio y revocación de sesión; sin contraseñas existentes en formularios. |
| 12 | Completar el registro de vehículos | Funciona parcialmente | Datos vehiculares y kilometraje de recepción; falta historial independiente completo de kilometraje. |
| 13 | Mejorar la selección de vehículos | Funciona correctamente | Selectores jerárquicos y registro manual cubiertos por pruebas de catálogo y widgets. |
| 14 | Revisar las bases de datos automotrices existentes | Funciona parcialmente | Fuentes vehículos y piezas verificadas, originales/licencias/hashes incluidos. Derechos de imágenes pendientes; no se redistribuyen logos. |
| 15 | Reparar el catálogo de marcas y modelos | Funciona parcialmente | Instalación limpia y selectores HTTP verificados con catálogo real precargado: 164 marcas y 2644 modelos; falta recorrido manual completo. |
| 16 | Reparar el catálogo de repuestos | Funciona parcialmente | Catálogo, términos y stock separados; falta completar precio unitario/compatibilidad en todos los flujos. |
| 17 | Incorporar correctamente los logotipos | Funciona parcialmente | Normalización y fallback probados; derechos y precarga offline de todos los logos pendientes. |
| 18 | Mantener información en español y orientada a Ecuador | Funciona parcialmente | Español, USD y configuración regional; impuesto editable. No se certifican reglas tributarias legales. |
| 19 | Implementar búsqueda flexible | Funciona correctamente | Búsqueda textual y filtros sin modelo semántico obligatorio; pruebas de catálogos. |
| 20 | Crear un catálogo independiente de actividades | Funciona correctamente | CRUD de actividades independiente y probado. |
| 21 | Implementar plantillas de mantenimiento | Funciona correctamente | Plantillas independientes, ocho referencias locales y versionado. |
| 22 | Crear mantenimientos mediante selección de actividades | Funciona correctamente | Recepción con selección y deselección, tareas extra y asignación; pruebas de flujo. |
| 23 | Separar selección y ejecución del checklist | Funciona correctamente | Selección separada de ejecución; estados y revisiones de tarea probados. |
| 24 | Permitir actividades manuales | Funciona parcialmente | Tareas solo de la orden soportadas; falta acción directa para guardar la tarea manual como actividad reutilizable. |
| 25 | Conservar el historial de las órdenes | Funciona correctamente | Instantáneas/versiones, cambios de plantilla no reescriben órdenes; pruebas de preservación. |
| 26 | Completar los datos obligatorios de mantenimiento | Funciona parcialmente | Campos de recepción, diagnóstico, costos y entrega; aún falta edición contextual completa. |
| 27 | Corregir definitivamente la vista de taller | Funciona parcialmente | Operaciones de ocupación y asignación probadas en API/widgets; falta recorrido manual de extremo a extremo. |
| 28 | Corregir la plantilla SVG del taller | Funciona parcialmente | SVG conservado y drag/drop con ocupación real probado en widgets; validación manual pendiente. |
| 29 | Mejorar las asignaciones de mecánicos | Funciona correctamente | Asignación de tareas/órdenes y visibilidad restringida a mecánicos cubiertas por pruebas. |
| 30 | Implementar seguimiento de estados | Funciona parcialmente | Etapas operativas derivadas y cierre con revisión; no todos los estados sugeridos son explícitos. |
| 31 | Registrar historial de estados | Funciona parcialmente | Nuevos cambios de estado guardan antes/después/actor/fecha; no se inventan fechas históricas. Falta panel cronológico completo. |
| 32 | Corregir las observaciones ambiguas | Funciona parcialmente | Síntomas, diagnóstico, notas de orden/tarea y retraso diferenciados; cliente y entrega requieren ampliación. |
| 33 | Explicar los retrasos | Funciona parcialmente | Motivo de demora existe; falta historial completo de ETA anterior/nueva y resolución por etapa. |
| 34 | Gestionar los repuestos utilizados | Funciona parcialmente | Solicitud, autorización y salida de stock idempotente; desglose unitario completo por tarea pendiente. |
| 35 | Separar presupuestos de costos finales | Funciona parcialmente | Estimación identificada y liquidación congelada al entregar; falta editor de ajustes y desglose previsto/real completo. |
| 36 | Implementar cálculos económicos consistentes | Funciona parcialmente | Decimal, ROUND_HALF_UP, tasa configurable y cálculo único en UI/export/avisos; alcance económico completo pendiente. |
| 37 | Cumplir los tres eventos académicos obligatorios | Funciona correctamente | Recepción, listo y pago probados en flujo completo sin portal ni proveedor. |
| 38 | Implementar una estructura completa de notificaciones | Funciona parcialmente | Estados, contenido, destinatario, fechas y confirmación externa; historial de cada intento requiere ampliación. |
| 39 | Editar contactos directamente desde notificaciones | Funciona correctamente | Edición de contactos y preferencias desde Notificaciones, sin duplicar mensajes; pruebas existentes. |
| 40 | Evitar saturación del panel de notificaciones | Funciona parcialmente | Bandeja, archivo, limpieza y actualización; filtros por fecha/canal/estado e historial visible aún incompletos. |
| 41 | Permitir notificaciones con y sin proveedores externos | Funciona correctamente | Pendientes offline, visualizar/copiar sin envío; prueba SMTP local real. Proveedores externos reales no verificados. |
| 42 | Prevenir duplicados y gestionar reintentos | Funciona parcialmente | Deduplicación y reintentos de misma fila; no hay garantía exactly-once ante caída después de entrega externa. |
| 43 | Cumplir íntegramente las cinco fases académicas | Funciona parcialmente | Cinco colecciones exportadas; falta importación incremental y completar detalle académico de costos/historia. |
| 44 | Construir un JSON académico válido | Funciona parcialmente | IDs y relaciones presentes, sin accesos temporales; fechas UTC y diagnóstico vacío sin inventar revisados. |
| 45 | Incorporar validación JSON Schema | Funciona parcialmente | JSON Schema y validador adicional de referencias/duplicados; pendiente ampliar cobertura de importación. |
| 46 | Exportar e importar datos | Funciona parcialmente | API incremental de clientes/vehículos con prevalidación e idempotencia probada. Pendiente interfaz e importación de órdenes académicas; no sustituir por restauración. |
| 47 | Funcionar con y sin API externas | Funciona parcialmente | Núcleo y catálogos precargados persisten localmente; pendientes costos detallados/demoras/importación incremental. |
| 48 | Funcionar con y sin Docker | Funciona parcialmente | Mismo backend Docker/local; PostgreSQL hasta 0015, reinicio y restauración aprobados. Integraciones externas reales pendientes. |
| 49 | Disponer de persistencia autónoma | Funciona parcialmente | SQLite FK, respaldo, versión 2 y migración conservativa; concurrencia local exige más pruebas. |
| 50 | Trabajar sin conexión permanente | Funciona parcialmente | Catálogo precargado, reinicio y respaldo/restauración del ZIP aprobados; arranque completo y suite actuales aprobados en Linux con red deshabilitada. |
| 51 | Distinguir trabajo local, red local y sincronización | Funciona correctamente | Instalación individual, LAN y equipos separados documentados sin prometer sincronización. |
| 52 | Preparar una instalación sencilla para terceros | Funciona parcialmente | ZIP con CPython firmado verificado en mismo equipo; falta otra PC/VM Windows limpia. |
| 53 | Preparar dos paquetes diferenciados | Funciona parcialmente | ZIP de usuario con runtime firmado y ZIP técnico reconstruidos. ZIP actual aprobado en carpeta aislada con PATH reducido. |
| 54 | Crear un asistente de primera ejecución | Funciona parcialmente | Asistente crea taller/admin sin tokens; datos generales y preferencias iniciales completos pendientes. |
| 55 | Implementar copias de seguridad y restauración | Funciona correctamente | Backup versionado, integridad, restauración a destino nuevo y secretos temporales excluidos; pruebas locales. |
| 56 | Mejorar la interfaz sin volverla genérica | Funciona parcialmente | Identidad conservada y 130 pruebas Flutter aprobadas; revisión manual integral pendiente. |
| 57 | Optimizar rendimiento y confiabilidad | Funciona parcialmente | Índices/paginación/carga selectiva existentes; aún no hay perfil completo bajo carga real. |
| 58 | Aplicar controles de seguridad | Funciona parcialmente | Autenticación y separación por taller verificadas; permisos corregidos, validación de importación pendiente. |
| 59 | Ejecutar pruebas integrales | Funciona parcialmente | 232 backend aprobadas/3 omitidas, 130 Flutter y ZIP actual aprobado. Recorrido manual completo, VM y proveedores externos pendientes. |
| 60 | Entregar resultados verificables y completos | Funciona parcialmente | Evidencia y matriz en actualización; no se declara cumplimiento integral. |

## Diagnóstico inicial prioritario

| Prioridad | Hallazgo inicial | Acción / estado |
|---|---|---|
| P0 | Exportación general permitida a mecánico | Corregida: solo administrador. |
| P0 | Archivar notificación no comprobaba taller | Corregido en búsqueda centralizada. |
| P1 | Cliente sin cuenta no recibía eventos y no podía autorizar ejecución | Eventos independientes del usuario y autorización presencial auditada. |
| P1 | Totales distintos entre orden, aviso y JSON; impuesto fijo | Servicio único Decimal, tasa configurable, instantánea de liquidación. |
| P1 | Exportación atribuía fechas inventadas a etapas | Retiradas inferencias; nuevo historial real con actor. |
| P1 | Importación incremental ausente | Pendiente, no confundir con restauración completa. |
| P1 | Instalación local inicia sin catálogo vehicular precargado | Resuelto para vehículos y piezas; logos excluidos con fallback. |
| P2 | Demoras y observaciones incompletas | Pendiente de flujo contextual completo. |
| P2 | Validación en equipo Windows limpio | Requiere segundo entorno disponible. |
