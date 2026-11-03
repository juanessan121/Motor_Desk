# MOTORDESK — PROMPT MAESTRO DEFINITIVO
## Auditoría, reparación, optimización, arquitectura híbrida y distribución de un sistema de gestión automotriz

### INSTRUCCIÓN PRINCIPAL

Actúa como un equipo senior de ingeniería de software especializado en arquitectura de sistemas, desarrollo full stack, bases de datos, seguridad, UX/UI, aplicaciones empresariales y despliegue multiplataforma.

Vas a continuar desarrollando **MotorDesk**, un sistema de gestión de talleres automotrices que ya tiene una implementación existente.

**No estás comenzando un proyecto nuevo.**

Necesito que inspecciones el proyecto completo, comprendas cómo está desarrollado, identifiques lo que funciona, detectes los errores existentes y realices las modificaciones necesarias.

El objetivo es obtener una aplicación estable, moderna, intuitiva, mantenible, portable y preparada para ser utilizada por un taller real en Ecuador.

No quiero que únicamente mejores la apariencia. Necesito que todas las funcionalidades trabajen correctamente, que los datos persistan y que cada rol pueda realizar sus operaciones sin procesos innecesariamente complicados.

Debes cumplir los siguientes 60 puntos.

---

# FASE A — AUDITORÍA DEL PROYECTO

## 1. Analizar el proyecto antes de modificarlo

Inspecciona la totalidad del proyecto y determina:

- Lenguajes y frameworks utilizados.
- Arquitectura del frontend y backend.
- Organización de carpetas.
- Dependencias.
- Sistema de autenticación.
- Base de datos.
- Modelos y relaciones.
- Servicios y API existentes.
- Configuración de Docker, si existe.
- Recursos gráficos y SVG.
- Módulos implementados.
- Funcionalidades incompletas.
- Errores de ejecución.
- Puntos de acoplamiento innecesario.

Comprende la implementación actual antes de escribir código.

## 2. Ejecutar un diagnóstico funcional

Intenta iniciar MotorDesk utilizando los mecanismos existentes.

Comprueba qué pantallas funcionan realmente y cuáles fallan.

Revisa particularmente:

- Inicio de sesión.
- Dashboard.
- Clientes.
- Vehículos.
- Taller.
- Mantenimientos.
- Actividades.
- Repuestos.
- Catálogos.
- Notificaciones.
- Administración.
- Gestión de usuarios.

No supongas que una función trabaja simplemente porque existe su interfaz.

Si no puedes ejecutar alguna parte, explica el impedimento y no declares que fue probada.

## 3. Elaborar una matriz inicial de problemas

Clasifica cada funcionalidad utilizando:

- Funciona correctamente.
- Funciona parcialmente.
- Presenta errores.
- No está implementada.
- No se pudo verificar.

Identifica las causas técnicas cuando sea posible.

Da prioridad a los fallos que impiden completar un proceso de negocio.

## 4. Conservar la implementación existente

No reconstruyas MotorDesk desde cero.

No reemplaces frameworks ni bases de datos sin una razón técnicamente demostrable.

Reutiliza los componentes, servicios, modelos y recursos que funcionen correctamente.

Aplica refactorizaciones incrementales.

Antes de modificar una estructura compartida, revisa qué otras funcionalidades dependen de ella.

## 5. Establecer una arquitectura modular

Organiza o adapta la arquitectura para separar:

- Presentación e interfaz.
- Reglas de negocio.
- Servicios de aplicación.
- Persistencia.
- Autenticación y autorización.
- Catálogos.
- Taller y órdenes.
- Inventario.
- Notificaciones.
- Integraciones externas.
- Exportación e importación.
- Configuración y despliegue.

Evita duplicar reglas entre frontend y backend.

La arquitectura debe permitir añadir módulos futuros sin modificar innecesariamente los existentes.

---

# FASE B — USUARIOS, CLIENTES Y VEHÍCULOS

## 6. Revisar los roles del sistema

Verifica qué roles ya existen.

Como mínimo, contempla las responsabilidades de:

**Administrador:** gestión general, clientes, vehículos, usuarios, actividades, mantenimiento, costos, notificaciones y configuraciones.

**Mecánico:** consultar los trabajos asignados, registrar diagnósticos autorizados, actualizar actividades y comunicar observaciones.

**Cliente:** consultar información de sus vehículos, mantenimientos y estados cuando tenga una cuenta habilitada.

**Recepcionista o personal de atención:** rol opcional cuando la arquitectura existente o las necesidades del taller lo justifiquen.

No todos los roles deben visualizar las mismas acciones.

## 7. Implementar permisos efectivos

No basta con ocultar botones.

Verifica las autorizaciones también en los servicios y endpoints correspondientes.

Un mecánico no debe acceder a órdenes de otros técnicos salvo que tenga permisos explícitos.

Un cliente no debe consultar vehículos o información privada de otros clientes.

El administrador debe disponer de los permisos necesarios para gestionar el taller.

## 8. Completar el registro de clientes

El registro debe contener obligatoriamente:

- Identificador único.
- Nombres.
- Apellidos.
- Número de identificación.
- Teléfono.
- WhatsApp.
- Correo electrónico.
- Dirección.
- Medio de notificación preferido: WhatsApp, Telegram o correo electrónico.

Adicionalmente, puede incorporar:

- Telegram.
- Estado del cliente.
- Fecha de registro.
- Observaciones propias del cliente.
- Historial de vehículos.
- Preferencias de comunicación.

Permite diferenciar teléfono y WhatsApp, aunque ambos puedan utilizar el mismo número.

Valida los identificadores y evita duplicaciones indebidas.

## 9. Permitir gestionar varios vehículos por cliente

Cada cliente debe poder tener uno o varios vehículos asociados.

Desde la ficha del cliente debe ser posible:

- Consultar vehículos registrados.
- Agregar vehículos.
- Editar información.
- Consultar historial de mantenimiento.
- Acceder a las órdenes correspondientes.

Evita solicitar nuevamente información ya registrada.

## 10. Resolver la creación de cuentas de acceso

Actualmente no está claro cómo obtiene sus credenciales un cliente nuevo.

Corrige este flujo.

Registrar un cliente y crear una cuenta de usuario deben ser procesos relacionados, pero independientes.

Al registrar un cliente, permite elegir si tendrá acceso al sistema.

Si tendrá acceso:

- Crear o vincular su usuario.
- Asociarlo correctamente al cliente.
- Generar un proceso seguro para establecer contraseña.
- Permitir activación posterior.
- Permitir recuperación de acceso.
- Mostrar el estado de la cuenta.

Estados sugeridos:

- Sin cuenta.
- Pendiente de activación.
- Activa.
- Deshabilitada.

No obligues a crear credenciales para registrar un vehículo.

## 11. Garantizar seguridad de credenciales

Nunca guardes contraseñas en texto plano.

Utiliza mecanismos de almacenamiento seguro, como algoritmos modernos de hash apropiados para contraseñas.

No muestres contraseñas existentes en formularios administrativos.

No utilices una contraseña universal para clientes nuevos.

Implementa recuperación o restablecimiento seguro, evitando revelar si una cuenta existe cuando ello represente un riesgo.

## 12. Completar el registro de vehículos

Cada vehículo debe almacenar:

- Identificador único.
- Identificador del propietario.
- Placa.
- Marca.
- Modelo.
- Año de fabricación.
- Color.
- Kilometraje actual.
- Tipo de combustible.
- Número de chasis o VIN.

Adicionalmente, considera:

- Generación o versión.
- Tipo de motor.
- Transmisión.
- Fecha de registro.
- Observaciones del vehículo.
- Historial de kilometraje.

Valida los datos y conserva los vínculos con sus órdenes.

## 13. Mejorar la selección de vehículos

Utiliza selectores dependientes cuando existan datos disponibles:

Marca → Modelo → Generación → Motor.

Si una marca o modelo no aparece, ofrece registro manual.

No obligues al usuario a introducir datos innecesarios.

Cuando se selecciona un vehículo registrado, carga automáticamente la información pertinente.

---

# FASE C — CATÁLOGOS Y DATOS AUTOMOTRICES

## 14. Revisar las bases de datos automotrices existentes

Comprueba qué información automotriz ya está importada.

Como fuentes candidatas previamente consideradas, revisa:

- `gor3a/vehicle-makes-models`, incluyendo `data/vehicles.sqlite` o CSV disponibles.
- `lifeofcapo/car-api`, incluyendo `car-parts.json`.
- `filippofilip95/car-logos-dataset`, incluyendo `logos/data.json`.

Antes de utilizarlas, verifica su disponibilidad, estructura, licencias y compatibilidad.

No asumas que los archivos, cantidades de componentes o rutas permanecen invariables.

No sobrescribas datos existentes sin comprobar su correspondencia.

## 15. Reparar el catálogo de marcas y modelos

Actualmente existen problemas con catálogos que aparecen vacíos o incompletos.

Investiga si la causa está en:

- Importaciones fallidas.
- Tablas vacías.
- Relaciones incorrectas.
- Consultas.
- Filtros.
- Servicios.
- Permisos.
- Componentes frontend.

Comprueba que los datos importados puedan seleccionarse realmente desde los formularios.

## 16. Reparar el catálogo de repuestos

El catálogo debe mostrar los repuestos disponibles en las fuentes de datos y los añadidos manualmente.

Cada repuesto puede contener:

- Código interno.
- Nombre.
- Categoría.
- Descripción.
- Compatibilidad.
- Marca o fabricante.
- Precio referencial.
- Stock, cuando aplique.
- Estado activo.
- Procedencia del registro.

No confundas el catálogo de piezas con el inventario físico del taller.

## 17. Incorporar correctamente los logotipos

Relaciona los logotipos disponibles con las marcas de vehículos.

Utiliza normalización de nombres cuando sea necesario.

Evita asociaciones incorrectas entre marcas parecidas.

Si una marca no tiene logotipo, utiliza una representación visual predeterminada.

Los formularios deben seguir funcionando aunque falten imágenes o servicios externos.

## 18. Mantener información en español y orientada a Ecuador

Toda la interfaz y los catálogos deben estar en español siempre que resulte adecuado.

Conserva marcas, códigos y términos técnicos que deban mantenerse en su idioma original.

Utiliza convenciones apropiadas para Ecuador:

- Moneda USD.
- Placas.
- Identificación.
- Teléfonos.
- Fechas.
- Direcciones.
- Factores tributarios configurables.

No inventes datos específicos de Ecuador cuando solo estén disponibles referencias generales.

## 19. Implementar búsqueda flexible

Permite buscar vehículos y repuestos por:

- Nombre.
- Código.
- Marca.
- Modelo.
- Categoría.
- Palabras relacionadas.
- Compatibilidad.

Si el proyecto dispone de búsqueda vectorial o semántica, evalúa su utilidad real.

La búsqueda tradicional debe funcionar siempre.

No conviertas una base de datos vectorial ni una API de inteligencia artificial en una dependencia obligatoria.

---

# FASE D — CATÁLOGO DE ACTIVIDADES Y MANTENIMIENTOS

## 20. Crear un catálogo independiente de actividades

Las actividades de mantenimiento no deben depender exclusivamente del formulario de edición de una orden.

Crea o adapta un catálogo reutilizable.

Ejemplos:

- Cambio de aceite.
- Cambio de filtros.
- Revisión de frenos.
- Revisión de neumáticos.
- Alineación.
- Balanceo.
- Diagnóstico electrónico.
- Inspección de suspensión.
- Revisión de refrigeración.
- Inspección eléctrica.

Cada actividad puede contener:

- Identificador.
- Nombre.
- Descripción.
- Categoría.
- Duración estimada.
- Estado.
- Indicaciones técnicas opcionales.

## 21. Implementar plantillas de mantenimiento

Permite crear tipos de mantenimiento con actividades predeterminadas.

Por ejemplo:

- Preventivo básico.
- Preventivo completo.
- Preventivo por kilometraje.
- Correctivo.
- Diagnóstico general.
- Personalizado.

Cada plantilla debe contener actividades seleccionables.

Las plantillas se administran en una sección independiente.

## 22. Crear mantenimientos mediante selección de actividades

Al crear una orden:

1. Seleccionar cliente.
2. Seleccionar vehículo.
3. Seleccionar tipo de mantenimiento.
4. Cargar actividades sugeridas.
5. Marcar las actividades que se incluirán.
6. Desmarcar las que no correspondan.
7. Añadir actividades manuales.
8. Asignar responsables.
9. Guardar la orden.

No obligues al usuario a seleccionar actividad por actividad cuando ya existe una plantilla.

## 23. Separar selección y ejecución del checklist

Existen dos procesos diferentes.

**Checklist de creación:** define cuáles actividades formarán parte de la orden.

**Checklist operativo:** controla cuáles actividades ya fueron realizadas.

No utilices un único campo booleano para representar ambos conceptos.

El checklist de ejecución debe admitir:

- Pendiente.
- En proceso.
- Completada.
- No aplicable.

Puede incorporar:

- Mecánico responsable.
- Fecha y hora de ejecución.
- Observaciones.
- Repuestos empleados.
- Evidencias opcionales.

## 24. Permitir actividades manuales

El sistema híbrido debe aceptar actividades fuera del catálogo.

Al agregarlas, permite elegir entre:

- Utilizarlas solamente en la orden.
- Guardarlas en el catálogo para reutilizarlas.

No obligues al usuario a modificar una plantilla global para atender un caso especial.

## 25. Conservar el historial de las órdenes

Una orden debe conservar una copia de las actividades y condiciones que tenía cuando fue creada.

Modificar posteriormente una plantilla no debe alterar órdenes históricas.

Evita duplicar actividades al editar una orden.

Si una actividad ya fue ejecutada, aplica reglas de autorización y trazabilidad antes de modificarla o retirarla.

---

# FASE E — ÓRDENES DE TRABAJO Y TALLER

## 26. Completar los datos obligatorios de mantenimiento

Cada orden debe incluir:

- Código único.
- Identificador del vehículo.
- Fecha y hora de ingreso.
- Tipo de mantenimiento.
- Descripción del problema o servicio solicitado.
- Diagnóstico técnico.
- Técnico responsable.
- Servicios realizados.
- Repuestos utilizados.
- Costo de mano de obra.
- Costo de repuestos.
- Impuestos aplicables.
- Total a pagar.
- Fecha estimada de entrega.
- Fecha real de entrega, cuando exista.

Diferencia claramente campos iniciales, de diagnóstico, de ejecución y de cierre.

## 27. Corregir definitivamente la vista de taller

La vista de taller sigue presentando problemas de funcionamiento.

Analiza la causa completa y corrígela.

Verifica:

- Rutas.
- Componentes.
- Estados internos.
- Consultas a base de datos.
- Comunicación con backend.
- Carga de vehículos.
- Órdenes.
- Mecánicos asignados.
- Permisos.
- Eventos de interfaz.
- Actualizaciones de estado.

No consideres solucionado el problema únicamente porque aparece la pantalla.

## 28. Corregir la plantilla SVG del taller

Si existe un plano, mapeado o representación SVG del taller, revisa su integración.

Comprueba:

- Renderizado.
- Tamaño y escalado.
- Interacciones.
- Selección de vehículos.
- Visualización de espacios.
- Información contextual.
- Correspondencia con órdenes reales.

Si es necesario adaptar el SVG, conserva el estilo visual existente y evita sustituirlo por una pantalla genérica.

## 29. Mejorar las asignaciones de mecánicos

Un administrador debe poder asignar órdenes o actividades a mecánicos autorizados.

Cada mecánico debe visualizar principalmente:

- Trabajos asignados.
- Vehículo.
- Servicio solicitado.
- Diagnóstico disponible.
- Checklist.
- Estado.
- Prioridad.
- Fecha estimada.
- Observaciones correspondientes.

No debe tener que navegar entre varios módulos para encontrar una tarea.

## 30. Implementar seguimiento de estados

Establece un flujo de estados coherente, por ejemplo:

- Recibido.
- Pendiente de diagnóstico.
- En diagnóstico.
- Pendiente de autorización.
- En mantenimiento.
- En espera de repuestos.
- Listo para entrega.
- Entregado.

Conserva estados existentes que sean útiles y compatibles.

Cada cambio debe actualizar correctamente el estado de la orden y su representación en taller.

## 31. Registrar historial de estados

Conserva información sobre cambios relevantes:

- Estado anterior.
- Estado nuevo.
- Fecha y hora.
- Usuario responsable.
- Motivo, cuando corresponda.

No dependas únicamente de un campo que sobrescribe el estado anterior.

## 32. Corregir las observaciones ambiguas

Actualmente existe una sección de observaciones al final cuyo propósito no está claro.

Separa las observaciones por contexto:

- Cliente.
- Vehículo.
- Orden.
- Diagnóstico.
- Actividad.
- Motivo de demora.
- Entrega.

Utiliza etiquetas comprensibles.

No mantengas campos llamados simplemente "Observación" cuando el usuario no pueda identificar a qué corresponden.

## 33. Explicar los retrasos

Cuando exista una demora, debe identificarse:

- Actividad o etapa afectada.
- Motivo del retraso.
- Fecha estimada anterior.
- Nueva fecha estimada, si se conoce.
- Responsable del registro.
- Estado de resolución.

Ejemplos de motivo:

- Esperando repuesto.
- Esperando autorización.
- Diagnóstico adicional.
- Trabajo técnico pendiente.
- Otro motivo.

No confundas la fecha estimada con una fecha confirmada.

---

# FASE F — REPUESTOS, COSTOS Y CONTROL ECONÓMICO

## 34. Gestionar los repuestos utilizados

Cada orden debe permitir registrar:

- Repuesto.
- Cantidad.
- Precio unitario.
- Subtotal.
- Actividad relacionada, cuando corresponda.
- Observaciones.

Permite seleccionar desde catálogo o añadir manualmente.

Si existe inventario, actualiza el stock mediante operaciones controladas.

No descuentes existencias dos veces por editar o guardar nuevamente la misma orden.

## 35. Separar presupuestos de costos finales

Distingue:

- Servicios previstos.
- Repuestos previstos.
- Costos estimados.
- Servicios realmente ejecutados.
- Repuestos utilizados.
- Costos finales.

No conviertas automáticamente un presupuesto en una factura definitiva.

Permite registrar ajustes autorizados.

## 36. Implementar cálculos económicos consistentes

Calcula correctamente:

- Mano de obra.
- Repuestos.
- Subtotales.
- Descuentos, si corresponden.
- Impuestos.
- Total final.

Configura los impuestos de acuerdo con las condiciones aplicables en Ecuador, sin depender de una tasa fija incorporada permanentemente en el código.

Emplea tipos numéricos adecuados para valores monetarios, evitando errores de redondeo.

---

# FASE G — SISTEMA DE NOTIFICACIONES

## 37. Cumplir los tres eventos académicos obligatorios

MotorDesk debe generar registros de notificación para:

**Recepción del vehículo**

Datos:

- Nombre del cliente.
- Placa.
- Fecha de ingreso.
- Número de orden.

**Vehículo listo para entrega**

Datos:

- Nombre del cliente.
- Placa.
- Estado final.
- Disponibilidad para retiro.

**Información de pago**

Datos:

- Número de orden.
- Servicios realizados.
- Total a pagar.

No dependas de proveedores externos para generar el registro interno de estos eventos.

## 38. Implementar una estructura completa de notificaciones

Cada notificación debe incluir:

- Identificador.
- Destinatario.
- Cliente relacionado.
- Orden relacionada, cuando exista.
- Canal.
- Tipo de evento.
- Mensaje.
- Fecha de generación.
- Estado de envío.
- Fecha de envío, si existe.
- Error, cuando corresponda.
- Número de intentos.
- Información de trazabilidad.

Los estados académicos obligatorios son:

- Pendiente.
- Enviado.
- Fallido.

Puedes añadir estados internos complementarios si no comprometen esa compatibilidad.

## 39. Editar contactos directamente desde notificaciones

Esta es una corrección importante de UX.

Desde la propia pestaña de notificaciones se debe poder:

- Modificar el correo.
- Añadir o editar Telegram.
- Eliminar o desactivar Telegram.
- Actualizar WhatsApp.
- Activar o desactivar canales.
- Cambiar el canal preferido.
- Consultar el estado de configuración.

No obligues a regresar al módulo de clientes para una modificación sencilla.

Los cambios deben actualizar los registros relacionados sin producir duplicados.

## 40. Evitar saturación del panel de notificaciones

No quiero una pestaña que acumule indefinidamente avisos irrelevantes.

Implementa:

- Filtros por estado.
- Filtros por canal.
- Filtros por fecha.
- Búsqueda.
- Archivo o descarte de avisos.
- Limpieza controlada del panel.
- Actualización de la vista sin recargar toda la página, cuando sea viable.
- Indicadores de pendientes.
- Separación entre notificaciones activas e historial.

Archivar o quitar un aviso de la vista no debe destruir necesariamente su historial de auditoría.

## 41. Permitir notificaciones con y sin proveedores externos

El sistema debe funcionar aunque no haya API de correo, Telegram o WhatsApp.

**Sin integración:**

- Generar registro interno.
- Guardar pendiente.
- Mostrar el mensaje.
- Permitir copia o preparación manual.
- No simular envío exitoso.

**Con integración:**

- Enviar mediante un proveedor autorizado.
- Registrar resultado.
- Actualizar estado.
- Manejar fallos.
- Mantener trazabilidad.

Las integraciones deben ser opcionales.

## 42. Prevenir duplicados y gestionar reintentos

Implementa idempotencia para los eventos de notificación.

Utiliza una identificación coherente basada en la orden, el evento, el destinatario y el canal cuando corresponda.

Al reintentar un envío:

- No crees notificaciones adicionales innecesarias.
- Registra el intento.
- Conserva el error anterior cuando sea útil.
- Actualiza el resultado.
- Limita los reintentos.
- Evita ciclos infinitos.

Distingue un mensaje generado de uno realmente entregado o aceptado por el proveedor.

---

# FASE H — REQUISITOS ACADÉMICOS Y JSON

## 43. Cumplir íntegramente las cinco fases académicas

MotorDesk debe satisfacer los requisitos originales:

**Fase 1:** registro de clientes y relación uno a muchos con vehículos.

**Fase 2:** registro de vehículos relacionados con clientes.

**Fase 3:** mantenimientos preventivos y correctivos, servicios, repuestos, costos y fechas.

**Fase 4:** seguimiento del estado de cada vehículo ingresado al taller.

**Fase 5:** notificaciones de recepción, disponibilidad de entrega e información de pago.

No confundas funcionalidades adicionales con cumplimiento de los requisitos mínimos.

## 44. Construir un JSON académico válido

Diseña un archivo JSON capaz de representar los datos obligatorios.

Debe contemplar, como mínimo, colecciones o estructuras equivalentes para:

- Clientes.
- Vehículos.
- Órdenes de mantenimiento.
- Estados de mantenimiento.
- Notificaciones.

Puedes incorporar colecciones adicionales para actividades, plantillas, repuestos y técnicos.

Utiliza identificadores consistentes, referencias válidas, tipos de datos adecuados y fechas normalizadas.

Diferencia claramente valores ausentes de cadenas vacías.

No incluyas contraseñas ni secretos en el JSON académico.

## 45. Incorporar validación JSON Schema

Genera un esquema para validar la estructura exportada.

Comprueba:

- Campos obligatorios.
- Tipos.
- Enumeraciones.
- Identificadores.
- Formatos.
- Estados.
- Relaciones mediante validaciones adicionales cuando JSON Schema no sea suficiente.

El archivo debe ser JSON válido y representar correctamente la información del sistema.

## 46. Exportar e importar datos

Implementa exportación JSON sin depender de API externas.

Para importaciones, incorpora:

- Validación previa.
- Comprobación de versión.
- Detección de duplicados.
- Integridad referencial.
- Gestión de conflictos.
- Manejo de errores.

No reemplaces indiscriminadamente información existente.

Distingue la importación de registros del proceso de restaurar una copia completa.

---

# FASE I — ARQUITECTURA HÍBRIDA Y FUNCIONAMIENTO AUTÓNOMO

## 47. Funcionar con y sin API externas

Las funciones principales de MotorDesk no deben depender de internet ni de servicios externos.

Deben funcionar de manera autónoma:

- Inicio de sesión local.
- Clientes.
- Vehículos.
- Taller.
- Mantenimientos.
- Checklists.
- Catálogos precargados.
- Costos.
- Historial.
- Notificaciones internas.
- Exportaciones.
- Copias de seguridad.

Es importante distinguir entre una API externa y una API interna del propio backend.

Si el frontend necesita comunicarse con un backend local, esa arquitectura puede mantenerse.

## 48. Funcionar con y sin Docker

MotorDesk debe admitir, cuando el stack lo permita, cuatro modalidades:

1. Local sin Docker y sin API externas.
2. Local sin Docker y con integraciones externas.
3. Docker sin integraciones externas obligatorias.
4. Docker con integraciones externas.

No implementes cuatro sistemas distintos.

Reutiliza el mismo núcleo de negocio y utiliza adaptadores de infraestructura según el modo seleccionado.

## 49. Disponer de persistencia autónoma

Investiga la base de datos existente.

Evalúa SQLite para instalaciones individuales, si resulta compatible con el stack.

Si existe PostgreSQL u otro motor, estudia cómo ofrecer una alternativa local sin duplicar reglas de negocio ni perjudicar la integridad.

Utiliza:

- Migraciones.
- Claves e índices.
- Restricciones.
- Transacciones.
- Integridad referencial.
- Copias de seguridad.

No utilices localStorage como almacenamiento principal del taller.

## 50. Trabajar sin conexión permanente

Una instalación autónoma debe poder continuar funcionando sin internet.

Si las API externas no están disponibles, desactiva o aplaza solamente las funciones que realmente las necesiten.

No pierdas órdenes, actividades ni información registrada.

Los catálogos locales deben seguir disponibles.

No afirmes compatibilidad offline si la autenticación o las operaciones principales todavía dependen de un servidor externo.

## 51. Distinguir trabajo local, red local y sincronización

Considera tres escenarios diferentes:

**Equipo individual:** aplicación y datos en una computadora.

**Red local:** una instalación central atiende dispositivos autorizados dentro del taller.

**Instalaciones independientes:** diferentes equipos almacenan información separada.

No confundas acceso en red con sincronización de bases de datos.

Si la sincronización entre instalaciones resulta necesaria, diseña previamente resolución de conflictos, identificadores y reglas de integridad.

No implementes sincronización improvisada que pueda duplicar o sobrescribir órdenes.

---

# FASE J — INSTALACIÓN, PORTABILIDAD Y DISTRIBUCIÓN

## 52. Preparar una instalación sencilla para terceros

Quiero poder comprimir MotorDesk, enviárselo a una persona y que pueda utilizarlo.

Prioriza un paquete para Windows, sin descartar Linux cuando sea compatible.

Si el stack permite generar un instalador o aplicación autocontenida, evalúa esa opción.

El usuario final no debería tener que abrir varias terminales ni configurar manualmente numerosos servicios.

No cambies el framework únicamente para obtener un ejecutable si existe una alternativa de empaquetado más simple.

## 53. Preparar dos paquetes diferenciados

**Paquete para usuario final**

Debe contener lo necesario para instalar o ejecutar MotorDesk de forma sencilla.

Incluye, según corresponda:

- Aplicación empaquetada.
- Lanzador.
- Componentes locales necesarios.
- Recursos estáticos.
- Inicialización de base de datos.
- Instrucciones breves.

**Paquete técnico**

Debe contener:

- Código fuente.
- Dependencias declaradas.
- Configuraciones de ejemplo.
- Scripts.
- Migraciones.
- Docker Compose, cuando corresponda.
- Documentación de desarrollo.

Un ZIP de código fuente no debe presentarse falsamente como una aplicación lista para ejecutar.

## 54. Crear un asistente de primera ejecución

Cuando el usuario inicie MotorDesk por primera vez, el sistema debe permitir:

1. Crear o inicializar la base de datos.
2. Registrar el nombre del taller.
3. Configurar los datos generales.
4. Crear el administrador principal.
5. Elegir las preferencias básicas.
6. Configurar canales de notificación de forma opcional.
7. Comenzar a utilizar el sistema.

No obligues al usuario a contratar servicios ni introducir tokens externos para completar la instalación.

## 55. Implementar copias de seguridad y restauración

El sistema debe poder generar copias de seguridad operativas.

Diferencia:

- Exportación JSON académica.
- Respaldo completo del negocio.

El respaldo debe permitir recuperar los datos necesarios para continuar trabajando.

La restauración debe validar la versión, comprobar la integridad y evitar sobrescrituras accidentales.

Las exportaciones destinadas a terceros no deben exponer credenciales, tokens ni secretos.

---

# FASE K — EXPERIENCIA DE USUARIO, CALIDAD Y SEGURIDAD

## 56. Mejorar la interfaz sin volverla genérica

Conserva la identidad visual y los recursos personalizados del proyecto.

Revisa las paletas de colores, componentes, iconografía, botones, SVG y estilos existentes antes de modificarlos.

Prioriza:

- Navegación clara.
- Menos clics.
- Formularios compactos.
- Acciones contextuales.
- Paneles laterales cuando sean útiles.
- Modales para operaciones breves.
- Búsquedas rápidas.
- Tablas legibles.
- Diseño adaptable.
- Estados de carga y error.
- Mensajes comprensibles.

No introduzcas colores o componentes inconsistentes con el diseño actual.

## 57. Optimizar rendimiento y confiabilidad

Revisa consultas, índices, servicios y carga de recursos.

Evita:

- Consultas duplicadas.
- Cargas completas innecesarias.
- Solicitudes continuas a servicios externos.
- Estados de interfaz inconsistentes.
- Operaciones que bloquean toda la aplicación.
- Dependencias ocultas del entorno de desarrollo.

Implementa registros de errores útiles, sin exponer información sensible.

## 58. Aplicar controles de seguridad

Verifica:

- Autenticación.
- Permisos por rol.
- Validación de entradas.
- Protección de credenciales.
- Seguridad de sesiones.
- Manejo de secretos.
- Restricciones de acceso a información de clientes.
- Seguridad de importaciones.
- Configuración de red.
- Protección de respaldos.

Por defecto, una instalación individual no debe exponerse públicamente a internet.

Si se habilita acceso desde otros equipos, documenta las medidas de seguridad necesarias.

## 59. Ejecutar pruebas integrales

No basta con comprobar que el proyecto compila.

Prueba los procesos reales:

**Clientes y usuarios**

- Registrar cliente.
- Editar información.
- Crear cuenta.
- Activar acceso.
- Iniciar sesión.
- Verificar permisos.

**Vehículos**

- Registrar varios vehículos.
- Consultar propietario.
- Editar datos.
- Consultar historial.

**Taller**

- Abrir la vista.
- Cargar órdenes.
- Asignar mecánicos.
- Actualizar estados.
- Consultar el SVG.
- Comprobar restricciones de acceso.

**Mantenimientos**

- Crear plantilla.
- Seleccionar actividades.
- Desmarcar actividades.
- Añadir actividades manuales.
- Ejecutar checklist.
- Registrar repuestos.
- Calcular costos.
- Cerrar orden.
- Preservar historial.

**Notificaciones**

- Generar los tres eventos obligatorios.
- Editar correo y Telegram desde la propia pestaña.
- Desactivar canales.
- Gestionar mensajes pendientes.
- Simular fallos.
- Registrar errores.
- Evitar duplicados.

**Portabilidad**

- Ejecutar sin Docker.
- Ejecutar con Docker.
- Ejecutar sin internet.
- Ejecutar sin API externas.
- Cerrar y reabrir sin perder datos.
- Exportar JSON.
- Restaurar respaldo.
- Probar el paquete en un entorno limpio.

Documenta qué pruebas fueron automatizadas, cuáles fueron manuales y cuáles no pudieron ejecutarse.

## 60. Entregar resultados verificables y completos

Trabaja siguiendo este orden:

**Fase 1 — Inspección**

Diagnostica el proyecto y produce una matriz de cumplimiento.

**Fase 2 — Corrección**

Soluciona errores existentes, comenzando por taller, autenticación y relaciones de datos.

**Fase 3 — Optimización**

Implementa catálogos reutilizables, checklist híbridos, notificaciones y mejoras de UX.

**Fase 4 — Cumplimiento académico**

Completa las cinco fases, genera el JSON y valida su estructura.

**Fase 5 — Arquitectura autónoma**

Adapta el funcionamiento sin API externas y sin Docker.

**Fase 6 — Distribución**

Prepara la instalación, el paquete para terceros y las instrucciones.

**Fase 7 — Validación**

Ejecuta pruebas funcionales, de seguridad, integridad y portabilidad.

**Fase 8 — Informe final**

Entrega:

- Resumen del diagnóstico inicial.
- Problemas corregidos.
- Funcionalidades implementadas.
- Archivos modificados.
- Cambios de base de datos.
- Migraciones ejecutadas.
- JSON académico.
- Esquema de validación.
- Resultado de las pruebas.
- Modos de ejecución disponibles.
- Instrucciones de instalación.
- Paquetes distribuibles que efectivamente se hayan generado.
- Problemas pendientes y limitaciones verificadas.
- Matriz final de cumplimiento.

No marques una funcionalidad como completada si no existe evidencia suficiente.

---

# CRITERIOS GENERALES DE ACEPTACIÓN

Antes de finalizar, comprueba que MotorDesk satisface estos objetivos:

**1. Funcionalidad:** los procesos esenciales del taller funcionan correctamente.

**2. Usabilidad:** las operaciones frecuentes requieren pocos pasos y están disponibles donde se necesitan.

**3. Reutilización:** las plantillas de mantenimiento permiten actividades predeterminadas y manuales.

**4. Integridad:** los datos conservan sus relaciones y su historial.

**5. Seguridad:** cada usuario accede únicamente a lo autorizado.

**6. Autonomía:** las funciones principales trabajan sin proveedores externos.

**7. Portabilidad:** el proyecto puede ejecutarse fuera de la computadora del desarrollador.

**8. Compatibilidad:** Docker es opcional y no un requisito universal.

**9. Cumplimiento académico:** las cinco fases y el archivo JSON satisfacen los requisitos originales.

**10. Mantenibilidad:** el código queda organizado, documentado y preparado para evolucionar.

# REGLAS FINALES PARA LA IA

- No reconstruyas MotorDesk desde cero.
- No elimines funcionalidades que actualmente trabajan.
- No inventes integraciones exitosas.
- No simules persistencia real con datos estáticos.
- No elimines registros existentes sin autorización.
- No expongas contraseñas ni secretos.
- No confundas una maqueta visual con una función terminada.
- No cambies innecesariamente el estilo visual.
- No conviertas las API externas en dependencias obligatorias.
- No dependas de Docker para el funcionamiento local.
- No modifiques órdenes históricas al editar plantillas.
- No confundas actividades seleccionadas con actividades completadas.
- No elimines opciones manuales de registro.
- No declares pruebas completadas si no se ejecutaron.
- No afirmes que un ZIP es portable sin verificarlo.
- No introduzcas complejidad innecesaria.
- No sacrifiques la integridad de los datos por simplificar formularios.

**AUTONOMÍA DE EJECUCIÓN**

No te limites a darme una lista de recomendaciones.

Debes inspeccionar el repositorio, realizar las modificaciones técnicamente viables, ejecutar pruebas y entregar resultados comprobables.

Si encuentras una decisión técnica con varias opciones, analiza su compatibilidad con el proyecto y utiliza la alternativa más sencilla y mantenible que satisfaga los requisitos.

Evita solicitar confirmaciones por decisiones menores que puedas resolver con fundamento técnico.

Si una modificación implica pérdida de datos, eliminación de funciones o sustitución irreversible de infraestructura, detén solamente esa operación y explica el riesgo.

**OBJETIVO DEFINITIVO**

Quiero que MotorDesk deje de ser simplemente una aplicación en desarrollo y se convierta en una solución automotriz funcional, organizada, reutilizable y portable.

Debe poder utilizarse en talleres de Ecuador, funcionar localmente, permitir futuras integraciones y cumplir íntegramente la tarea académica del sistema de gestión automotriz mediante JSON.

Quiero poder enviárselo a otra persona, que lo instale, cree su taller, registre clientes y vehículos, administre mantenimientos, trabaje con sus mecánicos y conserve toda su información.

**La prioridad es que MotorDesk funcione correctamente de principio a fin, no que solamente parezca terminado.**
