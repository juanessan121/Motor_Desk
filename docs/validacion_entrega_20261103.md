# Validación de entrega — 3 de noviembre de 2026

## Alcance

Entrega para instalación local y Docker, con catálogo precargado y administrador propio. El ZIP ligero requiere Python 3.14 x64 y descarga inicial de dependencias. No es una instalación completamente offline desde cero ni una certificación de despliegue público.

## Correcciones de esta revisión

- Actualizadas cryptography 48.0.1 → 50.0.0 y Pillow 12.3.0 → 13.0.0 tras encontrar avisos en la auditoría de dependencias.
- Auditoría posterior de requirements.lock: sin vulnerabilidades conocidas reportadas por pip-audit al consultar el 3 de noviembre de 2026. No equivale a garantizar ausencia de vulnerabilidades desconocidas.
- Documentación interactiva y OpenAPI deshabilitados en modo production.
- Cabecera contra enmarcado y revalidación de recursos web con nombres estables para no mantener una interfaz desactualizada después de instalar una entrega.
- Empaquetador reproducible desde fuente actual, límite estricto de 10.000.000 bytes, SHA-256 y manifiesto de archivos.
- Exclusión de exportaciones operativas, ZIP anteriores, respaldos, bases del taller y credenciales.
- Instalador ligero con Python x64, extracción segura, comprobación de integridad y dependencias fijadas; comandos de verificación y respaldo.

## Pruebas

- Interfaz: 134 pruebas Flutter aprobadas.
- Backend inicial: 235 aprobadas y 3 omitidas.
- Seguridad y regresiones específicas: 13 aprobadas.
- Backend final con bibliotecas corregidas: 237 aprobadas y 3 omitidas bajo SQLite.
- Los 3 casos omitidos pasaron por separado en PostgreSQL real: aprobación concurrente, orden única por vehículo y salida de stock exactamente una vez ante llamadas simultáneas.
- ZIP extraído: instalación de dependencias en venv nuevo, configuración inicial, autenticación, catálogos, recursos web, cliente, vehículo, orden, notificaciones pendientes, exportación, reinicio, integridad, respaldo y restauración aprobados.
- Docker del paquete: construcción, migraciones hasta 0015, autenticación, cliente, vehículo, orden, notificaciones, reinicio, persistencia de volumen, pg_dump y pg_restore aprobados en proyecto desechable.
- Se fijaron además 8 dependencias transitivas a las versiones resueltas por la instalación limpia. La auditoría de la lista completa no reportó vulnerabilidades conocidas.
- El código de la aplicación, catálogo y recursos web del ZIP final se comparan por SHA-256 con el contenido probado. El cierre de dependencias conserva las mismas versiones instaladas en esa prueba.

Evidencia local: build/production-backend-final-20261103.log, build/production-flutter-20261103.log, build/production-postgres-concurrency-final.log, build/production-lightweight-test.log, build/production-packaged-docker-test.log y build/production-dependency-audit-final.json. Los logs operativos completos no se publican para evitar divulgar datos de la máquina.

## Límites y pendientes explícitos

No se ha realizado una certificación en otra PC Windows limpia, una prueba de carga a escala ni envíos reales con proveedores externos. Las pruebas se ejecutan en carpetas/entornos nuevos y bases sintéticas del equipo de desarrollo. Los casos de concurrencia PostgreSQL se ejecutaron en una base aislada con las extensiones pg_trgm y vector.

El recorrido cliente → vehículo → orden está implementado. La ampliación a todos los demás botones de creación, la importación académica completa y otros puntos de la matriz de 60 requisitos siguen pendientes; consulte docs/matriz_prompt_maestro.md. Los datos históricos no se reconstruyen ni se inventan.

Para uso público: configurar dominio, HTTPS, control de acceso, supervisión, respaldo externo y recuperación comprobada según el entorno real. Los lanzadores entregados escuchan solamente en loopback. Las integraciones deben configurarse con credenciales propias. El token aportado en el chat no pertenece a la entrega y debe revocarse después de publicar.
