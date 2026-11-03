import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../vehicles/catalog_record_page.dart';

Future<void> editMaintenanceTemplate(
  BuildContext context, [
  MaintenanceCatalog? catalog,
]) => showDialog<void>(
  context: context,
  barrierDismissible: false,
  builder: (_) => MaintenanceTemplateEditor(catalog: catalog),
);

class MaintenanceTemplateEditor extends StatefulWidget {
  const MaintenanceTemplateEditor({super.key, this.catalog});
  final MaintenanceCatalog? catalog;
  @override
  State<MaintenanceTemplateEditor> createState() =>
      _MaintenanceTemplateEditorState();
}

class _TemplateTask {
  _TemplateTask(Json json)
    : label = TextEditingController(text: json['label'] as String? ?? ''),
      description = TextEditingController(
        text: json['description'] as String? ?? '',
      ),
      minutes = TextEditingController(
        text: json['estimated_minutes']?.toString() ?? '',
      ),
      required = json['required'] != false,
      parts = List<int>.from(json['suggested_part_ids'] as List? ?? []);
  final TextEditingController label, description, minutes;
  bool required;
  final List<int> parts;
  void dispose() {
    label.dispose();
    description.dispose();
    minutes.dispose();
  }
}

class _MaintenanceTemplateEditorState extends State<MaintenanceTemplateEditor> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _name,
      _price,
      _description,
      _interval,
      _source,
      _yearFrom,
      _yearTo;
  late final List<_TemplateTask> _tasks;
  late Json _conditions;
  bool _active = true, _saving = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    final data = widget.catalog?.json ?? {};
    _name = TextEditingController(text: data['name'] as String? ?? '');
    _price = TextEditingController(
      text: data['price_configured'] == false
          ? ''
          : data['base_price']?.toString() ?? '',
    );
    _description = TextEditingController(
      text: data['description'] as String? ?? '',
    );
    _interval = TextEditingController(
      text: data['interval_km']?.toString() ?? '',
    );
    _source = TextEditingController(
      text: data['schedule_source'] as String? ?? '',
    );
    _conditions = Map<String, dynamic>.from(
      data['applicability'] as Map? ?? {},
    );
    _yearFrom = TextEditingController(
      text: _conditions['year_from']?.toString() ?? '',
    );
    _yearTo = TextEditingController(
      text: _conditions['year_to']?.toString() ?? '',
    );
    _active = data['active'] != false;
    final tasks = jsonList(data['task_details']);
    _tasks =
        (tasks.isNotEmpty
                ? tasks
                : widget.catalog?.tasks
                          .map((label) => <String, dynamic>{'label': label})
                          .toList() ??
                      [{}])
            .map(_TemplateTask.new)
            .toList();
  }

  @override
  void dispose() {
    for (final controller in [
      _name,
      _price,
      _description,
      _interval,
      _source,
      _yearFrom,
      _yearTo,
    ]) {
      controller.dispose();
    }
    for (final task in _tasks) {
      task.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    if (_tasks.isEmpty) {
      setState(() => _error = 'Agrega al menos una actividad.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final state = context.read<WorkshopController>();
    try {
      await state.api.request(
        widget.catalog == null ? 'POST' : 'PUT',
        '/catalogs${widget.catalog == null ? '' : '/${widget.catalog!.id}'}',
        body: {
          'name': _name.text.trim(),
          'description': _description.text.trim(),
          'base_price': _price.text.trim().isEmpty
              ? '0.00'
              : _price.text.trim(),
          'price_configured': _price.text.trim().isNotEmpty,
          'interval_km': int.tryParse(_interval.text),
          'schedule_source': _source.text.trim(),
          'active': _active,
          'applicability': {
            ..._conditions,
            'year_from': int.tryParse(_yearFrom.text),
            'year_to': int.tryParse(_yearTo.text),
          },
          if (widget.catalog != null)
            'expected_revision': widget.catalog!.json['revision'],
          'tasks': [
            for (final task in _tasks)
              {
                'label': task.label.text.trim(),
                'description': task.description.text.trim(),
                'required': task.required,
                'estimated_minutes': int.tryParse(task.minutes.text),
                'suggested_part_ids': task.parts,
              },
          ],
        },
      );
      await state.refresh();
      if (mounted) Navigator.pop(context);
    } catch (failure) {
      if (mounted) {
        setState(() {
          _error = failure.toString();
          _saving = false;
        });
      }
    }
  }

  String? _integer(String? value, int min, int max) {
    if (value == null || value.trim().isEmpty) return null;
    final number = int.tryParse(value);
    return number == null || number < min || number > max
        ? 'Usa un entero de $min a $max'
        : null;
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<WorkshopController>().api;
    return PopScope(
      canPop: !_saving,
      child: AlertDialog(
        title: Text(
          widget.catalog == null
              ? 'Nueva plantilla de mantenimiento'
              : 'Editar plantilla · versión ${widget.catalog!.json['revision'] ?? 1}',
        ),
        content: SizedBox(
          width: 760,
          child: SingleChildScrollView(
            child: Form(
              key: _form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Las órdenes guardan su propia versión. No se modifican servicios anteriores. Precio vacío significa pendiente de configurar, no servicio gratuito.',
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _name,
                    enabled: !_saving,
                    maxLength: 150,
                    decoration: const InputDecoration(
                      labelText: 'Nombre del mantenimiento',
                    ),
                    validator: (value) => (value?.trim().length ?? 0) < 2
                        ? 'Escribe un nombre'
                        : null,
                  ),
                  TextFormField(
                    controller: _price,
                    enabled: !_saving,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: const InputDecoration(
                      labelText: 'Precio referencial (USD, opcional)',
                    ),
                    validator: (value) =>
                        value == null ||
                            value.isEmpty ||
                            RegExp(r'^\d{1,8}(\.\d{1,2})?$').hasMatch(value)
                        ? null
                        : 'Usa USD con hasta dos decimales',
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _description,
                    enabled: !_saving,
                    maxLength: 3000,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Descripción e indicaciones',
                    ),
                  ),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      SizedBox(
                        width: 220,
                        child: TextFormField(
                          controller: _interval,
                          enabled: !_saving,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'Intervalo (km, opcional)',
                          ),
                          validator: (value) => _integer(value, 1, 1000000),
                        ),
                      ),
                      SizedBox(
                        width: 180,
                        child: TextFormField(
                          controller: _yearFrom,
                          enabled: !_saving,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'Desde año (opcional)',
                          ),
                          validator: (value) => _integer(value, 1900, 2200),
                        ),
                      ),
                      SizedBox(
                        width: 180,
                        child: TextFormField(
                          controller: _yearTo,
                          enabled: !_saving,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'Hasta año (opcional)',
                          ),
                          validator: (value) => _integer(value, 1900, 2200),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _source,
                    enabled: !_saving,
                    maxLength: 500,
                    decoration: const InputDecoration(
                      labelText: 'Fuente del intervalo / manual del fabricante',
                    ),
                  ),
                  ExpansionTile(
                    title: const Text('Condiciones por marca, modelo y motor'),
                    children: [
                      const Text(
                        'Una referencia desconocida no confirma compatibilidad. Sin condiciones, la plantilla es genérica.',
                      ),
                      for (final level in [
                        'make',
                        'model',
                        'generation',
                        'engine',
                      ])
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: CatalogReferenceSearch(
                            key: ValueKey('$level:$_conditions'),
                            api: api,
                            label: {
                              'make': 'Marca',
                              'model': 'Modelo',
                              'generation': 'Generación',
                              'engine': 'Motor',
                            }[level]!,
                            endpoint:
                                '/catalog/browse?entity=$level${level == 'model' && _conditions['make_id'] != null ? '&make_id=${_conditions['make_id']}' : ''}${level == 'generation' && _conditions['model_id'] != null ? '&model_id=${_conditions['model_id']}' : ''}${level == 'engine' && _conditions['generation_id'] != null ? '&generation_id=${_conditions['generation_id']}' : ''}',
                            onSelected: (record) => setState(() {
                              _conditions['${level}_id'] = record['id'];
                              final levels = [
                                'make',
                                'model',
                                'generation',
                                'engine',
                              ];
                              for (final child in levels.skip(
                                levels.indexOf(level) + 1,
                              )) {
                                _conditions.remove('${child}_id');
                              }
                            }),
                          ),
                        ),
                      Text(
                        'Referencias actuales: ${_conditions.entries.where((entry) => entry.key.endsWith('_id')).map((entry) => '${entry.key}: ${entry.value}').join(' · ')}',
                      ),
                      TextButton(
                        onPressed: _saving
                            ? null
                            : () => setState(() => _conditions = {}),
                        child: const Text('Quitar condiciones de catálogo'),
                      ),
                    ],
                  ),
                  SwitchListTile(
                    title: const Text('Plantilla activa'),
                    value: _active,
                    onChanged: _saving
                        ? null
                        : (value) => setState(() => _active = value),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Actividades (${_tasks.length})',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  for (var i = 0; i < _tasks.length; i++)
                    _taskCard(_tasks[i], i),
                  TextButton.icon(
                    onPressed: _saving || _tasks.length >= 100
                        ? null
                        : () => setState(() => _tasks.add(_TemplateTask({}))),
                    icon: const Icon(Icons.add),
                    label: const Text('Agregar actividad'),
                  ),
                  if (_error != null)
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: _saving ? null : () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? 'Guardando…' : 'Guardar plantilla'),
          ),
        ],
      ),
    );
  }

  Widget _taskCard(_TemplateTask task, int index) => Card(
    key: ObjectKey(task),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextFormField(
            controller: task.label,
            enabled: !_saving,
            maxLength: 250,
            decoration: InputDecoration(labelText: 'Actividad ${index + 1}'),
            validator: (value) => value == null || value.trim().isEmpty
                ? 'Escribe la actividad'
                : null,
          ),
          ExpansionTile(
            title: const Text('Obligatoriedad, duración y repuestos sugeridos'),
            children: [
              TextFormField(
                controller: task.description,
                enabled: !_saving,
                maxLength: 2000,
                decoration: const InputDecoration(
                  labelText: 'Instrucciones de la actividad',
                ),
              ),
              TextFormField(
                controller: task.minutes,
                enabled: !_saving,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Duración estimada (min, opcional)',
                ),
                validator: (value) => _integer(value, 1, 10000),
              ),
              SwitchListTile(
                title: const Text('Actividad obligatoria'),
                value: task.required,
                onChanged: _saving
                    ? null
                    : (value) => setState(() => task.required = value),
              ),
              CatalogReferenceSearch(
                api: context.read<WorkshopController>().api,
                label: 'Buscar repuesto sugerido',
                endpoint: '/catalog/parts?',
                onSelected: (record) => setState(() {
                  final id = record['id'] as int;
                  if (!task.parts.contains(id) && task.parts.length < 20) {
                    task.parts.add(id);
                  }
                }),
              ),
              Wrap(
                children: [
                  for (final id in task.parts)
                    InputChip(
                      label: Text('Repuesto #$id'),
                      onPressed: () => openCatalogRecord(context, 'part', id),
                      onDeleted: _saving
                          ? null
                          : () => setState(() => task.parts.remove(id)),
                    ),
                ],
              ),
              const Text(
                'Sugerencia de plantilla; debe verificarse para el vehículo. No reserva ni descuenta stock.',
              ),
            ],
          ),
          Wrap(
            alignment: WrapAlignment.end,
            children: [
              IconButton(
                tooltip: 'Subir actividad',
                onPressed: _saving || index == 0
                    ? null
                    : () => setState(() {
                        _tasks.removeAt(index);
                        _tasks.insert(index - 1, task);
                      }),
                icon: const Icon(Icons.arrow_upward),
              ),
              IconButton(
                tooltip: 'Bajar actividad',
                onPressed: _saving || index == _tasks.length - 1
                    ? null
                    : () => setState(() {
                        _tasks.removeAt(index);
                        _tasks.insert(index + 1, task);
                      }),
                icon: const Icon(Icons.arrow_downward),
              ),
              IconButton(
                tooltip: 'Quitar actividad de la plantilla',
                onPressed: _saving || _tasks.length == 1
                    ? null
                    : () {
                        setState(() => _tasks.remove(task));
                        WidgetsBinding.instance.addPostFrameCallback(
                          (_) => task.dispose(),
                        );
                      },
                icon: const Icon(Icons.delete_outline),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
