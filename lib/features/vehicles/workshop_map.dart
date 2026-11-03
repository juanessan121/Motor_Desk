import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/models/entities.dart' show jsonList;
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';
import '../orders/order_widgets.dart';
import 'workshop_layout_page.dart';

enum BayState {
  available,
  occupied,
  maintenance,
  ready,
  unavailable,
  attention,
}

BayState workshopBayState(Json bay) {
  if (bay['active'] != true) return BayState.unavailable;
  final occupied = jsonList(bay['occupancies']);
  if (occupied.isEmpty) return BayState.available;
  if (occupied.any((row) => row['attention_required'] == true)) {
    return BayState.attention;
  }
  if (occupied.every((row) => row['status'] == 'ready')) return BayState.ready;
  if (occupied.any(
    (row) =>
        row['operational_stage'] == 'in_progress' ||
        (row['operational_stage'] == null && row['status'] == 'in_progress'),
  )) {
    return BayState.maintenance;
  }
  return BayState.occupied;
}

const bayStateLabels = {
  BayState.available: 'Disponible',
  BayState.occupied: 'Ocupado',
  BayState.maintenance: 'En mantenimiento',
  BayState.ready: 'Trabajo finalizado',
  BayState.unavailable: 'Fuera de servicio',
  BayState.attention: 'Atención requerida',
};

Color bayStateColor(BuildContext context, BayState state) => switch (state) {
  BayState.available => context.atelier.success,
  BayState.occupied => const Color(0xFF2563EB),
  BayState.maintenance => context.atelier.warning,
  BayState.ready => const Color(0xFF20B9B0),
  BayState.unavailable => context.atelier.unknown,
  BayState.attention => context.atelier.danger,
};

class WorkshopMapPage extends StatefulWidget {
  const WorkshopMapPage({super.key});
  @override
  State<WorkshopMapPage> createState() => _WorkshopMapPageState();
}

class _WorkshopMapPageState extends State<WorkshopMapPage> {
  Json? _layout;
  String? _error;
  bool _loading = false;
  bool _moving = false;
  bool _showZones = true;
  int _request = 0;
  int _revision = -1;
  int? _selectedBay;
  int? _selectedOrder;
  final _transform = TransformationController();

  ApiClient get api => context.read<WorkshopController>().api;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = context.watch<WorkshopController>();
    if ((state.isAdmin || state.isMechanic) && _revision != state.dataRevision) {
      _revision = state.dataRevision;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _load();
      });
    }
  }

  @override
  void dispose() {
    _transform.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final request = ++_request;
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final state = context.read<WorkshopController>();
      final path = state.isMechanic
          ? '/workshop/mechanic-view'
          : '/workshop/layout?include_inactive=true';
      final data = await api.request('GET', path) as Json;
      if (!mounted || request != _request) return;
      setState(() {
        _layout = data;
        if (!jsonList(data['bays']).any((bay) => bay['id'] == _selectedBay)) {
          _selectedBay = null;
        }
        if (!jsonList(
          data['orders'],
        ).any((order) => order['id'] == _selectedOrder)) {
          _selectedOrder = null;
        }
      });
    } catch (failure) {
      if (mounted && request == _request) {
        setState(() => _error = failure.toString());
      }
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  Future<void> _configure() async {
    await Navigator.of(
      context,
    ).push<void>(MaterialPageRoute(builder: (_) => const WorkshopLayoutPage()));
    if (mounted) await _load();
  }

  Future<void> _move(int orderId, int? bayId) async {
    if (_moving || _loading || _error != null) return;
    final orders = jsonList(_layout?['orders']);
    final order = orders.where((row) => row['id'] == orderId).firstOrNull;
    if (order == null) return;
    final bay = jsonList(
      _layout?['bays'],
    ).where((row) => row['id'] == bayId).firstOrNull;
    final expected =
        order['occupancy_id']; // Capturado antes de abrir el diálogo.
    await showEditor(
      context,
      title: bayId == null
          ? 'Retirar de la bahía'
          : 'Mover a ${bay?['name'] ?? 'bahía'}',
      description:
          '${order['plate']} · Orden #$orderId. Se validarán capacidad y ubicación actual. No cambia el estado mecánico ni finaliza el trabajo.',
      fields: const [
        EditorField(
          'reason',
          'Motivo del movimiento',
          initial: 'Movimiento registrado desde el plano',
        ),
      ],
      submitLabel: 'Confirmar movimiento',
      onSubmit: (values) async {
        if (_moving) return;
        setState(() => _moving = true);
        try {
          await api.request(
            'POST',
            '/orders/$orderId/location',
            body: {
              'bay_id': bayId,
              'reason': values['reason'],
              'expected_occupancy_id': expected,
            },
          );
          await _load();
          if (mounted) {
            await context.read<WorkshopController>().refresh().catchError(
              (Object _) {},
            );
          }
        } catch (failure) {
          if (failure is ApiException && failure.statusCode == 409) {
            await _load();
          }
          rethrow;
        } finally {
          if (mounted) setState(() => _moving = false);
        }
      },
    );
  }

  void _zoom(double factor) {
    final scale = (_transform.value.getMaxScaleOnAxis() * factor).clamp(
      1.0,
      4.0,
    );
    _transform.value = Matrix4.diagonal3Values(scale, scale, 1);
  }

  Future<void> _assign(int orderId) async {
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => _AssignmentDialog(api: api, orderId: orderId),
    );
    if (mounted && saved == true) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    if (!state.isAdmin && !state.isMechanic) {
      return const EmptyState(
        title: 'Acceso restringido',
        message: 'La vista del taller es para el personal operativo y de administración.',
      );
    }
    if (_layout == null && _loading) {
      return const Center(child: CircularProgressIndicator());
    }
    final bays = jsonList(_layout?['bays']);
    final zones = jsonList(_layout?['zones']);
    final orders = jsonList(_layout?['orders']);
    final selected = bays.where((bay) => bay['id'] == _selectedBay).firstOrNull;
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PageHeading(
            title: 'Vista del taller',
            subtitle: state.isMechanic
                ? 'Vehículos asignados, órdenes de trabajo y estado operativo.'
                : 'Posiciones registradas, órdenes activas y responsables.',
            action: state.isAdmin
                ? OutlinedButton.icon(
                    onPressed: _loading ? null : _configure,
                    icon: const Icon(Icons.settings_outlined),
                    label: const Text('Configurar plano'),
                  )
                : null,
          ),
          if (_loading || _moving) const LinearProgressIndicator(),
          if (_error != null) ...[
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            TextButton(onPressed: _load, child: const Text('Reintentar plano')),
          ],
          const SizedBox(height: 16),
          if (_layout != null && (zones.isEmpty || bays.isEmpty)) ...[
            SectionCard(
              title: 'No hay plano configurado',
              subtitle: state.isAdmin
                  ? 'Configura las bahías para ver la ocupación gráfica del taller, o inicializa la distribución estándar de 6 bahías.'
                  : 'El taller aún no tiene bahías activas en el plano.',
              child: const WorkshopTemplatePreview(),
            ),
            const SizedBox(height: 12),
            if (state.isAdmin)
              Wrap(
                spacing: 12,
                children: [
                  FilledButton.icon(
                    onPressed: _loading
                        ? null
                        : () async {
                            final messenger = ScaffoldMessenger.of(context);
                            try {
                              await api.request(
                                'POST',
                                '/workshop/layout/init-default',
                              );
                              await _load();
                            } catch (e) {
                              messenger.showSnackBar(
                                SnackBar(content: Text('Error: $e')),
                              );
                            }
                          },
                    icon: const Icon(Icons.flash_on_outlined),
                    label: const Text('Inicializar 6 bahías estándar'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _configure,
                    icon: const Icon(Icons.map_outlined),
                    label: const Text('Configurar zonas y bahías'),
                  ),
                ],
              ),
          ] else if (_layout != null) ...[
            Wrap(
              spacing: 10,
              runSpacing: 10,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                if (state.isAdmin) ...[
                  SizedBox(
                    width: 260,
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        labelText: 'Orden activa',
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<int>(
                          value: _selectedOrder,
                          isExpanded: true,
                          hint: const Text('Seleccionar orden'),
                          items: [
                            for (final order in orders)
                              DropdownMenuItem(
                                value: order['id'] as int,
                                child: Text(
                                  '#${order['id']} · ${order['plate']}',
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                          ],
                          onChanged: (value) =>
                              setState(() => _selectedOrder = value),
                        ),
                      ),
                    ),
                  ),
                  SizedBox(
                    width: 240,
                    child: InputDecorator(
                      decoration: const InputDecoration(labelText: 'Destino'),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<int>(
                          value: _selectedBay,
                          isExpanded: true,
                          items: [
                            const DropdownMenuItem<int>(
                              value: null,
                              child: Text('Sin asignar / retirar'),
                            ),
                            for (final bay in bays)
                              DropdownMenuItem(
                                value: bay['id'] as int,
                                child: Text(
                                  '${bay['name']} · ${bayStateLabels[workshopBayState(bay)]}',
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                          ],
                          onChanged: (value) =>
                              setState(() => _selectedBay = value),
                        ),
                      ),
                    ),
                  ),
                  FilledButton.icon(
                    onPressed:
                        _selectedOrder == null ||
                            _loading ||
                            _moving ||
                            _error != null
                        ? null
                        : () => _move(_selectedOrder!, _selectedBay),
                    icon: const Icon(Icons.swap_horiz),
                    label: const Text('Mover orden'),
                  ),
                ],
                IconButton(
                  tooltip: 'Actualizar plano',
                  onPressed: _loading ? null : _load,
                  icon: const Icon(Icons.refresh),
                ),
                IconButton(
                  tooltip: 'Acercar plano',
                  onPressed: () => _zoom(1.25),
                  icon: const Icon(Icons.zoom_in),
                ),
                IconButton(
                  tooltip: 'Alejar plano',
                  onPressed: () => _zoom(.8),
                  icon: const Icon(Icons.zoom_out),
                ),
                TextButton.icon(
                  onPressed: () => _transform.value = Matrix4.identity(),
                  icon: const Icon(Icons.center_focus_strong),
                  label: const Text('Restablecer'),
                ),
                FilterChip(
                  label: const Text('Mostrar zonas'),
                  selected: _showZones,
                  onSelected: (value) => setState(() => _showZones = value),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                for (final state in BayState.values)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        state == BayState.attention
                            ? Icons.warning_amber_rounded
                            : state == BayState.unavailable
                            ? Icons.pause_circle_outline
                            : Icons.circle,
                        size: 14,
                        color: bayStateColor(context, state),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        bayStateLabels[state]!,
                        style: const TextStyle(fontSize: 12),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 14),
            AspectRatio(
              aspectRatio: 1400 / 900,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: InteractiveViewer(
                  transformationController: _transform,
                  minScale: 1,
                  maxScale: 4,
                  child: LayoutBuilder(
                    builder: (context, bounds) => Stack(
                      children: [
                        Positioned.fill(
                          child: SvgPicture.asset(
                            'assets/visual/plano_taller_operativo.svg',
                            fit: BoxFit.fill,
                          ),
                        ),
                        if (_showZones)
                          for (final zone in zones)
                            _position(
                              zone,
                              bounds,
                              IgnorePointer(
                                child: Container(
                                  decoration: BoxDecoration(
                                    border: Border.all(color: Colors.white24),
                                    color: Colors.white.withValues(alpha: .02),
                                  ),
                                ),
                              ),
                            ),
                        for (final bay in bays)
                          _position(
                            bay,
                            bounds,
                            DragTarget<int>(
                              onWillAcceptWithDetails: (details) =>
                                  bay['active'] == true &&
                                  !_moving &&
                                  !_loading &&
                                  !jsonList(bay['occupancies']).any(
                                    (entry) =>
                                        entry['order_id'] == details.data,
                                  ) &&
                                  jsonList(bay['occupancies']).length <
                                      (bay['capacity'] as int),
                              onAcceptWithDetails: (details) =>
                                  _move(details.data, bay['id'] as int),
                              builder: (context, candidates, rejected) =>
                                  _BayTile(
                                    bay: bay,
                                    selected:
                                        bay['id'] == _selectedBay ||
                                        candidates.isNotEmpty,
                                    onTap: () => setState(
                                      () => _selectedBay = bay['id'] as int,
                                    ),
                                  ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Haz clic en una bahía para ver sus órdenes. Puedes arrastrar una tarjeta hacia un puesto disponible; cada movimiento requiere confirmación y se guarda en la API.',
            ),
            const SizedBox(height: 16),
            if (selected != null)
              SectionCard(
                title: selected['name'] as String,
                subtitle:
                    '${bayStateLabels[workshopBayState(selected)]} · ${jsonList(selected['occupancies']).length}/${selected['capacity']} puestos',
                child: jsonList(selected['occupancies']).isEmpty
                    ? const Text('No hay vehículos asignados a esta bahía.')
                    : Column(
                        children: [
                          for (final entry in jsonList(selected['occupancies']))
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: Text(
                                '${entry['plate']} · Orden #${entry['order_id']}',
                              ),
                              subtitle: Text(
                                '${entry['title']}\nResponsables: ${_mechanics(entry)}',
                              ),
                              onTap: () =>
                                  openOrder(context, entry['order_id'] as int),
                              trailing: IconButton(
                                tooltip: 'Retirar de la bahía',
                                onPressed: _moving
                                    ? null
                                    : () =>
                                          _move(entry['order_id'] as int, null),
                                icon: const Icon(Icons.exit_to_app),
                              ),
                            ),
                        ],
                      ),
              ),
            const SizedBox(height: 16),
            SectionCard(
              title: 'Bahías · alternativa accesible al plano',
              child: Column(
                children: [
                  for (final bay in bays)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(
                        bay['active'] == true
                            ? Icons.garage_outlined
                            : Icons.pause_circle_outline,
                        color: bayStateColor(context, workshopBayState(bay)),
                      ),
                      title: Text(bay['name'] as String),
                      subtitle: Text(
                        '${bayStateLabels[workshopBayState(bay)]} · ${jsonList(bay['occupancies']).length}/${bay['capacity']}',
                      ),
                      selected: bay['id'] == _selectedBay,
                      onTap: () =>
                          setState(() => _selectedBay = bay['id'] as int),
                    ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 20),
          SectionCard(
            title: 'Órdenes activas reales (${orders.length})',
            subtitle:
                'Sin asignación significa que aún no hay una ubicación registrada. No se simulan posiciones.',
            child: orders.isEmpty
                ? const Text(
                    'No hay vehículos con órdenes activas. Las bahías guardadas siguen disponibles.',
                  )
                : Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      for (final order in orders)
                        Draggable<int>(
                          data: order['id'] as int,
                          feedback: Material(
                            elevation: 6,
                            borderRadius: BorderRadius.circular(12),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Text(
                                '${order['plate']} · #${order['id']}',
                              ),
                            ),
                          ),
                          childWhenDragging: Opacity(
                            opacity: .35,
                            child: _orderCard(order),
                          ),
                          child: _orderCard(order),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _position(Json geometry, BoxConstraints bounds, Widget child) =>
      Positioned(
        left: (geometry['x'] as num).toDouble() * bounds.maxWidth,
        top: (geometry['y'] as num).toDouble() * bounds.maxHeight,
        width: (geometry['width'] as num).toDouble() * bounds.maxWidth,
        height: (geometry['height'] as num).toDouble() * bounds.maxHeight,
        child: child,
      );

  String _mechanics(Json row) => jsonList(row['mechanics']).isEmpty
      ? 'Sin mecánico asignado'
      : jsonList(
          row['mechanics'],
        ).map((mechanic) => mechanic['username']).join(', ');

  Widget _orderCard(Json order) => SizedBox(
    width: 280,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${order['plate']} · #${order['id']}',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            Text(order['title'] as String),
            const SizedBox(height: 8),
            StatusChip(order['status'] as String),
            Text(
              order['occupancy_id'] == null
                  ? 'Sin ubicación registrada'
                  : 'Ubicación guardada',
            ),
            Text(_mechanics(order)),
            Wrap(
              children: [
                TextButton(
                  onPressed: () => openOrder(context, order['id'] as int),
                  child: const Text('Ver orden'),
                ),
                TextButton(
                  onPressed: () => _assign(order['id'] as int),
                  child: const Text('Asignar mecánico'),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

class _BayTile extends StatelessWidget {
  const _BayTile({
    required this.bay,
    required this.selected,
    required this.onTap,
  });
  final Json bay;
  final bool selected;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final state = workshopBayState(bay), entries = jsonList(bay['occupancies']);
    final color = bayStateColor(context, state);
    return Semantics(
      button: true,
      selected: selected,
      label:
          '${bay['name']}. ${bayStateLabels[state]}. ${entries.length} de ${bay['capacity']}',
      child: Material(
        color: Color.alphaBlend(
          color.withValues(alpha: .18),
          const Color(0xFF17222D),
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(
            color: selected ? Colors.white : color,
            width: selected ? 3 : 2,
          ),
        ),
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(5),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Column(
                children: [
                  Icon(
                    state == BayState.attention
                        ? Icons.warning_amber_rounded
                        : entries.isEmpty
                        ? Icons.garage_outlined
                        : Icons.directions_car,
                    color: color,
                    size: 22,
                  ),
                  Text(
                    bay['name'] as String,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text(
                    bayStateLabels[state]!,
                    style: TextStyle(color: color, fontSize: 11),
                  ),
                  Text(
                    '${entries.length}/${bay['capacity']}',
                    style: const TextStyle(color: Colors.white, fontSize: 11),
                  ),
                  for (final entry in entries)
                    Text(
                      entry['plate'] as String,
                      style: const TextStyle(color: Colors.white, fontSize: 11),
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

class _AssignmentDialog extends StatefulWidget {
  const _AssignmentDialog({required this.api, required this.orderId});
  final ApiClient api;
  final int orderId;
  @override
  State<_AssignmentDialog> createState() => _AssignmentDialogState();
}

class _AssignmentDialogState extends State<_AssignmentDialog> {
  late final Future<List<dynamic>> _data;
  final Set<int> _tasks = {};
  int? _mechanic;
  bool _saving = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _data = Future.wait([
      widget.api.request('GET', '/staff/mechanics'),
      widget.api.request('GET', '/orders/${widget.orderId}'),
    ]);
  }

  Future<void> _save() async {
    if (_saving) return;
    if (_mechanic == null || _tasks.isEmpty) {
      setState(() => _error = 'Selecciona un mecánico y al menos una tarea.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '/orders/${widget.orderId}/assignments',
        body: {
          'mechanic_id': _mechanic,
          'task_ids': _tasks.toList(),
          'can_quote': false,
        },
      );
      if (mounted) Navigator.pop(context, true);
    } catch (failure) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = failure.toString();
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Asignar mecánico'),
    content: SizedBox(
      width: 460,
      child: FutureBuilder<List<dynamic>>(
        future: _data,
        builder: (context, snapshot) {
          if (snapshot.hasError) return Text(snapshot.error.toString());
          if (!snapshot.hasData) {
            return const SizedBox(
              height: 80,
              child: Center(child: CircularProgressIndicator()),
            );
          }
          final mechanics = jsonList(snapshot.data![0]),
              order = snapshot.data![1] as Json;
          return SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (mechanics.isEmpty)
                  const Text(
                    'No hay mecánicos activos registrados en este taller.',
                  ),
                DropdownButtonFormField<int>(
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Mecánico'),
                  items: [
                    for (final mechanic in mechanics)
                      DropdownMenuItem(
                        value: mechanic['id'] as int,
                        child: Text(mechanic['username'] as String),
                      ),
                  ],
                  onChanged: _saving ? null : (value) => _mechanic = value,
                ),
                for (final task in jsonList(order['items']))
                  CheckboxListTile(
                    title: Text(task['label'] as String),
                    value: _tasks.contains(task['id']),
                    onChanged: _saving
                        ? null
                        : (selected) => setState(() {
                            if (selected == true) {
                              _tasks.add(task['id'] as int);
                            } else {
                              _tasks.remove(task['id']);
                            }
                          }),
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
          );
        },
      ),
    ),
    actions: [
      TextButton(
        onPressed: _saving ? null : () => Navigator.pop(context),
        child: const Text('Cancelar'),
      ),
      FilledButton(
        onPressed: _saving ? null : _save,
        child: const Text('Guardar asignación'),
      ),
    ],
  );
}
