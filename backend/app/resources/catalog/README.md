# Datos de referencia incluidos

MotorDesk distribuye las fuentes originales sin modificar y el código de importación.
No contienen información de clientes ni representan existencias, precios o
compatibilidades verificadas del taller.

- `vehicles.sqlite`: gor3a/vehicle-makes-models y autoevolution.com, ODbL 1.0.
  https://github.com/gor3a/vehicle-makes-models
  Licencia: https://opendatacommons.org/licenses/odbl/1-0/
  El importador normaliza claves y combina duplicados. La base de referencia
  derivada conserva ODbL; el original y el código para reproducirla están incluidos.
- `part_terms.json`: lifeofcapo/car-api, copyright 2026 lifeofcapo, MIT.
  https://github.com/lifeofcapo/car-api
  El glosario de MotorDesk añade términos en español y marca traducciones pendientes.

Los archivos LICENSE incluyen los avisos de cada fuente y manifest.json sus
URL, tamaños y SHA-256. No se incluyen logos de terceros en este paquete:
el proyecto de logos advierte que cada imagen conserva los derechos de su titular.
La interfaz mantiene el fallback cuando no hay imagen.

Solo se cargan automáticamente catálogos vacíos. No se actualizan ni sobrescriben
referencias ya existentes al iniciar el programa. Los modelos semánticos y las
especificaciones extendidas no son necesarios para esta precarga.
