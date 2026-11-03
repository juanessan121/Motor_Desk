import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/models/entities.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';
import 'registry_forms.dart';

class MaintenanceCatalogPage extends StatefulWidget {
  const MaintenanceCatalogPage({super.key});
  @override
  State<MaintenanceCatalogPage> createState() => _MaintenanceCatalogPageState();
}

class _MaintenanceCatalogPageState extends State<MaintenanceCatalogPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // Estado para Plantillas
  List<MaintenanceCatalog> _allTemplates = [];
  bool _loadingTemplates = false;
  bool _inactiveTemplates = false;
  String? _errorTemplates;
  String _queryTemplates = '';

  // Estado para Catálogo de Actividades
  List<MaintenanceActivity> _allActivities = [];
  bool _loadingActivities = false;
  bool _inactiveActivities = false;
  String? _errorActivities;
  String _queryActivities = '';
  String _systemFilter = 'todos';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    if (context.read<WorkshopController>().isAdmin) {
      _loadTemplates();
      _loadActivities();
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // --- LÓGICA DE PLANTILLAS ---
  Future<void> _loadTemplates() async {
    setState(() {
      _loadingTemplates = true;
      _errorTemplates = null;
    });
    try {
      final result = await context.read<WorkshopController>().api.request(
        'GET',
        '/catalogs?include_inactive=true',
      );
      if (mounted) {
        setState(
          () => _allTemplates =
              jsonList(result).map(MaintenanceCatalog.new).toList(),
        );
      }
    } catch (failure) {
      if (mounted) setState(() => _errorTemplates = failure.toString());
    } finally {
      if (mounted) setState(() => _loadingTemplates = false);
    }
  }

  Future<void> _editTemplate([MaintenanceCatalog? row]) async {
    await editCatalog(context, row);
    if (mounted) await _loadTemplates();
  }

  Future<void> _versions(MaintenanceCatalog row) async {
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Versiones · ${row.name}'),
        content: SizedBox(
          width: 600,
          child: FutureBuilder(
            future: this.context.read<WorkshopController>().api.request(
              'GET',
              '/catalogs/${row.id}/versions',
            ),
            builder: (context, result) {
              if (result.hasError) return Text('${result.error}');
              if (!result.hasData) {
                return const SizedBox(
                  height: 100,
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              final rows = jsonList(result.data);
              return SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (rows.isEmpty)
                      const Text(
                        'La versión anterior no se había registrado. Se conservará al editar o usar la plantilla.',
                      ),
                    for (final version in rows)
                      ExpansionTile(
                        title: Text(
                          'Versión ${version['revision']} · ${shortDate(version['created_at'])}',
                        ),
                        children: [
                          for (final task in jsonList(
                            (version['snapshot'] as Map)['tasks'],
                          ))
                            ListTile(
                              title: Text(task['label'] as String),
                              subtitle: Text(
                                task['required'] == true
                                    ? 'Obligatoria'
                                    : 'Opcional',
                              ),
                            ),
                        ],
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

  Future<void> _duplicateTemplate(MaintenanceCatalog row) => showEditor(
    context,
    title: 'Duplicar plantilla',
    description:
        'Se crea una copia editable; la original y sus órdenes no cambian.',
    fields: [
      EditorField('name', 'Nombre de la copia', initial: '${row.name} (copia)'),
    ],
    onSubmit: (values) async {
      await context.read<WorkshopController>().mutate(
        'POST',
        '/catalogs/${row.id}/duplicate',
        body: {'name': values['name']},
      );
      await _loadTemplates();
    },
  );

  // --- LÓGICA DE ACTIVIDADES REUTILIZABLES ---
  Future<void> _loadActivities() async {
    setState(() {
      _loadingActivities = true;
      _errorActivities = null;
    });
    try {
      final queryParam = _inactiveActivities ? '?include_inactive=true' : '';
      final result = await context.read<WorkshopController>().api.request(
        'GET',
        '/activities$queryParam',
      );
      if (mounted) {
        setState(
          () => _allActivities = jsonList(result)
              .map(MaintenanceActivity.new)
              .toList(),
        );
      }
    } catch (failure) {
      if (mounted) setState(() => _errorActivities = failure.toString());
    } finally {
      if (mounted) setState(() => _loadingActivities = false);
    }
  }

  Future<void> _editActivity([MaintenanceActivity? activity]) async {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => _ActivityEditorDialog(
        activity: activity,
        onSaved: () {
          _loadActivities();
        },
      ),
    );
  }

  Future<void> _seedStandardActivities() async {
    final confirm = await confirmAction(
      context,
      'Cargar actividades estándar',
      'Se inicializarán actividades reutilizables recomendadas (cambio de aceite, frenos, filtros, suspensión, etc.) sin sobreescribir las ya existentes.',
    );
    if (!confirm || !mounted) return;

    final state = context.read<WorkshopController>();
    await runAction(
      context,
      () async {
        await state.api.request('POST', '/activities/seed-standard');
        await _loadActivities();
      },
      success: 'Actividades estándar cargadas exitosamente.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    if (!state.isAdmin) {
      return const EmptyState(
        title: 'Acceso restringido',
        message: 'Las plantillas y actividades las configura administración.',
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TabBar(
          controller: _tabController,
          labelColor: Theme.of(context).colorScheme.primary,
          unselectedLabelColor: context.atelier.secondaryText,
          indicatorColor: Theme.of(context).colorScheme.primary,
          tabs: const [
            Tab(
              icon: Icon(Icons.inventory_2_outlined),
              text: 'Plantillas de mantenimiento',
            ),
            Tab(
              icon: Icon(Icons.checklist_rtl_outlined),
              text: 'Catálogo de actividades reutilizables',
            ),
          ],
        ),
        const SizedBox(height: 16),
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _buildTemplatesTab(context, state),
              _buildActivitiesTab(context, state),
            ],
          ),
        ),
      ],
    );
  }

  // VISTA TAB 1: PLANTILLAS
  Widget _buildTemplatesTab(BuildContext context, WorkshopController state) {
    final rows = _allTemplates
        .where(
          (row) =>
              (_inactiveTemplates || row.json['active'] == true) &&
              '${row.name} ${row.json['description']} ${row.json['interval_km'] ?? ''}'
                  .toLowerCase()
                  .contains(_queryTemplates),
        )
        .toList();

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PageHeading(
            title: 'Plantillas de mantenimiento',
            subtitle:
                'Tipos predeterminados reutilizables (preventivo, kilometraje, correctivo). Al crear una orden se cargan como checklist editable.',
            action: FilledButton.icon(
              onPressed: () => _editTemplate(),
              icon: const Icon(Icons.add),
              label: const Text('Nueva plantilla'),
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 320,
                child: TextField(
                  decoration: const InputDecoration(
                    labelText: 'Buscar servicio o kilometraje',
                    prefixIcon: Icon(Icons.search),
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (value) =>
                      setState(() => _queryTemplates = value.toLowerCase().trim()),
                ),
              ),
              FilterChip(
                label: const Text('Incluir archivadas'),
                selected: _inactiveTemplates,
                onSelected: (value) {
                  setState(() => _inactiveTemplates = value);
                },
              ),
              OutlinedButton.icon(
                icon: const Icon(Icons.download_rounded, size: 18),
                label: const Text('Cargar plantillas de referencia'),
                onPressed: _loadingTemplates
                    ? null
                    : () => runAction(context, () async {
                        await state.api.request('POST', '/catalogs/reference');
                        await state.refresh();
                        await _loadTemplates();
                      }),
              ),
              IconButton(
                tooltip: 'Actualizar plantillas',
                onPressed: _loadingTemplates ? null : _loadTemplates,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text(
              'Modificar una plantilla no altera las órdenes de trabajo históricas.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ),
          if (_loadingTemplates) const LinearProgressIndicator(),
          if (_errorTemplates != null)
            Text(
              _errorTemplates!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (!_loadingTemplates && rows.isEmpty)
            const EmptyState(
              title: 'Sin plantillas en esta vista',
              message:
                  'Crea una plantilla o carga las referencias iniciales.',
            ),
          for (final row in rows)
            Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          row.name,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: row.json['active'] == true
                                ? context.atelier.success.withOpacity(0.12)
                                : Colors.grey.withOpacity(0.12),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            row.json['active'] == true ? 'Activa' : 'Archivada',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: row.json['active'] == true
                                  ? context.atelier.success
                                  : Colors.grey,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${row.tasks.length} actividades sugeridas · Versión ${row.json['revision']} · Precio: ${money(row.price)}',
                      style: const TextStyle(fontSize: 13),
                    ),
                    if (row.json['interval_km'] != null)
                      Text(
                        'Intervalo: ${row.json['interval_km']} km · ${row.json['schedule_source']}',
                        style: TextStyle(
                          fontSize: 12,
                          color: context.atelier.secondaryText,
                        ),
                      ),
                    if ((row.json['description'] as String? ?? '').isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          row.json['description'] as String,
                          style: TextStyle(
                            fontSize: 12,
                            color: context.atelier.secondaryText,
                          ),
                        ),
                      ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      children: [
                        TextButton.icon(
                          onPressed: () => _editTemplate(row),
                          icon: const Icon(Icons.edit_outlined, size: 16),
                          label: const Text('Editar plantilla'),
                        ),
                        TextButton.icon(
                          onPressed: () => _duplicateTemplate(row),
                          icon: const Icon(Icons.copy, size: 16),
                          label: const Text('Duplicar'),
                        ),
                        TextButton.icon(
                          onPressed: () => _versions(row),
                          icon: const Icon(Icons.history, size: 16),
                          label: const Text('Versiones'),
                        ),
                        if (row.json['active'] == true)
                          TextButton.icon(
                            onPressed: () async {
                              if (await confirmAction(
                                    context,
                                    'Archivar plantilla',
                                    'Se oculta para nuevas órdenes; el historial permanece intacto.',
                                  ) &&
                                  mounted) {
                                await runAction(this.context, () async {
                                  await state.mutate(
                                    'DELETE',
                                    '/catalogs/${row.id}',
                                  );
                                  await _loadTemplates();
                                });
                              }
                            },
                            icon: const Icon(Icons.archive_outlined, size: 16),
                            label: const Text('Archivar'),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  // VISTA TAB 2: CATÁLOGO DE ACTIVIDADES REUTILIZABLES
  Widget _buildActivitiesTab(BuildContext context, WorkshopController state) {
    final filtered = _allActivities.where((a) {
      if (_systemFilter != 'todos' && a.system != _systemFilter) return false;
      if (!_inactiveActivities && !a.active) return false;
      if (_queryActivities.isNotEmpty) {
        final text = '${a.name} ${a.description} ${a.system} ${a.technicalNotes}'
            .toLowerCase();
        if (!text.contains(_queryActivities)) return false;
      }
      return true;
    }).toList();

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PageHeading(
            title: 'Catálogo de actividades reutilizables',
            subtitle:
                'Actividades normalizadas para el taller (cambio de aceite, frenos, suspensión). Evita duplicidades y permite construir checklists en recepciones.',
            action: Wrap(
              spacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: _seedStandardActivities,
                  icon: const Icon(Icons.auto_fix_high_rounded, size: 18),
                  label: const Text('Cargar actividades estándar'),
                ),
                FilledButton.icon(
                  onPressed: () => _editActivity(),
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Nueva actividad'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 320,
                child: TextField(
                  decoration: const InputDecoration(
                    labelText: 'Buscar actividad o nota técnica',
                    prefixIcon: Icon(Icons.search),
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (value) => setState(
                    () => _queryActivities = value.toLowerCase().trim(),
                  ),
                ),
              ),
              DropdownButton<String>(
                value: _systemFilter,
                items: const [
                  DropdownMenuItem(value: 'todos', child: Text('Todos los sistemas')),
                  DropdownMenuItem(value: 'motor', child: Text('Motor')),
                  DropdownMenuItem(value: 'frenos', child: Text('Frenos')),
                  DropdownMenuItem(value: 'suspension', child: Text('Suspensión')),
                  DropdownMenuItem(value: 'direccion', child: Text('Dirección')),
                  DropdownMenuItem(value: 'transmision', child: Text('Transmisión')),
                  DropdownMenuItem(value: 'electrico', child: Text('Eléctrico')),
                  DropdownMenuItem(value: 'climatizacion', child: Text('Climatización')),
                  DropdownMenuItem(value: 'fluidos', child: Text('Fluidos')),
                  DropdownMenuItem(value: 'general', child: Text('General')),
                ],
                onChanged: (v) => setState(() => _systemFilter = v ?? 'todos'),
              ),
              FilterChip(
                label: const Text('Incluir inactivas'),
                selected: _inactiveActivities,
                onSelected: (value) {
                  setState(() => _inactiveActivities = value);
                  _loadActivities();
                },
              ),
              IconButton(
                tooltip: 'Actualizar actividades',
                onPressed: _loadingActivities ? null : _loadActivities,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_loadingActivities) const LinearProgressIndicator(),
          if (_errorActivities != null)
            Text(
              _errorActivities!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (!_loadingActivities && filtered.isEmpty)
            const EmptyState(
              title: 'No hay actividades en este filtro',
              message:
                  'Haga clic en "Nueva actividad" o "Cargar actividades estándar" para iniciar el catálogo central.',
            ),
          for (final activity in filtered)
            Card(
              margin: const EdgeInsets.only(bottom: 10),
              child: ListTile(
                title: Row(
                  children: [
                    Expanded(
                      child: Text(
                        activity.name,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ),
                    _SystemBadge(system: activity.system),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: activity.active
                            ? context.atelier.success.withOpacity(0.12)
                            : Colors.grey.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        activity.active ? 'Activa' : 'Inactiva',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: activity.active
                              ? context.atelier.success
                              : Colors.grey,
                        ),
                      ),
                    ),
                  ],
                ),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 4),
                    if (activity.description.isNotEmpty)
                      Text(activity.description, style: const TextStyle(fontSize: 12)),
                    Row(
                      children: [
                        if (activity.estimatedMinutes != null)
                          Text(
                            'Duración estimada: ${activity.estimatedMinutes} min   ·   ',
                            style: TextStyle(
                              fontSize: 12,
                              color: context.atelier.secondaryText,
                            ),
                          ),
                        if (activity.technicalNotes.isNotEmpty)
                          Expanded(
                            child: Text(
                              'Nota técnica: ${activity.technicalNotes}',
                              style: TextStyle(
                                fontSize: 12,
                                fontStyle: FontStyle.italic,
                                color: context.atelier.secondaryText,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.edit_outlined, size: 19),
                      tooltip: 'Editar actividad',
                      onPressed: () => _editActivity(activity),
                    ),
                    IconButton(
                      icon: Icon(
                        activity.active
                            ? Icons.pause_circle_outline
                            : Icons.play_circle_outline,
                        size: 19,
                        color: activity.active
                            ? context.atelier.warning
                            : context.atelier.success,
                      ),
                      tooltip: activity.active ? 'Desactivar' : 'Activar',
                      onPressed: () async {
                        final state = context.read<WorkshopController>();
                        await runAction(context, () async {
                          if (activity.active) {
                            await state.api.request(
                              'DELETE',
                              '/activities/${activity.id}',
                            );
                          } else {
                            await state.api.request(
                              'PUT',
                              '/activities/${activity.id}',
                              body: {'active': true},
                            );
                          }
                          await _loadActivities();
                        });
                      },
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SystemBadge extends StatelessWidget {
  const _SystemBadge({required this.system});
  final String system;

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (system.toLowerCase()) {
      'motor' => ('Motor', Colors.blue.shade700),
      'frenos' => ('Frenos', Colors.deepOrange.shade700),
      'suspension' => ('Suspensión', Colors.purple.shade700),
      'direccion' => ('Dirección', Colors.teal.shade700),
      'transmision' => ('Transmisión', Colors.amber.shade900),
      'electrico' => ('Eléctrico', Colors.amber.shade700),
      'climatizacion' => ('Climatización', Colors.cyan.shade700),
      'fluidos' => ('Fluidos', Colors.indigo.shade700),
      _ => ('General', Colors.grey.shade700),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withOpacity(0.4), width: 0.8),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _ActivityEditorDialog extends StatefulWidget {
  const _ActivityEditorDialog({this.activity, required this.onSaved});
  final MaintenanceActivity? activity;
  final VoidCallback onSaved;

  @override
  State<_ActivityEditorDialog> createState() => _ActivityEditorDialogState();
}

class _ActivityEditorDialogState extends State<_ActivityEditorDialog> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameCtrl;
  late TextEditingController _descCtrl;
  late TextEditingController _notesCtrl;
  late TextEditingController _minutesCtrl;
  late String _system;
  late bool _active;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final a = widget.activity;
    _nameCtrl = TextEditingController(text: a?.name ?? '');
    _descCtrl = TextEditingController(text: a?.description ?? '');
    _notesCtrl = TextEditingController(text: a?.technicalNotes ?? '');
    _minutesCtrl = TextEditingController(
      text: a?.estimatedMinutes?.toString() ?? '',
    );
    _system = a?.system ?? 'general';
    _active = a?.active ?? true;
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _notesCtrl.dispose();
    _minutesCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final state = context.read<WorkshopController>();
      final payload = {
        'name': _nameCtrl.text.trim(),
        'system': _system,
        'description': _descCtrl.text.trim(),
        'technical_notes': _notesCtrl.text.trim(),
        'estimated_minutes': int.tryParse(_minutesCtrl.text.trim()),
        'active': _active,
      };

      if (widget.activity == null) {
        await state.api.request('POST', '/activities', body: payload);
      } else {
        await state.api.request(
          'PUT',
          '/activities/${widget.activity!.id}',
          body: payload,
        );
      }

      if (mounted) {
        showMessage(
          context,
          widget.activity == null
              ? 'Actividad agregada al catálogo central'
              : 'Actividad actualizada',
        );
        widget.onSaved();
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) showMessage(context, e.toString(), error: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 540),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        widget.activity == null
                            ? 'Nueva actividad reutilizable'
                            : 'Editar actividad reutilizable',
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => Navigator.of(context).pop(),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Esta actividad estará disponible para seleccionarse en checklists de mantenimiento o al diseñar plantillas.',
                    style: TextStyle(
                      fontSize: 12,
                      color: context.atelier.secondaryText,
                    ),
                  ),
                  const Divider(height: 24),
                  TextFormField(
                    controller: _nameCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Nombre de la actividad',
                      hintText: 'Ej: Cambio de pastillas de freno',
                      border: OutlineInputBorder(),
                    ),
                    validator: (v) => v == null || v.trim().isEmpty
                        ? 'Ingrese el nombre de la actividad'
                        : null,
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          value: _system,
                          decoration: const InputDecoration(
                            labelText: 'Sistema del vehículo',
                            border: OutlineInputBorder(),
                          ),
                          items: const [
                            DropdownMenuItem(value: 'motor', child: Text('Motor')),
                            DropdownMenuItem(value: 'frenos', child: Text('Frenos')),
                            DropdownMenuItem(
                              value: 'suspension',
                              child: Text('Suspensión'),
                            ),
                            DropdownMenuItem(
                              value: 'direccion',
                              child: Text('Dirección'),
                            ),
                            DropdownMenuItem(
                              value: 'transmision',
                              child: Text('Transmisión'),
                            ),
                            DropdownMenuItem(
                              value: 'electrico',
                              child: Text('Eléctrico'),
                            ),
                            DropdownMenuItem(
                              value: 'climatizacion',
                              child: Text('Climatización'),
                            ),
                            DropdownMenuItem(
                              value: 'fluidos',
                              child: Text('Fluidos'),
                            ),
                            DropdownMenuItem(
                              value: 'general',
                              child: Text('General'),
                            ),
                          ],
                          onChanged: (v) =>
                              setState(() => _system = v ?? 'general'),
                        ),
                      ),
                      const SizedBox(width: 14),
                      SizedBox(
                        width: 150,
                        child: TextFormField(
                          controller: _minutesCtrl,
                          decoration: const InputDecoration(
                            labelText: 'Minutos est.',
                            hintText: 'Ej: 45',
                            border: OutlineInputBorder(),
                          ),
                          keyboardType: TextInputType.number,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _descCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Descripción / procedimiento general',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _notesCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Notas técnicas predeterminadas para mecánicos',
                      hintText: 'Ej: Comprobar par de apriete a 110 Nm',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 14),
                  SwitchListTile(
                    title: const Text('Actividad habilitada'),
                    value: _active,
                    onChanged: (v) => setState(() => _active = v),
                    contentPadding: EdgeInsets.zero,
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: _saving ? null : () => Navigator.of(context).pop(),
                        child: const Text('Cancelar'),
                      ),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                        icon: _saving
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.check),
                        label: const Text('Guardar actividad'),
                        onPressed: _saving ? null : _submit,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
