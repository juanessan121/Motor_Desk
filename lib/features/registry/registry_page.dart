import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart';
import '../../core/config/atelier_tokens.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';
import 'registry_forms.dart';
import 'customer_flow.dart';
import 'maintenance_catalog_page.dart';

enum RegistryKind { customers, vehicles, catalogs }

class RegistryPage extends StatelessWidget {
  const RegistryPage({super.key, required this.kind});
  final RegistryKind kind;

  @override
  Widget build(BuildContext context) {
    if (kind == RegistryKind.catalogs) return const MaintenanceCatalogPage();
    final state = context.watch<WorkshopController>();
    final (title, subtitle, button, endpoint) = switch (kind) {
      RegistryKind.customers => (
        'Clientes',
        'Relaciones que duran más que un mantenimiento.',
        'Nuevo cliente',
        '/customers',
      ),
      RegistryKind.vehicles => (
        'Vehículos',
        'Cada vehículo con su propietario y su historia.',
        'Ingresar vehículo',
        '/vehicles',
      ),
      RegistryKind.catalogs => (
        'Catálogo de mantenimientos',
        'Estandariza tus servicios sin perder ningún detalle.',
        'Nuevo mantenimiento',
        '/catalogs',
      ),
    };
    final records = switch (kind) {
      RegistryKind.customers => state.customers.map((row) => row.json).toList(),
      RegistryKind.vehicles => state.vehicles.map((row) => row.json).toList(),
      RegistryKind.catalogs => state.catalogs.map((row) => row.json).toList(),
    };
    final columns = switch (kind) {
      RegistryKind.customers => [
        RecordColumn(
          'Cliente',
          (row) => row['full_name'] as String,
          cell: (row) => Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: Theme.of(
                  context,
                ).colorScheme.primary.withValues(alpha: .09),
                child: Text(
                  (row['first_name'] as String)[0].toUpperCase(),
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.primary,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    row['full_name'] as String,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    row['username'] as String,
                    style: TextStyle(
                      fontSize: 11,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        RecordColumn('Cédula', (row) => row['national_id'] as String),
        RecordColumn('Correo', (row) => row['email'] as String),
        RecordColumn(
          'Teléfono / WA',
          (row) =>
              (row['whatsapp'] != null &&
                  (row['whatsapp'] as String).isNotEmpty)
              ? '${row['phone'] ?? ''}\nWA: ${row['whatsapp']}'
              : (row['phone'] as String? ?? '—'),
        ),
        RecordColumn(
          'Canal',
          (row) => switch (row['notification_channel']) {
            'whatsapp' => 'WhatsApp',
            'telegram' => 'Telegram',
            _ => 'Email',
          },
        ),
        RecordColumn(
          'Acceso portal',
          (row) => (row['access_status'] ?? 'sin_cuenta') as String,
          cell: (row) {
            final st = (row['access_status'] ?? 'sin_cuenta') as String;
            final (label, color) = switch (st) {
              'activo' => ('Activo', context.atelier.success),
              'pendiente_activacion' => ('Pendiente', context.atelier.warning),
              'deshabilitado' => ('Deshabilitado', Colors.grey),
              _ => ('Sin cuenta', context.atelier.secondaryText),
            };
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: color, width: 0.8),
              ),
              child: Text(
                label,
                style: TextStyle(
                  color: color,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            );
          },
        ),
      ],
      RegistryKind.vehicles => [
        RecordColumn(
          'Placa',
          (row) => row['plate'] as String,
          cell: (row) => Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              row['plate'] as String,
              style: const TextStyle(
                fontWeight: FontWeight.w800,
                letterSpacing: 1,
              ),
            ),
          ),
        ),
        RecordColumn('Vehículo', (row) => '${row['brand']} ${row['model']}'),
        RecordColumn(
          'Color',
          (row) => (row['color'] as String?)?.isNotEmpty == true
              ? row['color'] as String
              : 'No especificado',
        ),
        RecordColumn(
          'Combustible',
          (row) => (row['fuel_type'] as String?)?.isNotEmpty == true
              ? (row['fuel_type'] as String).toUpperCase()
              : 'GASOLINA',
        ),
        RecordColumn('Propietario', (row) => row['owner_name'] as String),
        RecordColumn('Año', (row) => '${row['year']}'),
        RecordColumn('Kilometraje', (row) => '${row['mileage']} km'),
      ],
      RegistryKind.catalogs => [
        RecordColumn('Servicio', (row) => row['name'] as String),
        RecordColumn(
          'Descripción',
          (row) => row['description'] as String,
          cell: (row) => SizedBox(
            width: 230,
            child: Text(
              row['description'] as String,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ),
        RecordColumn(
          'Tareas',
          (row) => '${(row['tasks'] as List).length} tareas',
        ),
        RecordColumn('Precio base', (row) => money(row['base_price'])),
      ],
    };
    Future<void> edit([Json? row]) => switch (kind) {
      RegistryKind.customers =>
        row == null
            ? startCustomerFlow(context)
            : editCustomer(context, Customer(row)),
      RegistryKind.vehicles =>
        row == null
            ? startVehicleFlow(context)
            : editVehicle(context, Vehicle(row)),
      RegistryKind.catalogs => editCatalog(
        context,
        row == null ? null : MaintenanceCatalog(row),
      ),
    };
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PageHeading(
            title: title,
            subtitle: subtitle,
            action: state.isAdmin
                ? FilledButton.icon(
                    onPressed: () => edit(),
                    icon: const Icon(Icons.add_rounded, size: 20),
                    label: Text(button),
                  )
                : null,
          ),
          const SizedBox(height: 28),
          RecordTable(
            key: ValueKey(kind),
            records: records,
            columns: columns,
            emptyTitle: 'Todavía no hay registros',
            actions: (row) => Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (kind == RegistryKind.vehicles)
                  IconButton(
                    tooltip: 'Historial técnico',
                    onPressed: () => showVehicleHistory(context, Vehicle(row)),
                    icon: const Icon(Icons.history_rounded, size: 19),
                  ),
                if (state.isAdmin) ...[
                  IconButton(
                    tooltip: 'Editar',
                    onPressed: () => edit(row),
                    icon: const Icon(Icons.edit_outlined, size: 19),
                  ),
                  if (kind == RegistryKind.vehicles)
                    IconButton(
                      tooltip: 'Traspasar propietario',
                      onPressed: () => transferVehicle(context, Vehicle(row)),
                      icon: const Icon(Icons.swap_horiz_rounded, size: 20),
                    ),
                  if (kind == RegistryKind.customers) ...[
                    if ((row['access_status'] ?? 'sin_cuenta') == 'sin_cuenta')
                      IconButton(
                        tooltip: 'Habilitar acceso al portal',
                        onPressed: () async {
                          if (await confirmAction(
                            context,
                            '¿Habilitar acceso web para este cliente?',
                            'Se creará una cuenta asociada y se generará un enlace seguro de activación para que establezca su contraseña.',
                          )) {
                            if (context.mounted) {
                              await runAction(context, () async {
                                final res =
                                    await state.api.request(
                                          'POST',
                                          '/customers/${row['id']}/enable-access',
                                        )
                                        as Json;
                                await state.refresh();
                                if (context.mounted) {
                                  _showActivationLinkDialog(context, res);
                                }
                              }, success: 'Acceso habilitado.');
                            }
                          }
                        },
                        icon: const Icon(Icons.lock_open_outlined, size: 19),
                      ),
                    if ((row['access_status'] ?? 'sin_cuenta') ==
                        'pendiente_activacion')
                      IconButton(
                        tooltip: 'Ver enlace de activación',
                        onPressed: () async {
                          await runAction(context, () async {
                            final res =
                                await state.api.request(
                                      'POST',
                                      '/customers/${row['id']}/activation-link',
                                    )
                                    as Json;
                            if (context.mounted) {
                              _showActivationLinkDialog(context, res);
                            }
                          });
                        },
                        icon: const Icon(Icons.link_outlined, size: 19),
                      ),
                    IconButton(
                      tooltip: 'Restablecer acceso / clave',
                      onPressed: () async {
                        if (await confirmAction(
                          context,
                          '¿Restablecer credenciales?',
                          'La contraseña anterior dejará de funcionar y se enviará una notificación con el nuevo acceso.',
                        )) {
                          if (context.mounted) {
                            await runAction(
                              context,
                              () => state.mutate(
                                'POST',
                                '/customers/${row['id']}/credentials',
                              ),
                              success: 'Nuevo acceso en cola de envío.',
                            );
                          }
                        }
                      },
                      icon: const Icon(Icons.key_outlined, size: 19),
                    ),
                  ],
                  IconButton(
                    tooltip: 'Archivar / desactivar',
                    onPressed: () async {
                      if (await confirmAction(
                        context,
                        '¿Archivar este registro?',
                        'Se ocultará de las listas activas. El historial de las órdenes se conserva.',
                      )) {
                        if (context.mounted) {
                          await runAction(
                            context,
                            () => state.mutate(
                              'DELETE',
                              '$endpoint/${row['id']}',
                            ),
                          );
                        }
                      }
                    },
                    icon: Icon(
                      Icons.archive_outlined,
                      size: 19,
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 18),
          Text(
            'Historial protegido · Los registros se archivan, no se eliminan físicamente.',
            style: TextStyle(
              color: context.atelier.secondaryText,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}

void _showActivationLinkDialog(BuildContext context, Json data) {
  final url = data['activation_url'] as String? ?? '';
  final token = data['activation_token'] as String? ?? '';
  showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.link_rounded, color: Colors.blue),
          SizedBox(width: 8),
          Text('Enlace de activación seguro'),
        ],
      ),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Entregue o envíe este enlace al cliente para que cree su contraseña de acceso personal:',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey.withOpacity(0.08),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: Colors.grey.withOpacity(0.3)),
              ),
              child: SelectableText(
                url.isNotEmpty ? url : 'Token: $token',
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Por motivos de seguridad, las contraseñas nunca se almacenan ni se muestran en texto plano. Este enlace es de un solo uso.',
              style: TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: const Text('Cerrar'),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.copy_rounded, size: 16),
          label: const Text('Copiar enlace'),
          onPressed: () {
            Clipboard.setData(
              ClipboardData(text: url.isNotEmpty ? url : token),
            );
            showMessage(context, 'Enlace copiado al portapapeles');
            Navigator.of(ctx).pop();
          },
        ),
      ],
    ),
  );
}
