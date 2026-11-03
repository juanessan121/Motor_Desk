import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart';
import '../../core/models/operation_key.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';
import '../vehicles/catalog_record_page.dart';
import 'assignment_editor.dart';

const taskStatusLabels = {
  'pending': 'Pendiente',
  'in_progress': 'En proceso',
  'completed': 'Completada',
  'not_applicable': 'No aplica',
  'attention': 'Requiere atención',
};
const operationStageLabels = {
  'received': 'Recibida',
  'pending_authorization': 'Pendiente de autorización',
  'assigned': 'Asignada',
  'in_progress': 'En proceso',
  'waiting': 'En espera de repuestos o decisión',
  'pending_review': 'Pendiente de revisión',
  'ready': 'Lista para entrega',
  'delivered': 'Entregada',
  'cancelled': 'Cancelada',
};

class ActivityTile extends StatelessWidget {
  const ActivityTile({
    super.key,
    required this.order,
    required this.item,
    required this.busy,
    required this.onAction,
  });
  final WorkOrder order;
  final Json item;
  final bool busy;
  final Future<void> Function(Future<void> Function()) onAction;
  String get status =>
      item['status'] as String? ??
      (item['completed'] == true ? 'completed' : 'pending');
  Future<void> _change(
    BuildContext context,
    String status, {
    String? notes,
  }) async {
    final state = context.read<WorkshopController>();
    if (['attention', 'not_applicable'].contains(status)) {
      await showEditor(
        context,
        title: taskStatusLabels[status]!,
        description:
            'Se conserva la actividad y el motivo en el historial. Una actividad en atención no cuenta como completada.',
        fields: [
          EditorField(
            'notes',
            'Observación / justificación',
            initial: notes ?? item['notes'] as String? ?? '',
            lines: 3,
          ),
        ],
        onSubmit: (values) => state.mutate(
          'PATCH',
          '/orders/${order.id}/items/${item['id']}',
          body: {
            'status': status,
            'notes': values['notes'],
            'expected_revision': item['revision'],
          },
        ),
      );
    } else {
      await onAction(
        () => state.mutate(
          'PATCH',
          '/orders/${order.id}/items/${item['id']}',
          body: {'status': status, 'expected_revision': item['revision']},
        ),
      );
    }
  }

  Future<void> _notes(BuildContext context) => showEditor(
    context,
    title: 'Observación técnica',
    description: 'Solo el personal autorizado ve estas observaciones internas.',
    fields: [
      EditorField(
        'notes',
        'Observación interna',
        initial: item['notes'] as String? ?? '',
        required: false,
        lines: 3,
      ),
    ],
    onSubmit: (values) => context.read<WorkshopController>().mutate(
      'PATCH',
      '/orders/${order.id}/items/${item['id']}',
      body: {'notes': values['notes'], 'expected_revision': item['revision']},
    ),
  );
  Future<void> _photo(BuildContext context) async {
    final state = context.read<WorkshopController>();
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['jpg', 'jpeg', 'png', 'webp'],
    );
    if (file == null) return;
    final size = await file.length();
    if (size == null || size > 5 * 1024 * 1024) {
      throw const ApiException('Selecciona una imagen de hasta 5 MB.');
    }
    await state.api.uploadPhoto(
      order.id,
      await file.readAsBytes(),
      file.name,
      taskId: item['id'] as int,
    );
    await state.refresh();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final editable = order.can('inspect') && !order.closed && !busy;
    final authorized = order.json['base_approval'] == 'approved';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item['label'] as String,
              style: TextStyle(
                fontWeight: FontWeight.w600,
                decoration: status == 'completed'
                    ? TextDecoration.lineThrough
                    : null,
              ),
            ),
            if ((item['description'] as String? ?? '').isNotEmpty)
              Text(item['description'] as String),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Chip(
                  label: Text(taskStatusLabels[status] ?? status),
                  avatar: Icon(
                    status == 'completed'
                        ? Icons.check_circle_outline
                        : status == 'attention'
                        ? Icons.warning_amber_rounded
                        : status == 'not_applicable'
                        ? Icons.not_interested
                        : Icons.pending_outlined,
                    size: 18,
                  ),
                ),
                Text(item['required'] == false ? 'Opcional' : 'Obligatoria'),
                if (item['estimated_minutes'] != null)
                  Text('${item['estimated_minutes']} min estimados'),
                if (!state.isCustomer)
                  Text(
                    (item['responsible_ids'] as List? ?? []).isEmpty
                        ? 'Sin responsable asignado'
                        : 'Responsable asignado',
                  ),
              ],
            ),
            if ((item['notes'] as String? ?? '').isNotEmpty)
              Text(item['notes'] as String),
            if (editable)
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  if (status == 'pending')
                    TextButton.icon(
                      onPressed: authorized
                          ? () => _change(context, 'in_progress')
                          : null,
                      icon: const Icon(Icons.play_arrow),
                      label: const Text('Comenzar'),
                    ),
                  if (status != 'completed' && status != 'not_applicable')
                    TextButton.icon(
                      onPressed: authorized
                          ? () => _change(context, 'completed')
                          : null,
                      icon: const Icon(Icons.check),
                      label: const Text('Completar'),
                    ),
                  PopupMenuButton<String>(
                    tooltip: 'Cambiar estado de actividad',
                    onSelected: (value) => _change(context, value),
                    itemBuilder: (_) => [
                      for (final entry in taskStatusLabels.entries)
                        if (entry.key != status &&
                            (![
                                  'completed',
                                  'in_progress',
                                ].contains(entry.key) ||
                                authorized) &&
                            (entry.key != 'not_applicable' ||
                                state.isAdmin ||
                                item['required'] == false))
                          PopupMenuItem(
                            value: entry.key,
                            child: Text(entry.value),
                          ),
                    ],
                    child: const Padding(
                      padding: EdgeInsets.all(12),
                      child: Text('Más estados'),
                    ),
                  ),
                  TextButton.icon(
                    onPressed: () => _notes(context),
                    icon: const Icon(Icons.notes, size: 18),
                    label: const Text('Observación'),
                  ),
                  IconButton(
                    tooltip: 'Adjuntar evidencia a esta actividad',
                    onPressed: () => onAction(() => _photo(context)),
                    icon: const Icon(Icons.add_a_photo_outlined),
                  ),
                ],
              ),
            if (!state.isCustomer &&
                (item['suggested_part_ids'] as List? ?? []).isNotEmpty)
              Wrap(
                children: [
                  for (final id in item['suggested_part_ids'] as List)
                    TextButton(
                      onPressed: () =>
                          openCatalogRecord(context, 'part', id as int),
                      child: Text(
                        'Repuesto sugerido #$id · verificar compatibilidad',
                      ),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class OrderAssignmentsPanel extends StatefulWidget {
  const OrderAssignmentsPanel({super.key, required this.order});
  final WorkOrder order;
  @override
  State<OrderAssignmentsPanel> createState() => _OrderAssignmentsPanelState();
}

class _OrderAssignmentsPanelState extends State<OrderAssignmentsPanel> {
  late Future<List<dynamic>> _data;
  int _revision = -1;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = context.watch<WorkshopController>();
    if (_revision != state.dataRevision) {
      _revision = state.dataRevision;
      _data = Future.wait([
        state.api.request('GET', '/staff/mechanics'),
        state.api.request('GET', '/orders/${widget.order.id}/assignments'),
      ]);
    }
  }

  Future<void> _edit(List<Json> mechanics, [Json? grant]) async {
    if (mechanics.isEmpty) {
      showMessage(context, 'No hay mecánicos activos registrados.');
      return;
    }
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AssignmentEditor(
        order: widget.order,
        mechanics: mechanics,
        grant: grant,
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ExpansionTile(
    tilePadding: EdgeInsets.zero,
    title: const Text('Responsables y asignaciones'),
    children: [
      FutureBuilder<List<dynamic>>(
        future: _data,
        builder: (context, result) {
          if (result.hasError) {
            return Text('No se pudieron cargar responsables: ${result.error}');
          }
          if (!result.hasData) return const LinearProgressIndicator();
          final mechanics = jsonList(result.data![0]),
              grants = jsonList(
                result.data![1],
              ).where((row) => row['revoked_at'] == null).toList();
          return Column(
            children: [
              if (grants.isEmpty) const Text('Aún no hay mecánicos asignados.'),
              for (final grant in grants)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(grant['mechanic_name'] as String),
                  subtitle: Text(
                    '${(grant['task_ids'] as List).length} actividades autorizadas',
                  ),
                  trailing: Wrap(
                    children: [
                      IconButton(
                        tooltip: 'Editar asignación',
                        onPressed: widget.order.closed
                            ? null
                            : () => _edit(mechanics, grant),
                        icon: const Icon(Icons.edit_outlined),
                      ),
                      IconButton(
                        tooltip: 'Revocar asignación',
                        onPressed: widget.order.closed
                            ? null
                            : () async {
                                if (await confirmAction(
                                      context,
                                      'Revocar acceso',
                                      'El mecánico perderá el acceso a estas tareas; el historial permanece.',
                                    ) &&
                                    context.mounted) {
                                  await runAction(
                                    context,
                                    () => context.read<WorkshopController>().mutate(
                                      'DELETE',
                                      '/orders/${widget.order.id}/assignments/${grant['id']}',
                                    ),
                                  );
                                }
                              },
                        icon: const Icon(Icons.person_remove_outlined),
                      ),
                    ],
                  ),
                ),
              if (!widget.order.closed)
                TextButton.icon(
                  onPressed: () => _edit(mechanics),
                  icon: const Icon(Icons.person_add_outlined),
                  label: const Text('Asignar mecánico'),
                ),
            ],
          );
        },
      ),
    ],
  );
}

class OrderPartsPanel extends StatefulWidget {
  const OrderPartsPanel({super.key, required this.order});
  final WorkOrder order;
  @override
  State<OrderPartsPanel> createState() => _OrderPartsPanelState();
}

class _OrderPartsPanelState extends State<OrderPartsPanel> {
  late Future<dynamic> _data;
  int _revision = -1;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = context.watch<WorkshopController>();
    if (_revision != state.dataRevision) {
      _revision = state.dataRevision;
      _data = state.api.request(
        'GET',
        '/orders/${widget.order.id}/part-requests',
      );
    }
  }

  Future<void> _request() async {
    final state = context.read<WorkshopController>();
    Json? part;
    var key = operationKey();
    String? previous;
    await showEditor(
      context,
      title: 'Solicitar repuesto',
      description:
          'No autoriza un costo ni descuenta inventario. Administración verifica disponibilidad y autorización del cliente.',
      fields: [
        EditorField(
          'task_id',
          'Actividad relacionada',
          options: {
            for (final item in widget.order.items)
              '${item['id']}': item['label'] as String,
          },
        ),
        const EditorField('description', 'Repuesto necesario'),
        EditorField(
          'quantity',
          'Cantidad requerida',
          initial: '1',
          keyboard: const TextInputType.numberWithOptions(decimal: true),
          validate: (value) =>
              RegExp(r'^\d{1,8}(\.\d{1,3})?$').hasMatch(value) &&
                  (double.tryParse(value) ?? 0) > 0
              ? null
              : 'Usa una cantidad positiva con hasta tres decimales',
        ),
        const EditorField(
          'unit',
          'Unidad (unidad, litro, etc.)',
          initial: 'unidad',
        ),
        const EditorField('reason', 'Motivo técnico', lines: 2),
      ],
      extra: CatalogReferenceSearch(
        api: state.api,
        endpoint: '/catalog/parts?',
        label: 'Ficha de catálogo (opcional)',
        onSelected: (row) => part = row,
        onTyped: () => part = null,
      ),
      onSubmit: (values) async {
        final body = <String, dynamic>{
          ...values,
          'task_id': int.parse(values['task_id']!),
          'part_id': part?['id'],
        };
        if (previous != null && previous != body.toString()) {
          key = operationKey();
        }
        previous = body.toString();
        await state.mutate(
          'POST',
          '/orders/${widget.order.id}/part-requests',
          body: {...body, 'request_key': key},
        );
      },
    );
  }

  Future<void> _resolve(Json row, bool approve) async {
    final state = context.read<WorkshopController>();
    Json? part;
    final approvedQuotes = widget.order.quotes
        .where((quote) => quote['decision'] == 'approved')
        .toList();
    await showEditor(
      context,
      title: approve ? 'Autorizar entrega de repuesto' : 'Rechazar solicitud',
      description: approve
          ? 'No aprueba gastos por el cliente. «Incluido en servicio base» exige que ya forme parte del alcance aceptado; un cargo nuevo necesita una cotización aprobada.'
          : 'Se conserva la solicitud y el motivo.',
      fields: [
        if (approve)
          EditorField(
            'basis',
            'Autorización existente',
            options: {
              'included_base': 'Incluido en el servicio base aceptado',
              for (final quote in approvedQuotes)
                '${quote['id']}': 'Cotización aceptada: ${quote['title']}',
            },
          ),
        const EditorField('note', 'Justificación administrativa', lines: 3),
      ],
      extra: !approve
          ? null
          : CatalogReferenceSearch(
              api: state.api,
              endpoint: '/catalog/parts?',
              label: row['part_id'] == null
                  ? 'Seleccionar repuesto real (obligatorio)'
                  : 'Cambiar ficha de repuesto (opcional)',
              onSelected: (value) => part = value,
              onTyped: () => part = null,
            ),
      onSubmit: (values) => state.mutate(
        'POST',
        '/orders/${widget.order.id}/part-requests/${row['id']}/resolution',
        body: {
          'decision': approve ? 'approve' : 'reject',
          'expected_revision': row['revision'],
          'note': values['note'],
          if (approve)
            'authorization_basis': values['basis'] == 'included_base'
                ? 'included_base'
                : 'approved_quote',
          if (approve && values['basis'] != 'included_base')
            'quote_id': int.parse(values['basis']!),
          if (approve) 'part_id': part?['id'] ?? row['part_id'],
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    return SectionCard(
      title: 'Solicitudes y repuestos utilizados',
      subtitle:
          'Catálogo ≠ inventario físico. Solo las entregas registradas descuentan stock.',
      trailing: widget.order.closed
          ? null
          : TextButton.icon(
              onPressed: _request,
              icon: const Icon(Icons.add),
              label: const Text('Solicitar'),
            ),
      child: FutureBuilder(
        future: _data,
        builder: (context, result) {
          if (result.hasError) {
            return Text(
              'No se pudieron consultar solicitudes: ${result.error}',
            );
          }
          if (!result.hasData) return const LinearProgressIndicator();
          final rows = jsonList(result.data);
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (rows.isEmpty)
                const Text(
                  'No hay solicitudes de repuestos para tus actividades.',
                ),
              for (final row in rows)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${row['description']} · ${row['quantity']} ${row['unit']}',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      Text(
                        '${{'requested': 'Por verificar y autorizar', 'approved': 'Autorizado, pendiente de entrega física', 'issued': 'Entregado desde inventario', 'rejected': 'Solicitud rechazada'}[row['status']]} · ${row['reason']}',
                      ),
                      if ((row['resolution_note'] as String? ?? '').isNotEmpty)
                        Text(row['resolution_note'] as String),
                      if (state.isAdmin && !widget.order.closed)
                        Wrap(
                          children: [
                            if (row['status'] == 'requested') ...[
                              TextButton(
                                onPressed: () => _resolve(row, true),
                                child: const Text('Verificar autorización'),
                              ),
                              TextButton(
                                onPressed: () => _resolve(row, false),
                                child: const Text('Rechazar'),
                              ),
                            ],
                            if (row['status'] == 'approved')
                              TextButton.icon(
                                icon: const Icon(Icons.inventory_2_outlined),
                                label: const Text('Registrar entrega física'),
                                onPressed: () async {
                                  if (await confirmAction(
                                        context,
                                        'Entregar repuesto',
                                        'Se descontará ${row['quantity']} ${row['unit']} del inventario real. El reintento no vuelve a descontar.',
                                      ) &&
                                      context.mounted) {
                                    await runAction(
                                      context,
                                      () => state.mutate(
                                        'POST',
                                        '/orders/${widget.order.id}/part-requests/${row['id']}/issue',
                                        body: {
                                          'expected_revision': row['revision'],
                                        },
                                      ),
                                    );
                                  }
                                },
                              ),
                          ],
                        ),
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
