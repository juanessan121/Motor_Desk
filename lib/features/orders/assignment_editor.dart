import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';

class AssignmentEditor extends StatefulWidget {
  const AssignmentEditor({
    super.key,
    required this.order,
    required this.mechanics,
    this.grant,
  });
  final WorkOrder order;
  final List<Json> mechanics;
  final Json? grant;
  @override
  State<AssignmentEditor> createState() => _AssignmentEditorState();
}

class _AssignmentEditorState extends State<AssignmentEditor> {
  late final Set<int> _tasks;
  int? _mechanic;
  bool _quote = false, _saving = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _mechanic = widget.grant?['mechanic_id'] as int?;
    _quote = widget.grant?['can_quote'] == true;
    _tasks = Set<int>.from(
      widget.grant?['task_ids'] as List? ??
          widget.order.items.map((row) => row['id']),
    );
  }

  Future<void> _save() async {
    if (_saving) return;
    if (_mechanic == null || _tasks.isEmpty) {
      setState(
        () => _error = 'Selecciona un mecánico y al menos una actividad.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await context.read<WorkshopController>().mutate(
        widget.grant == null ? 'POST' : 'PUT',
        '/orders/${widget.order.id}/assignments${widget.grant == null ? '' : '/${widget.grant!['id']}'}',
        body: {
          'mechanic_id': _mechanic,
          'task_ids': _tasks.toList()..sort(),
          'can_quote': _quote,
          if (widget.grant != null)
            'expected_revision': widget.grant!['revision'],
        },
      );
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

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      title: Text(
        widget.grant == null ? 'Asignar actividades' : 'Editar asignación',
      ),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<int>(
                initialValue: _mechanic,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Mecánico'),
                items: [
                  for (final mechanic in widget.mechanics)
                    DropdownMenuItem(
                      value: mechanic['id'] as int,
                      child: Text(mechanic['username'] as String),
                    ),
                ],
                onChanged: _saving || widget.grant != null
                    ? null
                    : (value) => setState(() => _mechanic = value),
              ),
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  'El mecánico solo verá y actualizará las actividades seleccionadas. Para reasignar a otra persona, revoca esta asignación y crea otra.',
                ),
              ),
              for (final item in widget.order.items)
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(item['label'] as String),
                  value: _tasks.contains(item['id']),
                  onChanged: _saving
                      ? null
                      : (selected) => setState(() {
                          if (selected == true) {
                            _tasks.add(item['id'] as int);
                          } else {
                            _tasks.remove(item['id']);
                          }
                        }),
                ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Puede proponer cotizaciones de sus tareas'),
                subtitle: const Text('Nunca aprueba costos por el cliente.'),
                value: _quote,
                onChanged: _saving
                    ? null
                    : (value) => setState(() => _quote = value),
              ),
              if (_error != null)
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
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
          child: Text(_saving ? 'Guardando…' : 'Guardar asignación'),
        ),
      ],
    ),
  );
}
