import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';
import '../vehicles/vehicle_catalog_picker.dart';
import 'maintenance_editor.dart';

String? validateMoney(String value) =>
    RegExp(r'^\d{1,8}(\.\d{1,2})?$').hasMatch(value)
    ? null
    : 'Usa un valor positivo con hasta 2 decimales';
String? validateEmail(String value) =>
    RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(value)
    ? null
    : 'Correo electrónico no válido';
String? validateInteger(String value) =>
    int.tryParse(value) == null ? 'Usa un número entero' : null;

Future<int?> editCustomer(
  BuildContext context, [
  Customer? customer,
  bool guided = false,
]) async {
  int? savedId;
  final state = context.read<WorkshopController>();
  final initial = customer?.json ?? <String, dynamic>{};
  String text(String key) => initial[key]?.toString() ?? '';
  await showEditor(
    context,
    title: customer == null
        ? (guided ? 'Paso 1 de 3 · Nuevo cliente' : 'Nuevo cliente')
        : 'Editar cliente',
    submitLabel: guided ? 'Guardar y continuar al vehículo' : 'Guardar',
    description:
        'Puede registrar al cliente con o sin acceso al portal web. Los canales de notificación pueden configurarse individualmente.',
    fields: [
      EditorField(
        'national_id',
        'Cédula / identificación',
        initial: text('national_id'),
      ),
      EditorField('first_name', 'Nombre', initial: text('first_name')),
      EditorField('last_name', 'Apellido', initial: text('last_name')),
      EditorField(
        'email',
        'Correo electrónico',
        initial: text('email'),
        validate: validateEmail,
        keyboard: TextInputType.emailAddress,
      ),
      EditorField(
        'phone',
        'Teléfono fijo o convencional',
        initial: text('phone'),
        required: false,
        keyboard: TextInputType.phone,
      ),
      EditorField(
        'whatsapp',
        'WhatsApp / Móvil',
        initial: text('whatsapp').isEmpty ? text('phone') : text('whatsapp'),
        required: false,
        keyboard: TextInputType.phone,
      ),
      EditorField(
        'address',
        'Dirección',
        initial: text('address'),
        required: false,
      ),
      if (customer == null)
        EditorField(
          'has_portal_access',
          'Acceso al portal web',
          initial: 'true',
          options: const {
            'true': 'Crear cuenta con acceso al portal (enlace seguro)',
            'false': 'Solo registro en taller (sin cuenta web)',
          },
        ),
      EditorField(
        'notification_channel',
        'Canal de notificación preferido',
        initial: text('notification_channel').isEmpty
            ? 'email'
            : text('notification_channel'),
        options: const {
          'email': 'Correo electrónico (SMTP)',
          'whatsapp': 'WhatsApp',
          'telegram': 'Telegram Bot',
        },
      ),
      EditorField(
        'telegram_chat_id',
        'Telegram chat_id (opcional)',
        initial: text('telegram_chat_id'),
        required: false,
      ),
    ],
    onSubmit: (values) async {
      final Json payload = {
        ...values,
        'has_portal_access': values['has_portal_access'] == 'true',
        'whatsapp': values['whatsapp'] ?? '',
        'telegram_chat_id': values['telegram_chat_id']?.isEmpty ?? true
            ? null
            : values['telegram_chat_id'],
      };
      final result = await state.api.request(
        customer == null ? 'POST' : 'PUT',
        customer == null ? '/customers' : '/customers/${customer.id}',
        body: payload,
      );
      savedId = (result as Json)['id'] as int;
      await state.refresh();
      if (context.mounted) {
        showMessage(
          context,
          customer == null
              ? (values['has_portal_access'] == 'true'
                    ? 'Cliente registrado con acceso al portal. Enlace de activación listo.'
                    : 'Cliente registrado en el taller.')
              : 'Cliente actualizado.',
        );
      }
    },
  );
  return savedId;
}

Future<int?> editVehicle(
  BuildContext context, [
  Vehicle? vehicle,
  int? suggestedOwnerId,
  bool guided = false,
]) async {
  int? savedId;
  final state = context.read<WorkshopController>();
  if (state.customers.isEmpty) {
    showMessage(
      context,
      'Registra al menos un cliente antes de ingresar un vehículo.',
    );
    return null;
  }
  final initial = vehicle?.json ?? <String, dynamic>{};
  String text(String key) => initial[key]?.toString() ?? '';
  // Los campos de marca y modelo se editan a mano, pero el catálogo ofrece la
  // cascada y el registro manual de lo que las fuentes no traen.
  final brand = TextEditingController(text: text('brand'));
  final model = TextEditingController(text: text('model'));
  Json? selection;
  var selectionChanged = false;
  try {
    await showEditor(
      context,
      title: vehicle == null
          ? (guided ? 'Paso 2 de 3 · Ingresar vehículo' : 'Ingresar vehículo')
          : 'Editar vehículo',
      submitLabel: guided ? 'Guardar y continuar a la orden' : 'Guardar',
      description:
          'El historial pertenece al vehículo. Para cambiar de dueño utiliza la acción de traspaso.',
      fields: [
        if (vehicle == null)
          EditorField(
            'owner_id',
            'Propietario',
            initial: suggestedOwnerId?.toString() ?? '',
            options: {
              for (final customer in state.customers)
                '${customer.id}': customer.name,
            },
          ),
        EditorField('plate', 'Placa / matrícula', initial: text('plate')),
        EditorField('brand', 'Marca', initial: text('brand')),
        EditorField('model', 'Modelo', initial: text('model')),
        EditorField(
          'color',
          'Color',
          initial: text('color').isEmpty ? 'Blanco' : text('color'),
          required: false,
        ),
        EditorField(
          'fuel_type',
          'Tipo de combustible',
          initial: text('fuel_type').isEmpty ? 'gasolina' : text('fuel_type'),
          options: const {
            'gasolina': 'Gasolina',
            'diesel': 'Diésel',
            'hibrido': 'Híbrido',
            'electrico': 'Eléctrico',
            'glp': 'GLP',
          },
        ),
        EditorField(
          'year',
          'Año',
          initial: text('year').isEmpty
              ? '${DateTime.now().year}'
              : text('year'),
          keyboard: TextInputType.number,
          validate: validateInteger,
        ),
        EditorField(
          'mileage',
          'Kilometraje',
          initial: text('mileage').isEmpty ? '0' : text('mileage'),
          keyboard: TextInputType.number,
          validate: validateInteger,
        ),
        EditorField(
          'vin',
          'VIN / chasis',
          initial: text('vin'),
          required: false,
        ),
      ],
      extra: VehicleCatalogPicker(
        api: state.api,
        brandController: brand,
        modelController: model,
        // El año ya está en el formulario: no se muestra una segunda copia.
        showYear: false,
        initialReference: initial['catalog'] as Json?,
        onChanged: (value) {
          selection = value;
          selectionChanged = true;
        },
      ),
      sharedControllers: {'brand': brand, 'model': model},
      onSubmit: (values) async {
        final result = await state.api.request(
          vehicle == null ? 'POST' : 'PUT',
          vehicle == null ? '/vehicles' : '/vehicles/${vehicle.id}',
          body: {
            ...values,
            'owner_id': vehicle?.ownerId ?? int.parse(values['owner_id']!),
            'year': int.parse(values['year']!),
            'mileage': int.parse(values['mileage']!),
            'color': values['color']?.isEmpty ?? true
                ? 'No especificado'
                : values['color'],
            'fuel_type': values['fuel_type'] ?? 'gasolina',
            'vin': values['vin']!.isEmpty ? null : values['vin'],
            if (selectionChanged)
              for (final level in ['make', 'model', 'generation', 'engine'])
                'catalog_${level}_id': (selection?[level] as Map?)?['id'],
          },
        );
        savedId = (result as Json)['id'] as int;
        await state.refresh();
      },
    );
  } finally {
    brand.dispose();
    model.dispose();
  }
  return savedId;
}

Future<void> transferVehicle(
  BuildContext context,
  Vehicle vehicle,
) => showEditor(
  context,
  title: 'Traspasar ${vehicle.plate}',
  description:
      'Las órdenes cerradas mantienen al pagador original. El nuevo dueño recibe solo el historial técnico, sin datos privados ni facturas anteriores.',
  fields: [
    EditorField(
      'owner_id',
      'Nuevo propietario',
      options: {
        for (final customer
            in context.read<WorkshopController>().customers.where(
              (customer) => customer.id != vehicle.ownerId,
            ))
          '${customer.id}': customer.name,
      },
    ),
  ],
  onSubmit: (values) => context.read<WorkshopController>().mutate(
    'POST',
    '/vehicles/${vehicle.id}/transfer',
    body: {'owner_id': int.parse(values['owner_id']!)},
  ),
);

Future<void> editCatalog(BuildContext context, [MaintenanceCatalog? catalog]) =>
    editMaintenanceTemplate(context, catalog);

Future<void> showVehicleHistory(BuildContext context, Vehicle vehicle) {
  final future = context.read<WorkshopController>().api.request(
    'GET',
    '/vehicles/${vehicle.id}/history',
  );
  return showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('Historial · ${vehicle.plate}'),
      content: SizedBox(
        width: 550,
        child: FutureBuilder(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.hasError) return Text('${snapshot.error}');
            if (!snapshot.hasData) {
              return const SizedBox(
                height: 100,
                child: Center(child: CircularProgressIndicator()),
              );
            }
            final rows = jsonList(snapshot.data);
            if (rows.isEmpty) {
              return const Text('Este vehículo aún no registra servicios.');
            }
            return SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final row in rows)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(row['title'] as String),
                      subtitle: Text(
                        '${shortDate(row['date'])}\n${(row['tasks'] as List).join(' · ')}',
                      ),
                      isThreeLine: true,
                      trailing: StatusChip(row['status'] as String),
                    ),
                ],
              ),
            );
          },
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cerrar'),
        ),
      ],
    ),
  );
}
