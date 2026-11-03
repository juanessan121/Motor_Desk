import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/models/entities.dart';
import '../../core/models/operation_key.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';
import '../registry/registry_forms.dart';

class ReceptionDialog extends StatefulWidget {
  const ReceptionDialog({super.key, this.vehicleId});
  final int? vehicleId;
  @override
  State<ReceptionDialog> createState() => _ReceptionDialogState();
}

class _ReceptionDialogState extends State<ReceptionDialog> {
  final _form = GlobalKey<FormState>();
  final _search = TextEditingController();
  final _mileage = TextEditingController();
  final _symptoms = TextEditingController();
  final _technicalDiagnosis = TextEditingController();
  final _notes = TextEditingController();
  final _extra = TextEditingController();
  final _manualTaskCtrl = TextEditingController();

  final Set<int> _selected = {};
  final Map<String, bool> _checklistActivities = {};
  final Set<String> _customManualActivities = {};

  List<Json> _suggestions = [];
  List<Json> _mechanics = [];
  int? _vehicleId, _mechanic, _payer;
  String _priority = 'normal';
  String _maintenanceType = 'preventivo';
  String _manualTaskSystem = 'general';
  bool _saveManualToCatalog = false;

  String _key = operationKey();
  Json? _lastPayload;
  String? _error, _suggestionError;
  bool _saving = false, _suggesting = false;
  int _request = 0;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _vehicleId = widget.vehicleId;
    final state = context.read<WorkshopController>();
    final vehicle = state.vehicles
        .where((row) => row.id == _vehicleId)
        .firstOrNull;
    if (vehicle != null) {
      _mileage.text = '${vehicle.json['mileage']}';
      _suggest();
    }
    _loadMechanics();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    for (final controller in [
      _search,
      _mileage,
      _symptoms,
      _technicalDiagnosis,
      _notes,
      _extra,
      _manualTaskCtrl,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _loadMechanics() async {
    try {
      final result = await context.read<WorkshopController>().api.request(
        'GET',
        '/staff/mechanics',
      );
      if (mounted) setState(() => _mechanics = jsonList(result));
    } catch (failure) {
      if (mounted) {
        setState(
          () => _error =
              'No se pudo cargar responsables: $failure. Puedes asignarlos después.',
        );
      }
    }
  }

  Future<void> _suggest() async {
    final request = ++_request;
    if (_vehicleId == null) return;
    setState(() {
      _suggesting = true;
      _suggestionError = null;
    });
    try {
      final params = Uri(queryParameters: {'mileage': _mileage.text}).query;
      final result =
          await context.read<WorkshopController>().api.request(
                'GET',
                '/vehicles/$_vehicleId/maintenance-suggestions?$params',
              )
              as Json;
      if (mounted && request == _request) {
        setState(() => _suggestions = jsonList(result['items']));
      }
    } catch (failure) {
      if (mounted && request == _request) {
        setState(() => _suggestionError = failure.toString());
      }
    } finally {
      if (mounted && request == _request) setState(() => _suggesting = false);
    }
  }

  void _choose(Vehicle vehicle) {
    setState(() {
      _vehicleId = vehicle.id;
      _mileage.text = '${vehicle.json['mileage']}';
      _selected.clear();
      _checklistActivities.clear();
      _payer = null;
      _suggestions = [];
    });
    _suggest();
  }

  Future<void> _newVehicle({bool newCustomer = false}) async {
    final state = context.read<WorkshopController>();
    int? owner;
    if (newCustomer || state.customers.isEmpty) {
      owner = await editCustomer(context, null, true);
      if (!mounted || owner == null) return;
    }
    final vehicleId = await editVehicle(context, null, owner, true);
    if (!mounted || vehicleId == null) return;
    final vehicle = state.vehicles
        .where((row) => row.id == vehicleId)
        .firstOrNull;
    if (vehicle != null) _choose(vehicle);
  }

  void _syncChecklistActivities(List<Json> catalogs) {
    final activeTemplates = catalogs
        .where((row) => _selected.contains(row['id']))
        .toList();

    final Set<String> templateTaskLabels = {};
    for (final template in activeTemplates) {
      final tasks = template['tasks'] as List? ?? [];
      for (final t in tasks) {
        final label = t is Map ? t['label'] as String : t.toString();
        templateTaskLabels.add(label);
        if (!_checklistActivities.containsKey(label)) {
          // Por defecto pre-marcada como incluida al elegir la plantilla
          _checklistActivities[label] = true;
        }
      }
    }

    // Limpiar actividades de plantillas que ya no están seleccionadas
    _checklistActivities.removeWhere((label, _) {
      return !_customManualActivities.contains(label) &&
          !templateTaskLabels.contains(label);
    });
  }

  void _addManualActivity() async {
    final name = _manualTaskCtrl.text.trim();
    if (name.isEmpty) return;

    setState(() {
      _checklistActivities[name] = true;
      _customManualActivities.add(name);
      _manualTaskCtrl.clear();
    });

    if (_saveManualToCatalog) {
      try {
        final state = context.read<WorkshopController>();
        await state.api.request(
          'POST',
          '/activities',
          body: {
            'name': name,
            'system': _manualTaskSystem,
            'technical_notes': 'Agregada desde recepción de orden de trabajo',
            'active': true,
          },
        );
        if (mounted) {
          showMessage(
            context,
            'Actividad "$name" guardada en el catálogo central reutilizable.',
          );
        }
      } catch (e) {
        if (mounted) showMessage(context, e.toString(), error: true);
      }
    }
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    if (_vehicleId == null || _selected.isEmpty) {
      setState(
        () => _error =
            'Selecciona un vehículo y al menos una plantilla de servicio.',
      );
      return;
    }

    final included = _checklistActivities.entries
        .where((e) => e.value)
        .map((e) => e.key)
        .toList();

    if (included.isEmpty) {
      setState(
        () => _error =
            'Debes marcar al menos una actividad en el checklist para incluir en la orden.',
      );
      return;
    }

    final state = context.read<WorkshopController>();
    final extras = _extra.text
        .split('\n')
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toList();

    final body = <String, dynamic>{
      'vehicle_id': _vehicleId,
      'catalog_ids': _selected.toList()..sort(),
      'included_tasks': included,
      'maintenance_type': _maintenanceType,
      'mileage': int.parse(_mileage.text),
      'symptoms': _symptoms.text.trim(),
      'problem_description': _symptoms.text.trim(),
      'technical_diagnosis': _technicalDiagnosis.text.trim(),
      'notes': _notes.text.trim(),
      'customer_id': _payer,
      'mechanic_id': _mechanic,
      'priority': _priority,
      'extra_tasks': [
        for (final label in extras)
          {
            'label': label,
            'reason':
                'Actividad adicional indicada en recepción; sin cargo adicional.',
          },
      ],
    };

    if (_lastPayload != null && _lastPayload.toString() != body.toString()) {
      _key = operationKey();
    }
    _lastPayload = body;

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final saved =
          await state.api.request(
                'POST',
                '/orders',
                body: {...body, 'request_key': _key},
              )
              as Json;
      await state.refresh();
      if (mounted) Navigator.pop(context, saved['id'] as int);
    } catch (failure) {
      if (mounted) {
        setState(() {
          _error = failure.toString();
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final vehicle = state.vehicles
        .where((row) => row.id == _vehicleId)
        .firstOrNull;
    final query = _search.text.trim().toLowerCase();
    final vehicles = state.vehicles
        .where(
          (row) =>
              row.active &&
              '${row.plate} ${row.name} ${row.ownerName}'
                  .toLowerCase()
                  .contains(query),
        )
        .take(8)
        .toList();

    final catalogs = _suggestions.isNotEmpty
        ? _suggestions
        : state.catalogs.map((row) => row.json).toList();

    _syncChecklistActivities(catalogs);

    return PopScope(
      canPop: !_saving,
      child: AlertDialog(
        title: Text(
          widget.vehicleId == null
              ? 'Recepción · vehículo → servicios → confirmar'
              : 'Paso 3 de 3 · Servicios y orden',
        ),
        content: SizedBox(
          width: 820,
          child: SingleChildScrollView(
            child: Form(
              key: _form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min,
                children: [
                  // PASO 1: Selección de Vehículo
                  const Text(
                    '1. Vehículo y cliente',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _search,
                    enabled: !_saving,
                    decoration: const InputDecoration(
                      labelText: 'Buscar placa, vehículo o propietario',
                      prefixIcon: Icon(Icons.search),
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                  if (vehicle == null || query.isNotEmpty) ...[
                    for (final row in vehicles)
                      ListTile(
                        dense: true,
                        title: Text('${row.plate} · ${row.name}'),
                        subtitle: Text(row.ownerName),
                        trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                        onTap: _saving
                            ? null
                            : () {
                                _search.clear();
                                _choose(row);
                              },
                      ),
                    if (vehicles.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(10),
                        child: Text(
                          'No hay coincidencias. Puedes registrar un nuevo vehículo directamente.',
                          style: TextStyle(fontSize: 12),
                        ),
                      ),
                  ],
                  Wrap(
                    children: [
                      TextButton.icon(
                        onPressed: _saving ? null : () => _newVehicle(),
                        icon: const Icon(Icons.add, size: 16),
                        label: const Text('Nuevo vehículo'),
                      ),
                      TextButton.icon(
                        onPressed: _saving
                            ? null
                            : () => _newVehicle(newCustomer: true),
                        icon: const Icon(Icons.person_add_outlined, size: 16),
                        label: const Text('Nuevo cliente y vehículo'),
                      ),
                    ],
                  ),
                  if (vehicle != null) ...[
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.directions_car, size: 32),
                        title: Text(
                          '${vehicle.plate} · ${vehicle.name}',
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        subtitle: Text(
                          'Propietario: ${vehicle.ownerName}\n'
                          'Año: ${vehicle.json['year']} · Último registro: ${vehicle.json['mileage']} km\n'
                          'Color: ${vehicle.json['color'] ?? 'No especificado'} · '
                          'Combustible: ${(vehicle.json['fuel_type'] ?? 'gasolina').toString().toUpperCase()}',
                        ),
                        isThreeLine: true,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _mileage,
                      enabled: !_saving,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Kilometraje de recepción',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      validator: (value) {
                        final km = int.tryParse(value ?? '');
                        return km == null ||
                                km < number(vehicle.json['mileage']) ||
                                km > 10000000
                            ? 'Usa un kilometraje válido (no menor al anterior)'
                            : null;
                      },
                      onChanged: (_) {
                        _debounce?.cancel();
                        _debounce = Timer(
                          const Duration(milliseconds: 400),
                          _suggest,
                        );
                      },
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: _maintenanceType,
                      decoration: const InputDecoration(
                        labelText: 'Tipo de mantenimiento',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'preventivo',
                          child: Text('Preventivo básico'),
                        ),
                        DropdownMenuItem(
                          value: 'preventivo_completo',
                          child: Text('Preventivo completo'),
                        ),
                        DropdownMenuItem(
                          value: 'kilometraje',
                          child: Text('Por kilometraje'),
                        ),
                        DropdownMenuItem(
                          value: 'correctivo',
                          child: Text('Correctivo'),
                        ),
                        DropdownMenuItem(
                          value: 'diagnostico',
                          child: Text('Diagnóstico general'),
                        ),
                        DropdownMenuItem(
                          value: 'personalizado',
                          child: Text('Personalizado'),
                        ),
                      ],
                      onChanged: (v) =>
                          setState(() => _maintenanceType = v ?? 'preventivo'),
                    ),
                    const Divider(height: 28),

                    // PASO 2: Plantillas de Servicio
                    const Text(
                      '2. Plantillas de servicio sugeridas',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Seleccione una o más plantillas para precargar su lista de actividades sugeridas:',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    if (_suggesting) const LinearProgressIndicator(),
                    if (_suggestionError != null)
                      Text(
                        'No se pudieron verificar sugerencias: $_suggestionError',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    for (final catalog in catalogs)
                      CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(catalog['name'] as String),
                        value: _selected.contains(catalog['id']),
                        subtitle: Text(
                          '${catalog['price_configured'] == false ? 'Precio por configurar' : money(catalog['base_price'])} · ${(catalog['tasks'] as List).length} actividades sugeridas'
                          '${catalog['interval_km'] == null ? '' : ' · cada ${catalog['interval_km']} km'}',
                        ),
                        onChanged:
                            _saving || catalog['price_configured'] == false
                            ? null
                            : (selected) {
                                setState(() {
                                  if (selected == true) {
                                    _selected.add(catalog['id'] as int);
                                  } else {
                                    _selected.remove(catalog['id']);
                                  }
                                });
                              },
                      ),
                    const Divider(height: 28),

                    // PASO 3: SISTEMA HÍBRIDO CHECKLIST (Requerimiento 6)
                    Card(
                      color: Theme.of(
                        context,
                      ).colorScheme.surfaceContainerHighest.withOpacity(0.35),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            LayoutBuilder(
                              builder: (context, constraints) {
                                final isNarrow = constraints.maxWidth < 900;
                                final badge = Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 3,
                                  ),
                                  decoration: BoxDecoration(
                                    color: context.atelier.success.withOpacity(
                                      0.12,
                                    ),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    '${_checklistActivities.values.where((v) => v).length} seleccionadas de ${_checklistActivities.length}',
                                    style: TextStyle(
                                      color: context.atelier.success,
                                      fontWeight: FontWeight.w700,
                                      fontSize: 11,
                                    ),
                                  ),
                                );

                                if (isNarrow) {
                                  return Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Icon(
                                            Icons.checklist_rtl_rounded,
                                            color: Theme.of(
                                              context,
                                            ).colorScheme.primary,
                                          ),
                                          const SizedBox(width: 8),
                                          const Expanded(
                                            child: Text(
                                              '3. Checklist de actividades para la orden',
                                              style: TextStyle(
                                                fontWeight: FontWeight.w700,
                                                fontSize: 14,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 6),
                                      badge,
                                    ],
                                  );
                                }

                                return Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(
                                          Icons.checklist_rtl_rounded,
                                          color: Theme.of(
                                            context,
                                          ).colorScheme.primary,
                                        ),
                                        const SizedBox(width: 8),
                                        const Text(
                                          '3. Checklist de actividades para la orden',
                                          style: TextStyle(
                                            fontWeight: FontWeight.w700,
                                            fontSize: 14,
                                          ),
                                        ),
                                      ],
                                    ),
                                    badge,
                                  ],
                                );
                              },
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Marque o desmarque las casillas para definir qué actividades se incluirán en la orden de trabajo. (Las casillas representan inclusión en la orden, no ejecución completada).',
                              style: TextStyle(
                                fontSize: 12,
                                color: context.atelier.secondaryText,
                              ),
                            ),
                            const SizedBox(height: 12),
                            if (_checklistActivities.isEmpty)
                              const Padding(
                                padding: EdgeInsets.symmetric(vertical: 8),
                                child: Text(
                                  'Seleccione una plantilla de servicio arriba o agregue actividades manualmente a continuación.',
                                  style: TextStyle(
                                    fontStyle: FontStyle.italic,
                                    fontSize: 12,
                                  ),
                                ),
                              )
                            else
                              for (final entry in _checklistActivities.entries)
                                CheckboxListTile(
                                  dense: true,
                                  contentPadding: EdgeInsets.zero,
                                  title: Text(
                                    entry.key,
                                    style: TextStyle(
                                      fontWeight: entry.value
                                          ? FontWeight.w600
                                          : FontWeight.normal,
                                      decoration: entry.value
                                          ? null
                                          : TextDecoration.lineThrough,
                                    ),
                                  ),
                                  value: entry.value,
                                  onChanged: _saving
                                      ? null
                                      : (checked) {
                                          setState(() {
                                            _checklistActivities[entry.key] =
                                                checked ?? false;
                                          });
                                        },
                                ),
                            const Divider(height: 20),

                            // Agregar actividad manual / catálogo reutilizable
                            const Text(
                              'Añadir actividad manual a la orden:',
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 12,
                              ),
                            ),
                            const SizedBox(height: 8),
                            LayoutBuilder(
                              builder: (context, constraints) {
                                final isNarrow = constraints.maxWidth < 450;
                                if (isNarrow) {
                                  return Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.stretch,
                                    children: [
                                      TextField(
                                        controller: _manualTaskCtrl,
                                        decoration: const InputDecoration(
                                          hintText:
                                              'Ej: Revisión de ruido en suspensión',
                                          border: OutlineInputBorder(),
                                          isDense: true,
                                        ),
                                      ),
                                      const SizedBox(height: 8),
                                      Row(
                                        children: [
                                          Expanded(
                                            child:
                                                DropdownButtonFormField<String>(
                                                  isExpanded: true,
                                                  initialValue:
                                                      _manualTaskSystem,
                                                  decoration:
                                                      const InputDecoration(
                                                        border:
                                                            OutlineInputBorder(),
                                                        isDense: true,
                                                      ),
                                                  items: const [
                                                    DropdownMenuItem(
                                                      value: 'general',
                                                      child: Text('General'),
                                                    ),
                                                    DropdownMenuItem(
                                                      value: 'motor',
                                                      child: Text('Motor'),
                                                    ),
                                                    DropdownMenuItem(
                                                      value: 'frenos',
                                                      child: Text('Frenos'),
                                                    ),
                                                    DropdownMenuItem(
                                                      value: 'suspension',
                                                      child: Text('Suspensión'),
                                                    ),
                                                    DropdownMenuItem(
                                                      value: 'direccion',
                                                      child: Text('Dirección'),
                                                    ),
                                                    DropdownMenuItem(
                                                      value: 'electrico',
                                                      child: Text('Eléctrico'),
                                                    ),
                                                    DropdownMenuItem(
                                                      value: 'fluidos',
                                                      child: Text('Fluidos'),
                                                    ),
                                                  ],
                                                  onChanged: (v) => setState(
                                                    () => _manualTaskSystem =
                                                        v ?? 'general',
                                                  ),
                                                ),
                                          ),
                                          const SizedBox(width: 8),
                                          FilledButton.tonalIcon(
                                            icon: const Icon(
                                              Icons.add,
                                              size: 16,
                                            ),
                                            label: const Text('Agregar'),
                                            onPressed: _addManualActivity,
                                          ),
                                        ],
                                      ),
                                    ],
                                  );
                                }
                                return Row(
                                  children: [
                                    Expanded(
                                      child: TextField(
                                        controller: _manualTaskCtrl,
                                        decoration: const InputDecoration(
                                          hintText:
                                              'Ej: Revisión de ruido en suspensión',
                                          border: OutlineInputBorder(),
                                          isDense: true,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    SizedBox(
                                      width: 135,
                                      child: DropdownButtonFormField<String>(
                                        isExpanded: true,
                                        initialValue: _manualTaskSystem,
                                        decoration: const InputDecoration(
                                          border: OutlineInputBorder(),
                                          isDense: true,
                                        ),
                                        items: const [
                                          DropdownMenuItem(
                                            value: 'general',
                                            child: Text('General'),
                                          ),
                                          DropdownMenuItem(
                                            value: 'motor',
                                            child: Text('Motor'),
                                          ),
                                          DropdownMenuItem(
                                            value: 'frenos',
                                            child: Text('Frenos'),
                                          ),
                                          DropdownMenuItem(
                                            value: 'suspension',
                                            child: Text('Suspensión'),
                                          ),
                                          DropdownMenuItem(
                                            value: 'direccion',
                                            child: Text('Dirección'),
                                          ),
                                          DropdownMenuItem(
                                            value: 'electrico',
                                            child: Text('Eléctrico'),
                                          ),
                                          DropdownMenuItem(
                                            value: 'fluidos',
                                            child: Text('Fluidos'),
                                          ),
                                        ],
                                        onChanged: (v) => setState(
                                          () => _manualTaskSystem =
                                              v ?? 'general',
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    FilledButton.tonalIcon(
                                      icon: const Icon(Icons.add, size: 16),
                                      label: const Text('Agregar'),
                                      onPressed: _addManualActivity,
                                    ),
                                  ],
                                );
                              },
                            ),
                            Row(
                              children: [
                                Checkbox(
                                  value: _saveManualToCatalog,
                                  onChanged: (v) => setState(
                                    () => _saveManualToCatalog = v ?? false,
                                  ),
                                ),
                                const Expanded(
                                  child: Text(
                                    'Guardar también en el catálogo central de actividades reutilizables',
                                    style: TextStyle(fontSize: 11),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                    const Divider(height: 28),

                    // PASO 4: OBSERVACIONES CONTEXTUALIZADAS (Requerimiento 4)
                    const Text(
                      '4. Contexto, diagnóstico y observaciones',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Cada observación está clasificada según su propósito técnico u operativo:',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _symptoms,
                      enabled: !_saving,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Síntomas / motivo reportado por el cliente',
                        hintText:
                            'Ej: Chirrido metálico al frenar y vibración en el volante a alta velocidad',
                        prefixIcon: Icon(Icons.hearing_outlined),
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _technicalDiagnosis,
                      enabled: !_saving,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Diagnóstico técnico preliminar / recepción',
                        hintText:
                            'Ej: Desgaste en pastillas delanteras al 15% restante, disco derecho con surco',
                        prefixIcon: Icon(Icons.analytics_outlined),
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _notes,
                      enabled: !_saving,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Observaciones internas del taller',
                        hintText:
                            'Ej: Cliente solicita entrega urgente antes de las 17:00. Trae líquidos propios.',
                        prefixIcon: Icon(Icons.notes_outlined),
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    ExpansionTile(
                      title: const Text(
                        'Asignación de mecánico y prioridad',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      children: [
                        LayoutBuilder(
                          builder: (context, constraints) {
                            final isNarrow = constraints.maxWidth < 450;
                            final mechanicField = DropdownButtonFormField<int>(
                              isExpanded: true,
                              decoration: const InputDecoration(
                                labelText: 'Mecánico responsable asignado',
                                border: OutlineInputBorder(),
                                isDense: true,
                              ),
                              items: [
                                for (final mechanic in _mechanics)
                                  DropdownMenuItem(
                                    value: mechanic['id'] as int,
                                    child: Text(mechanic['username'] as String),
                                  ),
                              ],
                              onChanged: _saving
                                  ? null
                                  : (value) =>
                                        setState(() => _mechanic = value),
                            );

                            final priorityField =
                                DropdownButtonFormField<String>(
                                  isExpanded: true,
                                  initialValue: _priority,
                                  decoration: const InputDecoration(
                                    labelText: 'Prioridad',
                                    border: OutlineInputBorder(),
                                    isDense: true,
                                  ),
                                  items: const [
                                    DropdownMenuItem(
                                      value: 'normal',
                                      child: Text('Normal'),
                                    ),
                                    DropdownMenuItem(
                                      value: 'urgent',
                                      child: Text('Urgente'),
                                    ),
                                  ],
                                  onChanged: _saving
                                      ? null
                                      : (value) =>
                                            setState(() => _priority = value!),
                                );

                            if (isNarrow) {
                              return Column(
                                children: [
                                  mechanicField,
                                  const SizedBox(height: 12),
                                  priorityField,
                                ],
                              );
                            }
                            return Row(
                              children: [
                                Expanded(child: mechanicField),
                                const SizedBox(width: 12),
                                Expanded(child: priorityField),
                              ],
                            );
                          },
                        ),
                        const SizedBox(height: 10),
                      ],
                    ),
                  ],
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                          fontWeight: FontWeight.w600,
                        ),
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
            label: Text(_saving ? 'Confirmando…' : 'Confirmar orden'),
            onPressed: _saving ? null : _save,
          ),
        ],
      ),
    );
  }
}
