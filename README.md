# MotorDesk

Entrega del 3 de noviembre de 2026 para instalación local en Windows o con Docker.

## Descargar y ejecutar

Descarga **MotorDesk-Final-10MB.zip** desde [Releases](https://github.com/juanessan121/Motor_Desk/releases). Tamaño: **9.912.385 bytes**, inferior a 10 MB.

Extrae el ZIP y sigue su guía de inicio. La primera instalación local requiere **Python 3.14 x64 e Internet** para descargar dependencias. El tamaño instalado será mayor que el ZIP. Docker requiere Docker Desktop.

## Código fuente

**MotorDesk-Tecnico.zip** contiene el árbol completo del código fuente, catálogo, scripts y documentación. Extráelo para desarrollar o reconstruir la aplicación. El código se publica como archivo comprimido; las tareas de CI incluidas no se ejecutan automáticamente desde este repositorio de entrega.

## Verificación y alcance

- 134 pruebas de interfaz aprobadas.
- 237 pruebas backend aprobadas; los 3 casos de concurrencia se comprobaron además en PostgreSQL real.
- Instalación limpia del paquete, persistencia, respaldo/restauración y modalidad Docker verificadas.
- Auditoría de dependencias: sin vulnerabilidades conocidas reportadas en la fecha de entrega.

Consulta [instalación y alcance](entrega_produccion.md), [resultados y pendientes](validacion_entrega_20261103.md) y [evidencia resumida](release-validation.json).

Validado para uso local. Un despliegue público requiere configurar HTTPS, dominio, supervisión y respaldos externos. El flujo cliente → vehículo → orden está implementado; la extensión a todos los demás botones de creación permanece pendiente. No se incluyen credenciales ni datos operativos del taller.
