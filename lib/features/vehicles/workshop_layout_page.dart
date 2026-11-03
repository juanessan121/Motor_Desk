import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart' show jsonList;
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';

/// Configuración persistente; nunca crea bahías al abrir la pantalla.
class WorkshopLayoutPage extends StatefulWidget {
  const WorkshopLayoutPage({super.key});
  @override
  State<WorkshopLayoutPage> createState() => _WorkshopLayoutPageState();
}

class _WorkshopLayoutPageState extends State<WorkshopLayoutPage> {
  Json? _layout;
  String? _error;
  bool _loading = false;
  bool _saving = false;

  ApiClient get api => context.read<WorkshopController>().api;

  @override
  void initState() {
    super.initState();
    if (context.read<WorkshopController>().isAdmin) _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data =
          await api.request('GET', '/workshop/layout?include_inactive=true')
              as Json;
      if (mounted) setState(() => _layout = data);
    } catch (failure) {
      if (mounted) setState(() => _error = failure.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String? _number(String value, {bool positive = false}) {
    final number = double.tryParse(value.replaceAll(',', '.'));
    if (number == null ||
        !number.isFinite ||
        number < 0 ||
        number > 1 ||
        (positive && number == 0)) {
      return positive
          ? 'Usa un número mayor que 0 y hasta 1'
          : 'Usa un número de 0 a 1';
    }
    return null;
  }

  Future<void> _edit({Json? row, bool bay = false}) async {
    final zones = jsonList(
      _layout?['zones'],
    ).where((zone) => zone['active'] == true).toList();
    if (bay && zones.isEmpty) {
      showMessage(context, 'Crea primero una zona activa.');
      return;
    }
    if (bay &&
        row != null &&
        !zones.any((zone) => zone['id'] == row['zone_id'])) {
      showMessage(context, 'La zona de esta bahía no está activa.');
      return;
    }
    String value(String key, String fallback) =>
        row?[key]?.toString() ?? fallback;
    await showEditor(
      context,
      title: '${row == null ? 'Crear' : 'Editar'} ${bay ? 'bahía' : 'zona'}',
      description:
          'Las coordenadas van de 0 a 1 respecto del plano. X/Y indican la esquina superior izquierda. La API valida límites y capacidad.',
      fields: [
        EditorField('name', 'Nombre', initial: value('name', '')),
        if (bay)
          EditorField(
            'zone_id',
            'Zona',
            initial: value('zone_id', ''),
            options: {
              for (final zone in zones) '${zone['id']}': zone['name'] as String,
            },
          ),
        EditorField(
          'kind',
          'Tipo',
          initial: value('kind', bay ? 'mechanical' : 'service'),
          options: {
            'service': 'Servicio',
            'mechanical': 'Mecánica',
            'electrical': 'Electricidad',
            'diagnostic': 'Diagnóstico',
            'delivery': 'Entrega',
            if (row != null &&
                ![
                  'service',
                  'mechanical',
                  'electrical',
                  'diagnostic',
                  'delivery',
                ].contains(row['kind']))
              '${row['kind']}': '${row['kind']}',
          },
        ),
        EditorField(
          'capacity',
          'Capacidad',
          initial: value('capacity', bay ? '1' : '6'),
          keyboard: TextInputType.number,
          validate: (text) {
            final n = int.tryParse(text);
            return n == null || n < 1 || n > 100
                ? 'Usa un entero de 1 a 100'
                : null;
          },
        ),
        for (final field in {
          'x': 'Posición X',
          'y': 'Posición Y',
          'width': 'Ancho',
          'height': 'Alto',
        }.entries)
          EditorField(
            field.key,
            '${field.value} (0–1)',
            initial: value(
              field.key,
              ['x', 'y'].contains(field.key)
                  ? '0.05'
                  : bay
                  ? '0.2'
                  : '0.9',
            ),
            keyboard: const TextInputType.numberWithOptions(decimal: true),
            validate: (text) => _number(
              text,
              positive: ['width', 'height'].contains(field.key),
            ),
          ),
      ],
      onSubmit: (values) async {
        await api.request(
          row == null ? 'POST' : 'PUT',
          '/workshop/${bay ? 'bays' : 'zones'}${row == null ? '' : '/${row['id']}'}',
          body: {
            'name': values['name'],
            'kind': values['kind'],
            'capacity': int.parse(values['capacity']!),
            for (final field in ['x', 'y', 'width', 'height'])
              field: double.parse(values[field]!.replaceAll(',', '.')),
            if (bay) 'zone_id': int.parse(values['zone_id']!),
            if (bay) 'active': row?['active'] ?? true,
            if (row != null) 'expected_revision': row['revision'],
          },
        );
        await _load();
      },
    );
  }

  Future<void> _template() async {
    if (_saving || _layout == null) return;
    if (!await confirmAction(
      context,
      'Crear seis bahías',
      'Se guardará una zona con seis puestos, siguiendo la plantilla del kit. Confirma que deseas usar esta distribución; luego podrás editarla. No se crearán vehículos ni ocupaciones.',
    )) {
      return;
    }
    if (!mounted) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await api.request(
        'POST',
        '/workshop/layout/template',
        body: {
          'expected_revision': _layout!['revision'],
          'template': 'six-bays',
        },
      );
      await _load();
    } catch (failure) {
      if (mounted) setState(() => _error = failure.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _availability(Json bay) async {
    final active = bay['active'] == true;
    if (!await confirmAction(
      context,
      active ? 'Desactivar bahía' : 'Reactivar bahía',
      active
          ? 'Quedará fuera de servicio. Una bahía ocupada no se puede desactivar y el historial se conserva.'
          : 'El puesto volverá a aceptar movimientos autorizados.',
    )) {
      return;
    }
    if (!mounted) return;
    await runAction(context, () async {
      await api.request(
        'PUT',
        '/workshop/bays/${bay['id']}',
        body: {
          for (final field in [
            'name',
            'kind',
            'capacity',
            'x',
            'y',
            'width',
            'height',
            'zone_id',
          ])
            field: bay[field],
          'expected_revision': bay['revision'],
          'active': !active,
        },
      );
      await _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final admin = context.watch<WorkshopController>().isAdmin;
    final zones = jsonList(_layout?['zones']);
    final bays = jsonList(_layout?['bays']);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Configurar plano del taller'),
        actions: [
          IconButton(
            tooltip: 'Actualizar plano',
            onPressed: _loading || !admin ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !admin
          ? const EmptyState(
              title: 'Acceso restringido',
              message: 'Solo un administrador puede configurar el taller.',
            )
          : _loading && _layout == null
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_loading || _saving) const LinearProgressIndicator(),
                  if (_error != null) ...[
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                    TextButton(
                      onPressed: _load,
                      child: const Text('Reintentar'),
                    ),
                  ],
                  if (_layout != null && zones.isEmpty && bays.isEmpty) ...[
                    const SectionCard(
                      title: 'Elige una distribución',
                      subtitle:
                          'Plantilla de referencia, todavía sin guardar. No representa vehículos ni ocupaciones reales.',
                      child: WorkshopTemplatePreview(),
                    ),
                    const SizedBox(height: 12),
                    FilledButton.icon(
                      onPressed: _saving ? null : _template,
                      icon: const Icon(Icons.grid_view),
                      label: const Text('Usar plantilla de 6 bahías'),
                    ),
                    const SizedBox(height: 24),
                  ],
                  SectionCard(
                    title: 'Zonas (${zones.length})',
                    trailing: TextButton.icon(
                      onPressed: _saving ? null : () => _edit(),
                      icon: const Icon(Icons.add),
                      label: const Text('Nueva zona'),
                    ),
                    child: zones.isEmpty
                        ? const Text('Aún no hay zonas guardadas.')
                        : Column(
                            children: [
                              for (final zone in zones)
                                ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  title: Text(zone['name'] as String),
                                  subtitle: Text(
                                    'Capacidad ${zone['capacity']} · x ${zone['x']} · y ${zone['y']}',
                                  ),
                                  trailing: IconButton(
                                    tooltip: 'Editar zona',
                                    onPressed: () => _edit(row: zone),
                                    icon: const Icon(Icons.edit_outlined),
                                  ),
                                ),
                            ],
                          ),
                  ),
                  const SizedBox(height: 18),
                  SectionCard(
                    title: 'Bahías (${bays.length})',
                    trailing: TextButton.icon(
                      onPressed: _saving || zones.isEmpty
                          ? null
                          : () => _edit(bay: true),
                      icon: const Icon(Icons.add),
                      label: const Text('Nueva bahía'),
                    ),
                    child: bays.isEmpty
                        ? const Text('Aún no hay bahías guardadas.')
                        : Column(
                            children: [
                              for (final bay in bays)
                                ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  title: Text(bay['name'] as String),
                                  subtitle: Text(
                                    '${bay['active'] == true ? 'Activa' : 'Fuera de servicio'} · Capacidad ${bay['capacity']}',
                                  ),
                                  trailing: Wrap(
                                    children: [
                                      IconButton(
                                        tooltip: 'Editar bahía',
                                        onPressed: () =>
                                            _edit(row: bay, bay: true),
                                        icon: const Icon(Icons.edit_outlined),
                                      ),
                                      IconButton(
                                        tooltip: bay['active'] == true
                                            ? 'Desactivar bahía'
                                            : 'Reactivar bahía',
                                        onPressed: () => _availability(bay),
                                        icon: Icon(
                                          bay['active'] == true
                                              ? Icons.pause_circle_outline
                                              : Icons.play_circle_outline,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                            ],
                          ),
                  ),
                ],
              ),
            ),
    );
  }
}

class WorkshopTemplatePreview extends StatelessWidget {
  const WorkshopTemplatePreview({super.key});
  @override
  Widget build(BuildContext context) => ConstrainedBox(
    constraints: const BoxConstraints(maxHeight: 320),
    child: AspectRatio(
      aspectRatio: 1400 / 900,
      child: Semantics(
        image: true,
        label: 'Plantilla ilustrativa de seis bahías, sin ocupaciones',
        child: SvgPicture.asset(
          'assets/visual/plano_taller_base.svg',
          fit: BoxFit.contain,
        ),
      ),
    ),
  );
}
