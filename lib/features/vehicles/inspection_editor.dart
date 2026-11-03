import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';
import '../orders/order_widgets.dart';
import 'vehicle_diagnostic_viewer.dart';
import 'vehicle_template.dart';

Future<void> openInspectionEditor(
  BuildContext context, {
  required int inspectionId,
}) async {
  await Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => InspectionEditor(inspectionId: inspectionId),
    ),
  );
}

Future<void> createInspectionDialog(BuildContext context, int vehicleId) async {
  final state = context.read<WorkshopController>();
  final orders = state.orders
      .where((row) => row.json['vehicle_id'] == vehicleId && !row.closed)
      .toList();
  if (orders.isEmpty) {
    showMessage(
      context,
      'Necesitas una orden activa autorizada para registrar la inspección.',
    );
    return;
  }
  var selectedOrder = orders.first;
  int? selectedTask = state.isMechanic
      ? (selectedOrder.items.firstOrNull?['id'] as int?)
      : null;
  final title = TextEditingController(text: 'Inspección documentada');
  int? created;
  bool saving = false;
  String? error;
  await showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) => StatefulBuilder(
      builder: (context, setState) => AlertDialog(
        title: const Text('Nueva inspección'),
        content: SizedBox(
          width: 520,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'El registro conserva autor y fecha. No se publica al cliente hasta revisión del administrador.',
                  style: TextStyle(height: 1.6),
                ),
                const SizedBox(height: 18),
                DropdownButtonFormField<int>(
                  initialValue: selectedOrder.id,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Orden autorizada',
                  ),
                  items: [
                    for (final row in orders)
                      DropdownMenuItem(
                        value: row.id,
                        child: Text(
                          '#${row.id} · ${row.title}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: saving
                      ? null
                      : (id) => setState(() {
                          selectedOrder = orders.firstWhere(
                            (row) => row.id == id,
                          );
                          selectedTask = state.isMechanic
                              ? (selectedOrder.items.firstOrNull?['id'] as int?)
                              : null;
                        }),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<int>(
                  key: ValueKey(selectedOrder.id),
                  initialValue: selectedTask ?? 0,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Tarea asociada',
                  ),
                  items: [
                    if (!state.isMechanic)
                      const DropdownMenuItem(
                        value: 0,
                        child: Text('Recepción / sin tarea específica'),
                      ),
                    for (final row in selectedOrder.items)
                      DropdownMenuItem(
                        value: row['id'] as int,
                        child: Text(
                          row['label'] as String,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: saving
                      ? null
                      : (id) => selectedTask = id == 0 ? null : id,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: title,
                  decoration: const InputDecoration(
                    labelText: 'Título de la inspección',
                  ),
                ),
                if (error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 16),
                    child: Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: saving ? null : () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          AtelierAction(
            label: 'Crear registro',
            compact: true,
            loading: saving,
            // Antes el rótulo pasaba de «Crear registro» a «Guardando…». Con
            // un formulario que ya está enviado a medias, ese cambio hace dudar
            // de si el registro se creó o no.
            error: error,
            onPressed: () async {
              if (title.text.trim().length < 2 ||
                  (state.isMechanic && selectedTask == null)) {
                setState(
                  () => error =
                      'Escribe un título y selecciona una tarea autorizada.',
                );
                return;
              }
              setState(() {
                saving = true;
                error = null;
              });
              try {
                final result =
                    await state.api.request(
                          'POST',
                          '/inspections',
                          body: {
                            'order_id': selectedOrder.id,
                            'task_id': selectedTask,
                            'title': title.text.trim(),
                          },
                        )
                        as Json;
                created = result['id'] as int;
                if (dialogContext.mounted) Navigator.pop(dialogContext);
              } catch (failure) {
                if (dialogContext.mounted) {
                  setState(() {
                    saving = false;
                    error = failure.toString();
                  });
                }
              }
            },
          ),
        ],
      ),
    ),
  );
  title.dispose();
  if (context.mounted && created != null) {
    await openInspectionEditor(context, inspectionId: created!);
  }
}

class InspectionEditor extends StatefulWidget {
  const InspectionEditor({super.key, required this.inspectionId});
  final int inspectionId;
  @override
  State<InspectionEditor> createState() => _InspectionEditorState();
}

class _InspectionEditorState extends State<InspectionEditor> {
  Json? data;
  VehicleTemplate? template;
  String viewId = 'inspection_side';
  String? error;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final result =
          await context.read<WorkshopController>().api.request(
                'GET',
                '/inspections/${widget.inspectionId}',
              )
              as Json;
      final templates = await VehicleTemplate.load();
      if (mounted) {
        setState(() {
          data = result;
          template = templates.firstWhere(
            (item) => item.id == result['template_id'],
          );
          error = null;
        });
      }
    } catch (failure) {
      if (mounted) {
        setState(() {
          error = failure.toString();
          data = null;
        });
      }
    }
  }

  Future<void> action(String path, Json body) async {
    final state = context.read<WorkshopController>();
    setState(() => busy = true);
    await runAction(context, () async {
      final result =
          await state.api.request(
                'POST',
                '/inspections/${widget.inspectionId}/$path',
                body: body,
              )
              as Json;
      if (!mounted) return;
      setState(() => data = result);
      await state.refresh();
    });
    if (mounted) setState(() => busy = false);
  }

  Future<void> finding(Offset position, [Json? existing]) async {
    final revision = data!['revision'];
    final component =
        existing?['component_id'] as String? ??
        template!.components.first['id'] as String;
    await showEditor(
      context,
      title: existing == null
          ? 'Registrar observación en la posición elegida'
          : 'Editar observación documentada',
      description:
          'La posición se guarda normalizada por vista y versión. Un hallazgo interno no cambia el informe ya publicado hasta nueva revisión.',
      fields: [
        EditorField(
          'component_id',
          'Componente',
          initial: component,
          options: {
            for (final item in template!.components)
              item['id'] as String: item['label'] as String,
          },
        ),
        EditorField(
          'category',
          'Categoría',
          initial: existing?['category'] as String? ?? 'Observación',
          options: const {
            'Observación': 'Observación',
            'Rayón': 'Rayón',
            'Golpe': 'Golpe',
            'Desgaste': 'Desgaste',
            'Otro': 'Otro',
          },
        ),
        EditorField(
          'condition',
          'Estado observado (requiere revisión)',
          initial: existing?['condition'] as String? ?? 'follow_up',
          options: conditionLabels,
        ),
        EditorField(
          'severity',
          'Severidad documentada',
          initial: existing?['severity'] as String? ?? 'not_assessed',
          options: const {
            'not_assessed': 'Sin evaluación de severidad',
            'minor': 'Leve',
            'moderate': 'Moderada',
            'major': 'Alta',
          },
        ),
        EditorField(
          'note',
          'Nota de la observación',
          initial: existing?['note'] as String? ?? '',
          lines: 4,
        ),
      ],
      onSubmit: (values) async {
        final state = context.read<WorkshopController>();
        final result =
            await state.api.request(
                  existing == null ? 'POST' : 'PUT',
                  '/inspections/${widget.inspectionId}/findings${existing == null ? '' : '/${existing['id']}'}',
                  body: {
                    ...values,
                    'expected_revision': revision,
                    'view_id': existing?['view_id'] ?? viewId,
                    'x': existing?['x'] ?? position.dx,
                    'y': existing?['y'] ?? position.dy,
                    'polygon': existing?['polygon'],
                  },
                )
                as Json;
        if (!mounted) return;
        setState(() => data = result);
        await state.refresh();
      },
    );
  }

  Future<void> upload([Json? finding]) async {
    final state = context.read<WorkshopController>();
    final current = data!;
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['jpg', 'jpeg', 'png', 'webp'],
    );
    if (file == null) return;
    final length = await file.length();
    if (length == null || length > 5 * 1024 * 1024) {
      throw const ApiException('La fotografía supera 5 MB.');
    }
    await state.api.uploadPhoto(
      current['order_id'] as int,
      await file.readAsBytes(),
      file.name,
      taskId: current['task_id'] as int?,
      inspectionId: widget.inspectionId,
      findingId: finding?['id'] as int?,
      expectedRevision: current['revision'] as int,
    );
    await load();
    await state.refresh();
  }

  Future<void> publication() async {
    final selected = jsonList(data!['photos'])
        .where((row) => row['published'] == true)
        .map((row) => row['id'] as int)
        .toSet();
    final revision = data!['revision'];
    final publish = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Publicar informe revisado'),
          content: SizedBox(
            width: 500,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Se publicará una versión congelada de las observaciones revisadas. Selecciona qué fotografías autorizar al cliente.',
                  ),
                  for (final photo in jsonList(data!['photos']))
                    CheckboxListTile(
                      title: Text('Foto #${photo['id']}'),
                      value: selected.contains(photo['id']),
                      onChanged: (value) => setState(() {
                        if (value == true) {
                          selected.add(photo['id'] as int);
                        } else {
                          selected.remove(photo['id']);
                        }
                      }),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancelar'),
            ),
            AtelierAction(
              label: 'Publicar versión',
              compact: true,
              onPressed: () => Navigator.pop(context, true),
            ),
          ],
        ),
      ),
    );
    if (publish == true && mounted) {
      await action('publish', {
        'expected_revision': revision,
        'photo_ids': selected.toList(),
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final current = data;
    final editable = current?['can_edit'] == true;
    return Scaffold(
      appBar: AppBar(
        title: Text(current?['title'] as String? ?? 'Inspección'),
        actions: [
          IconButton(
            tooltip: 'Recargar versión',
            onPressed: busy ? null : load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !state.signedIn
          ? const EmptyState(
              title: 'Sesión finalizada',
              message: 'Vuelve al inicio para autenticarte.',
            )
          : error != null
          ? EmptyState(title: 'Inspección no disponible', message: error!)
          : current == null || template == null
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(22),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1200),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Wrap(
                        spacing: 12,
                        runSpacing: 10,
                        children: [
                          AtelierBadge(
                            current['review_status'] == 'draft'
                                ? 'Borrador interno'
                                : 'Revisada',
                          ),
                          Text(
                            'Versión ${current['revision']} · ${shortDate(current['created_at'])} · ${current['author']}',
                          ),
                          if (current['published_revision'] != null)
                            Text(
                              'Última publicación: v${current['published_revision']}',
                            ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        editable
                            ? 'Selecciona una vista y toca la imagen para registrar una observación. Las marcas no se incrustan en el recurso base.'
                            : 'Informe publicado por el taller. Las observaciones corresponden a la fecha indicada, no a sensores en vivo.',
                        style: const TextStyle(height: 1.6),
                      ),
                      const SizedBox(height: 18),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final view in template!.views)
                            ChoiceChip(
                              label: Text(view.label),
                              selected: view.id == viewId,
                              onSelected: (_) =>
                                  setState(() => viewId = view.id),
                            ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      VehicleDiagnosticViewer(
                        template: template!,
                        view: template!.views.firstWhere(
                          (item) => item.id == viewId,
                        ),
                        states: {
                          for (final row in jsonList(current['findings']))
                            row['component_id'] as String: {
                              'condition':
                                  current['review_status'] == 'reviewed'
                                  ? row['condition']
                                  : 'no_data',
                            },
                        },
                        points: [
                          for (final row in jsonList(
                            current['findings'],
                          ).where((row) => row['view_id'] == viewId))
                            VehiclePoint(
                              id: 'finding:${row['id']}',
                              componentId: row['component_id'] as String,
                              x: number(row['x']),
                              y: number(row['y']),
                            ),
                        ],
                        onPosition: editable && !busy
                            ? (point) => finding(point)
                            : null,
                        onPoint: (point) {
                          final row = jsonList(current['findings']).firstWhere(
                            (row) => 'finding:${row['id']}' == point.id,
                          );
                          if (editable && !busy) {
                            finding(
                              Offset(number(row['x']), number(row['y'])),
                              row,
                            );
                          } else {
                            showDialog<void>(
                              context: context,
                              builder: (context) => AlertDialog(
                                title: Text(
                                  template!.label(
                                    row['component_id'] as String,
                                  ),
                                ),
                                content: Text(row['note'] as String),
                                actions: [
                                  TextButton(
                                    onPressed: () => Navigator.pop(context),
                                    child: const Text('Cerrar'),
                                  ),
                                ],
                              ),
                            );
                          }
                        },
                      ),
                      const SizedBox(height: 20),
                      if (busy) const LinearProgressIndicator(),
                      Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          if (editable)
                            AtelierAction(
                              label: 'Añadir evidencia interna',
                              icon: Icons.add_a_photo_outlined,
                              family: AtelierButton.secondary,
                              compact: true,
                              onPressed: busy
                                  ? null
                                  : () => runAction(context, () => upload()),
                            ),
                          if (state.isAdmin) ...[
                            AtelierAction(
                              label: 'Registrar revisión',
                              icon: Icons.verified_outlined,
                              compact: true,
                              onPressed: busy
                                  ? null
                                  : () => action('review', {
                                      'expected_revision': current['revision'],
                                    }),
                            ),
                            // Publicar al cliente solo tiene sentido con una
                            // revisión hecha: el botón se apaga y lo dice, en
                            // vez de dejar que el servidor rechace el envío.
                            AtelierAction(
                              label: 'Publicar al cliente',
                              icon: Icons.publish,
                              compact: true,
                              family: AtelierButton.contextual,
                              tooltip:
                                  current['review_status'] != 'reviewed'
                                      ? 'Primero hay que registrar la revisión'
                                      : null,
                              onPressed: busy ||
                                      current['review_status'] != 'reviewed'
                                  ? null
                                  : publication,
                            ),
                            if (current['published_revision'] != null)
                              // Retirar la publicación la deja de ver el
                              // cliente: es una acción crítica y pide
                              // confirmación.
                              AtelierAction(
                                label: 'Retirar publicación',
                                family: AtelierButton.critical,
                                compact: true,
                                confirmation:
                                    'El cliente dejará de ver esta versión. '
                                    '¿Retirarla?',
                                onPressed: busy
                                    ? null
                                    : () => action('withdraw', {
                                        'expected_revision':
                                            current['revision'],
                                      }),
                              ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 24),
                      SectionCard(
                        title: 'Observaciones guardadas · lista accesible',
                        child: jsonList(current['findings']).isEmpty
                            ? const Text(
                                'Sin observaciones. No se presume un estado normal.',
                              )
                            : Column(
                                children: [
                                  for (final row in jsonList(
                                    current['findings'],
                                  ))
                                    Padding(
                                      padding: const EdgeInsets.only(
                                        bottom: 18,
                                      ),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '${template!.label(row['component_id'] as String)} · ${row['category']}',
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w700,
                                            ),
                                          ),
                                          const SizedBox(height: 7),
                                          Text(row['note'] as String),
                                          const SizedBox(height: 7),
                                          Text(
                                            '${row['severity']} · ${row['view_id']} · ${shortDate(row['created_at'])}',
                                            style: const TextStyle(
                                              fontSize: 11,
                                            ),
                                          ),
                                          if (editable)
                                            Wrap(
                                              children: [
                                                TextButton(
                                                  onPressed: () => finding(
                                                    Offset(
                                                      number(row['x']),
                                                      number(row['y']),
                                                    ),
                                                    row,
                                                  ),
                                                  child: const Text('Editar'),
                                                ),
                                                TextButton.icon(
                                                  onPressed: () => runAction(
                                                    context,
                                                    () => upload(row),
                                                  ),
                                                  icon: const Icon(
                                                    Icons.photo_camera_outlined,
                                                    size: 17,
                                                  ),
                                                  label: const Text(
                                                    'Foto del hallazgo',
                                                  ),
                                                ),
                                                TextButton(
                                                  onPressed: () => runAction(
                                                    context,
                                                    () async {
                                                      final result =
                                                          await state.api.request(
                                                                'DELETE',
                                                                '/inspections/${widget.inspectionId}/findings/${row['id']}',
                                                                body: {
                                                                  'expected_revision':
                                                                      current['revision'],
                                                                },
                                                              )
                                                              as Json;
                                                      if (mounted) {
                                                        setState(
                                                          () => data = result,
                                                        );
                                                      }
                                                      await state.refresh();
                                                    },
                                                  ),
                                                  child: const Text(
                                                    'Archivar observación',
                                                  ),
                                                ),
                                              ],
                                            ),
                                        ],
                                      ),
                                    ),
                                ],
                              ),
                      ),
                      const SizedBox(height: 22),
                      SectionCard(
                        title: editable
                            ? 'Evidencias de la inspección (internas hasta publicación)'
                            : 'Evidencias publicadas',
                        child: jsonList(current['photos']).isEmpty
                            ? const Text('Sin fotografías disponibles.')
                            : Wrap(
                                spacing: 12,
                                runSpacing: 12,
                                children: [
                                  for (final photo in jsonList(
                                    current['photos'],
                                  ))
                                    if (current['order_id'] != null)
                                      PhotoTile(
                                        key: ValueKey(photo['id']),
                                        orderId: current['order_id'] as int,
                                        photoId: photo['id'] as int,
                                      ),
                                ],
                              ),
                      ),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
              ),
            ),
    );
  }
}
