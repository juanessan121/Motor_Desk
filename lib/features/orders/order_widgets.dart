import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/config/app_config_model.dart';
import '../../core/config/theme_controller.dart';
import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';
import '../registry/registry_forms.dart';
import 'order_execution_widgets.dart';

Future<void> openOrder(BuildContext context, int id) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      constraints: const BoxConstraints(maxWidth: 900),
      builder: (_) => OrderDetail(orderId: id),
    );

class OrderCard extends StatelessWidget {
  const OrderCard({super.key, required this.order});
  final WorkOrder order;
  @override
  Widget build(BuildContext context) => Card(
    child: InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: () => openOrder(context, order.id),
      child: Padding(
        padding: const EdgeInsets.all(23),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  '#${order.id.toString().padLeft(4, '0')}',
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const Spacer(),
                StatusChip(order.status),
              ],
            ),
            const SizedBox(height: 22),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(
                      context,
                    ).colorScheme.primary.withValues(alpha: .07),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    Icons.directions_car_outlined,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        order.plate,
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 19,
                          letterSpacing: .6,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        order.json['vehicle_name'] as String,
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 22),
            Text(
              order.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 7),
            Text(
              operationStageLabels[order.json['operational_stage']] ??
                  operationStageLabels[order.status] ??
                  order.status,
              style: const TextStyle(fontSize: 12),
            ),
            if (order.json['priority'] == 'urgent')
              const Text(
                'Prioridad urgente',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
            Text(
              order.customerName,
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 22),
            Row(
              children: [
                const Text(
                  'Progreso del trabajo',
                  style: TextStyle(fontSize: 11),
                ),
                const Spacer(),
                Text(
                  '${(order.progress * 100).round()}%',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: order.progress,
                minHeight: 6,
                backgroundColor: Theme.of(
                  context,
                ).colorScheme.primary.withValues(alpha: .08),
              ),
            ),
            const SizedBox(height: 22),
            const Divider(),
            const SizedBox(height: 17),
            Row(
              children: [
                Expanded(
                  child: Text(
                    shortDate(order.json['created_at']),
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 11,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                if (order.showsFinancials) ...[
                  Text(
                    money(order.total),
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 18,
                    ),
                  ),
                  const SizedBox(width: 10),
                ],
                const Icon(Icons.arrow_forward_rounded, size: 17),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

class OrderSummaryTile extends StatelessWidget {
  const OrderSummaryTile({super.key, required this.order, required this.onTap});
  final WorkOrder order;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => InkWell(
    onTap: onTap,
    borderRadius: BorderRadius.circular(12),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(13),
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.directions_car_outlined, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  order.plate,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  order.title,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(5),
                  child: LinearProgressIndicator(
                    value: order.progress,
                    minHeight: 4,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 18),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              StatusChip(order.status),
              const SizedBox(height: 8),
              Text(
                '${(order.progress * 100).round()}%',
                style: const TextStyle(fontSize: 11),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

class OrderDetail extends StatefulWidget {
  const OrderDetail({super.key, required this.orderId});
  final int orderId;
  @override
  State<OrderDetail> createState() => _OrderDetailState();
}

class _OrderDetailState extends State<OrderDetail> {
  bool busy = false;

  @override
  void initState() {
    super.initState();
    // `OrderDetail` lee la orden del estado local: el listado ya la trajo.
    // Las acciones persisten en el servidor; no hace falta volver a consultarla.
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final flags = context.watch<ThemeController>().config;
    if (!state.signedIn ||
        (state.isCustomer && !flags.enabled('maintenance'))) {
      return const SizedBox(
        height: 220,
        child: EmptyState(
          title: 'Orden no disponible',
          message: 'Actualiza tus datos o verifica los permisos de tu cuenta.',
        ),
      );
    }
    final order = state.orders.firstWhere(
      (row) => row.id == widget.orderId,
      orElse: () => WorkOrder({}),
    );
    if (order.id == 0) {
      return const SizedBox(
        height: 220,
        child: EmptyState(
          title: 'Orden no disponible',
          message: 'No hay acceso a esta orden.',
        ),
      );
    }
    return content(order, state, flags);
  }

  Future<void> act(Future<void> Function() action) async {
    if (busy) return;
    final state = context.read<WorkshopController>();
    setState(() => busy = true);
    await runAction(context, () async {
      try {
        await action();
      } on ApiException catch (failure) {
        if (failure.statusCode == 409) {
          await state.refresh();
        }
        rethrow;
      }
    });
    if (mounted) setState(() => busy = false);
  }

  Future<void> addQuote(WorkOrder order) => showEditor(
    context,
    title: 'Cotizar repuesto adicional',
    description:
        'Una variante por línea con el formato: nombre | precio. El cliente debe autorizar el gasto; una aprobación agrega la tarea de instalación.',
    fields: [
      if (context.read<WorkshopController>().isMechanic)
        EditorField(
          'task_id',
          'Actividad relacionada',
          options: {
            for (final item in order.items)
              '${item['id']}': item['label'] as String,
          },
        ),
      const EditorField('title', 'Repuesto / trabajo detectado'),
      EditorField(
        'options',
        'Variantes · nombre | precio',
        lines: 5,
        validate: (value) {
          final lines = value
              .split('\n')
              .where((line) => line.trim().isNotEmpty)
              .toList();
          if (lines.isEmpty || lines.length > 10) {
            return 'Ingresa de 1 a 10 variantes';
          }
          for (final line in lines) {
            final parts = line.split('|');
            if (parts.length != 2 ||
                parts[0].trim().isEmpty ||
                validateMoney(parts[1].trim()) != null) {
              return 'Formato requerido: Nacional | 45.00';
            }
          }
          return null;
        },
      ),
    ],
    onSubmit: (values) => context.read<WorkshopController>().mutate(
      'POST',
      '/orders/${order.id}/quotes',
      body: {
        'title': values['title'],
        if (values['task_id'] != null) 'task_id': int.parse(values['task_id']!),
        'options': [
          for (final line
              in values['options']!
                  .split('\n')
                  .where((line) => line.trim().isNotEmpty))
            {
              'label': line.split('|')[0].trim(),
              'price': line.split('|')[1].trim(),
            },
        ],
      },
    ),
    submitLabel: 'Enviar a aprobación',
  );

  Future<void> upload(WorkOrder order) async {
    final state = context.read<WorkshopController>();
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['jpg', 'jpeg', 'png', 'webp'],
    );
    if (file == null) return;
    final length = await file.length();
    if (length == null || length > 5 * 1024 * 1024) {
      throw const ApiException('Selecciona una imagen de hasta 5 MB.');
    }
    await state.api.uploadPhoto(order.id, await file.readAsBytes(), file.name);
    await state.refresh();
  }

  Widget content(
    WorkOrder order,
    WorkshopController state,
    AppConfigModel flags,
  ) {
    return SizedBox(
      height: MediaQuery.sizeOf(context).height * .86,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 4, 16, 18),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${order.plate} · Orden #${order.id}',
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 21,
                        ),
                      ),
                      const SizedBox(height: 7),
                      Text(order.title, style: const TextStyle(fontSize: 13)),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: 'Cerrar',
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
          ),
          if (busy)
            const LinearProgressIndicator(minHeight: 2)
          else
            const Divider(),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 16,
                    runSpacing: 12,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      StatusChip(order.status),
                      Text(
                        operationStageLabels[order.json['operational_stage']] ??
                            '',
                      ),
                      if (order.json['intake_mileage'] != null)
                        Text('${order.json['intake_mileage']} km al ingreso'),
                      if (order.showsFinancials) ...[
                        Text(
                          'Pagador: ${order.customerName}',
                          style: const TextStyle(fontSize: 13),
                        ),
                        Text(
                          '${order.status == 'delivered' ? 'Total final' : 'Total estimado'}: ${money(order.total)}',
                          style: const TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ] else
                        const Text(
                          'Trabajo asignado · sin importes ni datos de facturación',
                          style: TextStyle(fontSize: 13),
                        ),
                    ],
                  ),
                  if ((order.json['symptoms'] as String? ?? '').isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 16),
                      child: Text(
                        'Servicio / síntomas: ${order.json['symptoms']}',
                      ),
                    ),
                  if (state.isAdmin) OrderAssignmentsPanel(order: order),
                  if ((order.json['templates'] as List? ?? []).isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text(
                        'Plantillas: ${jsonList(order.json['templates']).map((row) => '${row['name']} · v${row['revision']}').join(' / ')}',
                      ),
                    ),
                  if (!state.isCustomer &&
                      order.json['base_approval'] != 'approved' &&
                      !order.closed)
                    const Padding(
                      padding: EdgeInsets.only(top: 12),
                      child: Text(
                        'Pendiente de aceptación del cliente. Puedes documentar observaciones, pero no iniciar ni completar trabajo no autorizado.',
                      ),
                    ),
                  const SizedBox(height: 12),
                  if (state.isAdmin &&
                      order.json['can_record_approval'] == true &&
                      !order.closed)
                    OutlinedButton.icon(
                      icon: const Icon(Icons.fact_check_outlined),
                      label: const Text('Registrar autorización presencial'),
                      onPressed: busy
                          ? null
                          : () => showEditor(
                              context,
                              title: 'Autorización del cliente sin portal',
                              description:
                                  'Registra únicamente una autorización recibida. Se guardarán tu usuario, la fecha y el total estimado.',
                              fields: const [
                                EditorField(
                                  'note',
                                  'Quién autorizó, cuándo y constancia de la autorización',
                                  lines: 3,
                                ),
                              ],
                              onSubmit: (values) => state.mutate(
                                'POST',
                                '/orders/${order.id}/recorded-approval',
                                body: {
                                  'approved': true,
                                  'expected_revision': order.json['revision'],
                                  'note': values['note'],
                                },
                              ),
                            ),
                    ),
                  _OrderObservationsCard(
                    order: order,
                    isAdmin: state.isAdmin,
                    busy: busy,
                    onTogglePublication: () => act(
                      () => state.mutate(
                        'POST',
                        '/orders/${order.id}/notes/publication',
                        body: {
                          'published': order.json['notes_published'] != true,
                          'expected_published':
                              order.json['notes_published'] == true,
                        },
                      ),
                    ),
                  ),
                  if (state.isCustomer &&
                      order.json['base_approval'] == 'pending' &&
                      !order.closed) ...[
                    const SizedBox(height: 18),
                    const Text('Servicio base pendiente de tu aceptación'),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        AtelierAction(
                          label: 'Aceptar servicio',
                          loading: busy,
                          onPressed: () => act(
                            () => state.mutate(
                              'POST',
                              '/orders/${order.id}/approval',
                              body: {'approved': true},
                            ),
                          ),
                        ),
                        AtelierAction(
                          label: 'Rechazar servicio',
                          family: AtelierButton.secondary,
                          loading: busy,
                          onPressed: () => act(
                            () => state.mutate(
                              'POST',
                              '/orders/${order.id}/approval',
                              body: {'approved': false},
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                  const SizedBox(height: 26),
                  Text(
                    'Checklist · ${(order.progress * 100).round()}%',
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: order.progress,
                      minHeight: 7,
                    ),
                  ),
                  const SizedBox(height: 14),
                  const Text(
                    '«No aplica» se conserva sin contar en el avance; «Requiere atención» bloquea la finalización.',
                  ),
                  for (final item in order.items)
                    ActivityTile(
                      key: ValueKey(item['id']),
                      order: order,
                      item: item,
                      busy: busy,
                      onAction: act,
                    ),
                  if (state.isAdmin && !order.closed)
                    TextButton.icon(
                      icon: const Icon(Icons.add_task),
                      label: const Text('Agregar actividad extraordinaria'),
                      onPressed: busy
                          ? null
                          : () => showEditor(
                              context,
                              title: 'Agregar actividad sin cargo adicional',
                              description:
                                  'Los nuevos costos requieren cotización y aceptación del cliente. La plantilla original no cambia.',
                              fields: const [
                                EditorField('label', 'Actividad'),
                                EditorField(
                                  'reason',
                                  'Motivo de la modificación',
                                  lines: 2,
                                ),
                              ],
                              onSubmit: (values) => state.mutate(
                                'POST',
                                '/orders/${order.id}/items',
                                body: {
                                  'label': values['label'],
                                  'reason': values['reason'],
                                },
                              ),
                            ),
                    ),
                  if (!state.isCustomer) ...[
                    const SizedBox(height: 20),
                    OrderPartsPanel(order: order),
                  ],
                  if (!state.isCustomer || flags.enabled('quotes')) ...[
                    const SizedBox(height: 24),
                    Row(
                      children: [
                        const Expanded(
                          child: Text(
                            'Repuestos adicionales',
                            style: TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        if (order.can('quote') && !order.closed)
                          TextButton.icon(
                            onPressed: busy ? null : () => addQuote(order),
                            icon: const Icon(Icons.add, size: 18),
                            label: const Text('Cotizar'),
                          ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    if (order.quotes.isEmpty)
                      Text(
                        'No hay gastos adicionales.',
                        style: TextStyle(
                          fontSize: 13,
                          color: context.atelier.secondaryText,
                        ),
                      ),
                    for (final quote in order.quotes)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: QuoteCard(order: order, quote: quote),
                      ),
                  ],
                  if (!state.isCustomer || flags.enabled('photos')) ...[
                    const SizedBox(height: 28),
                    Row(
                      children: [
                        const Expanded(
                          child: Text(
                            'Evidencia de recepción',
                            style: TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        if (order.can('upload') &&
                            !order.closed &&
                            state.isAdmin)
                          IconButton(
                            tooltip: 'Subir fotografía',
                            onPressed: busy
                                ? null
                                : () => act(() => upload(order)),
                            icon: const Icon(Icons.add_a_photo_outlined),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (order.photos.isEmpty)
                      Text(
                        'No se han adjuntado fotografías.',
                        style: TextStyle(
                          fontSize: 13,
                          color: context.atelier.secondaryText,
                        ),
                      ),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        for (final photo in order.photos)
                          PhotoTile(
                            key: ValueKey(photo['id']),
                            orderId: order.id,
                            photoId: photo['id'] as int,
                          ),
                      ],
                    ),
                  ],
                  if (order.can('manage') && !order.closed) ...[
                    const SizedBox(height: 30),
                    const Divider(),
                    const SizedBox(height: 20),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        if (state.isAdmin &&
                            order.json['operational_stage'] == 'pending_review')
                          AtelierAction(
                            label: 'Revisar y dejar lista para entrega',
                            icon: Icons.fact_check_outlined,
                            onPressed: busy
                                ? null
                                : () => showEditor(
                                    context,
                                    title: 'Revisión final de ejecución',
                                    description:
                                        'Confirma la revisión de las actividades y solicitudes. No registra todavía la entrega del vehículo.',
                                    fields: const [
                                      EditorField(
                                        'note',
                                        'Resultado de revisión',
                                        initial:
                                            'Ejecución revisada por administración',
                                      ),
                                    ],
                                    onSubmit: (values) => state.mutate(
                                      'POST',
                                      '/orders/${order.id}/execution-review',
                                      body: {
                                        'expected_revision':
                                            order.json['revision'],
                                        'note': values['note'],
                                      },
                                    ),
                                  ),
                          ),
                        if (order.status == 'ready')
                          AtelierAction(
                            label: 'Registrar entrega',
                            icon: Icons.key_rounded,
                            onPressed: busy
                                ? null
                                : () => act(
                                    () => state.mutate(
                                      'PATCH',
                                      '/orders/${order.id}/status?status=delivered',
                                    ),
                                  ),
                          ),
                        AtelierAction(
                          label: 'Cancelar orden',
                          // Cancelar deshace el trabajo: es la acción más
                          // peligrosa de la orden y por eso es crítica, no
                          // secundaria.
                          family: AtelierButton.critical,
                          confirmation:
                              'Se conservarán las fotografías, decisiones y '
                              'tareas como evidencia.',
                          onPressed: busy
                              ? null
                              : () async {
                                  if (await confirmAction(
                                    context,
                                    '¿Cancelar la orden?',
                                    'Se conservarán las fotografías, decisiones y tareas como evidencia.',
                                  )) {
                                    await act(
                                      () => state.mutate(
                                        'PATCH',
                                        '/orders/${order.id}/status?status=cancelled',
                                      ),
                                    );
                                  }
                                },
                        ),
                      ],
                    ),
                  ],
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class QuoteCard extends StatefulWidget {
  const QuoteCard({super.key, required this.order, required this.quote});
  final WorkOrder order;
  final Json quote;
  @override
  State<QuoteCard> createState() => _QuoteCardState();
}

class _QuoteCardState extends State<QuoteCard> {
  int? selected;
  bool busy = false;
  Future<void> decide(bool approve) async {
    final state = context.read<WorkshopController>();
    setState(() => busy = true);
    await runAction(
      context,
      () => state.mutate(
        'POST',
        '/orders/${widget.order.id}/quotes/${widget.quote['id']}/decision',
        body: {
          'decision': approve ? 'approved' : 'rejected',
          'option_id': approve ? selected : null,
        },
      ),
    );
    if (mounted) setState(() => busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final isCustomer = context.watch<WorkshopController>().isCustomer;
    final quote = widget.quote;
    final pending = quote['decision'] == 'pending' && !widget.order.closed;
    return Card(
      color: Theme.of(context).scaffoldBackgroundColor,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    quote['title'] as String,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                const SizedBox(width: 10),
                StatusChip(quote['decision'] as String),
              ],
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final option in jsonList(quote['options']))
                  ChoiceChip(
                    label: Text(
                      '${option['label']} · ${money(option['price'])}',
                    ),
                    selected:
                        (quote['selected_option_id'] ?? selected) ==
                        option['id'],
                    onSelected: isCustomer && pending && !busy
                        ? (_) => setState(() => selected = option['id'] as int)
                        : null,
                  ),
              ],
            ),
            if (isCustomer && pending) ...[
              const SizedBox(height: 18),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  AtelierAction(
                    label: 'Autorizar gasto',
                    loading: busy,
                    onPressed: selected == null || busy
                        ? null
                        : () => decide(true),
                  ),
                  AtelierAction(
                    label: 'Rechazar',
                    family: AtelierButton.secondary,
                    loading: busy,
                    onPressed: busy ? null : () => decide(false),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class PhotoTile extends StatefulWidget {
  const PhotoTile({
    super.key,
    this.orderId,
    this.inspectionId,
    required this.photoId,
    this.expanded = false,
  }) : assert(orderId != null || inspectionId != null);
  final int? orderId;
  final int? inspectionId;
  final int photoId;
  final bool expanded;
  @override
  State<PhotoTile> createState() => _PhotoTileState();
}

class _PhotoTileState extends State<PhotoTile> {
  Future<Uint8List>? image;
  String? _access;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = context.watch<WorkshopController>();
    final flags = context.watch<ThemeController>().config;
    final key = '${state.sessionEpoch}:${state.dataRevision}:${flags.features}';
    if (_access != key) {
      _access = key;
      image = allowed(state, flags)
          ? state.api.download(
              widget.inspectionId == null
                  ? '/orders/${widget.orderId}/photos/${widget.photoId}'
                  : '/inspections/${widget.inspectionId}/photos/${widget.photoId}',
            )
          : null;
    }
  }

  bool allowed(WorkshopController state, AppConfigModel flags) =>
      state.signedIn &&
      (!state.isCustomer ||
          (flags.enabled('photos') &&
              (widget.inspectionId == null || flags.enabled('history'))));

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final flags = context.watch<ThemeController>().config;
    if (!allowed(state, flags)) {
      return const Text(
        'Fotografía no disponible para esta cuenta o dispositivo.',
      );
    }
    return FutureBuilder<Uint8List>(
      key: ValueKey(_access),
      future: image,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return const SizedBox(
            width: 130,
            height: 100,
            child: Center(
              child: Tooltip(
                message: 'No se pudo cargar la foto',
                child: Icon(Icons.broken_image_outlined),
              ),
            ),
          );
        }
        if (snapshot.connectionState != ConnectionState.done ||
            !snapshot.hasData) {
          return const SizedBox(
            width: 130,
            height: 100,
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          );
        }
        if (widget.expanded) {
          return InteractiveViewer(
            child: Image.memory(snapshot.data!, fit: BoxFit.contain),
          );
        }
        return InkWell(
          onTap: () => showDialog<void>(
            context: context,
            builder: (context) => Dialog(
              child: Stack(
                children: [
                  PhotoTile(
                    orderId: widget.orderId,
                    inspectionId: widget.inspectionId,
                    photoId: widget.photoId,
                    expanded: true,
                  ),
                  Positioned(
                    right: 8,
                    top: 8,
                    child: IconButton.filledTonal(
                      tooltip: 'Cerrar imagen',
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ),
                ],
              ),
            ),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.memory(
              snapshot.data!,
              width: 130,
              height: 100,
              fit: BoxFit.cover,
              cacheWidth: 520,
            ),
          ),
        );
      },
    );
  }
}

class _OrderObservationsCard extends StatelessWidget {
  const _OrderObservationsCard({
    required this.order,
    required this.isAdmin,
    required this.busy,
    required this.onTogglePublication,
  });

  final WorkOrder order;
  final bool isAdmin;
  final bool busy;
  final VoidCallback onTogglePublication;

  @override
  Widget build(BuildContext context) {
    final symptom = order.symptoms ?? order.problemDescription ?? '';
    final diag = order.technicalDiagnosis ?? '';
    final delay = order.delayReason ?? '';
    final notes = order.notes ?? '';

    final hasAny =
        symptom.isNotEmpty ||
        diag.isNotEmpty ||
        delay.isNotEmpty ||
        notes.isNotEmpty;

    if (!hasAny) return const SizedBox.shrink();

    final isPublished = order.json['notes_published'] == true;

    return Card(
      margin: const EdgeInsets.only(top: 8, bottom: 8),
      color: Theme.of(
        context,
      ).colorScheme.surfaceContainerHighest.withOpacity(0.35),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.assignment_outlined,
                  size: 18,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                const Text(
                  'Observaciones contextualizadas de la orden',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                ),
              ],
            ),
            const Divider(height: 20),

            // 1. Síntomas / Motivo de ingreso reportado
            if (symptom.isNotEmpty) ...[
              _ObservationRow(
                badgeLabel: 'Motivo de ingreso / Síntomas',
                badgeColor: Colors.blue.shade700,
                icon: Icons.hearing_outlined,
                content: symptom,
              ),
              const SizedBox(height: 10),
            ],

            // 2. Diagnóstico técnico inicial
            if (diag.isNotEmpty) ...[
              _ObservationRow(
                badgeLabel: 'Diagnóstico técnico inicial',
                badgeColor: Colors.purple.shade700,
                icon: Icons.biotech_outlined,
                content: diag,
              ),
              const SizedBox(height: 10),
            ],

            // 3. Motivo de espera o retraso
            if (delay.isNotEmpty) ...[
              _ObservationRow(
                badgeLabel: 'Motivo de espera / demora',
                badgeColor: Colors.deepOrange.shade700,
                icon: Icons.pause_circle_outline,
                content: delay,
              ),
              const SizedBox(height: 10),
            ],

            // 4. Observaciones generales del taller
            if (notes.isNotEmpty) ...[
              _ObservationRow(
                badgeLabel: isPublished
                    ? 'Notas generales (Publicadas al cliente)'
                    : 'Notas internas del taller (Privadas)',
                badgeColor: isPublished
                    ? Colors.teal.shade700
                    : Colors.blueGrey.shade700,
                icon: isPublished
                    ? Icons.visibility_outlined
                    : Icons.lock_outline,
                content: notes,
              ),
              if (isAdmin) ...[
                const SizedBox(height: 6),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    icon: Icon(
                      isPublished
                          ? Icons.visibility_off_outlined
                          : Icons.publish,
                      size: 16,
                    ),
                    label: Text(
                      isPublished
                          ? 'Ocultar al cliente'
                          : 'Publicar al cliente',
                      style: const TextStyle(fontSize: 12),
                    ),
                    onPressed: busy ? null : onTogglePublication,
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _ObservationRow extends StatelessWidget {
  const _ObservationRow({
    required this.badgeLabel,
    required this.badgeColor,
    required this.icon,
    required this.content,
  });

  final String badgeLabel;
  final Color badgeColor;
  final IconData icon;
  final String content;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: badgeColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: badgeColor, width: 0.8),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon, size: 12, color: badgeColor),
                  const SizedBox(width: 4),
                  Text(
                    badgeLabel,
                    style: TextStyle(
                      color: badgeColor,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Padding(
          padding: const EdgeInsets.only(left: 4),
          child: Text(
            content,
            style: const TextStyle(fontSize: 13, height: 1.4),
          ),
        ),
      ],
    );
  }
}
