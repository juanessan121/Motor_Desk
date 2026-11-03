import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/state/make_logo_cache.dart';
import '../../shared/atelier_controls.dart';
import '../../core/config/theme_controller.dart';
import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';
import '../orders/order_widgets.dart';
import '../customer/customer_passport.dart';
import 'inspection_editor.dart';
import 'vehicle_diagnostic_viewer.dart';
import 'vehicle_template.dart';

Future<void> openPassport(BuildContext context, int vehicleId) async {
  await Navigator.of(context).push<void>(
    MaterialPageRoute(builder: (_) => VehiclePassport(vehicleId: vehicleId)),
  );
}

class VehiclePassport extends StatefulWidget {
  const VehiclePassport({super.key, required this.vehicleId});
  final int vehicleId;
  @override
  State<VehiclePassport> createState() => _VehiclePassportState();
}

class _VehiclePassportState extends State<VehiclePassport> {
  late Future<Json> future;
  int lastRevision = -1;
  String? lastAccess;
  String viewId = 'vehicle_top';
  String component = 'motor';
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = context.watch<WorkshopController>();
    final config = context.watch<ThemeController>().config;
    final access = '${state.sessionEpoch}:${state.user?['id']}:${config.features}';
    if (lastRevision != state.dataRevision || lastAccess != access) {
      lastRevision = state.dataRevision;
      lastAccess = access;
      if (state.signedIn && (!state.isCustomer || config.enabled('vehicles'))) future = load();
    }
  }

  Future<Json> load() async {
    final state = context.read<WorkshopController>();
    final result =
        await state.api.request('GET', '/vehicles/${widget.vehicleId}/passport')
            as Json;
    await VehicleTemplate.load();
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final flags = context.watch<ThemeController>().config;
    final allowed =
        state.signedIn && (!state.isCustomer || flags.enabled('vehicles'));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pasaporte digital'),
        actions: [
          IconButton(
            tooltip: 'Actualizar expediente',
            onPressed: () => setState(() => future = load()),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !allowed
          ? const EmptyState(
              title: 'Acceso no disponible',
              message: 'Inicia sesión o revisa los permisos de tu cuenta.',
            )
          : FutureBuilder<Json>(
              future: future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return EmptyState(
                    title: 'No se puede consultar el expediente',
                    message: snapshot.error.toString(),
                    action: TextButton(onPressed: () => setState(() => future = load()), child: const Text('Reintentar')),
                  );
                }
                final data = snapshot.data!;
                final vehicle = Vehicle(data['vehicle'] as Json);
                return FutureBuilder<List<VehicleTemplate>>(
                  future: VehicleTemplate.load(),
                  builder: (context, loaded) {
                    if (!loaded.hasData) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    final template = loaded.data!
                        .where((item) => item.id == data['template_id'])
                        .first;
                    if (state.isCustomer) return CustomerPassportBody(data: data, template: template);
                    final view = template.views.firstWhere(
                      (item) => item.id == viewId,
                    );
                    final states = Map<String, dynamic>.from(
                      data['component_states'] as Map,
                    );
                    final inspected = jsonList(data['inspections']);
                    final findings = [
                      for (final inspection in inspected)
                        for (final finding in jsonList(inspection['findings']))
                          if (finding['component_id'] == component)
                            {...finding, 'inspection': inspection},
                    ];
                    final status = states[component] as Json? ?? {};
                    final diagnostics = Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            for (final item in template.views.where(
                              (view) => view.passport,
                            ))
                              ChoiceChip(
                                label: Text(item.label),
                                selected: item.id == viewId,
                                onSelected: (_) =>
                                    setState(() => viewId = item.id),
                              ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        VehicleDiagnosticViewer(
                          template: template,
                          view: view,
                          states: states,
                          height: viewId == 'vehicle_top' ? 480 : 330,
                          onPoint: (point) =>
                              setState(() => component = point.componentId),
                        ),
                        const SizedBox(height: 16),
                        const Text(
                          'Componentes · alternativa accesible al visor',
                          style: TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            for (final item in template.components)
                              ChoiceChip(
                                label: Text(item['label'] as String),
                                selected: component == item['id'],
                                onSelected: (_) => setState(
                                  () => component = item['id'] as String,
                                ),
                              ),
                          ],
                        ),
                      ],
                    );
                    final contextPanel = SectionCard(
                      title: template.label(component),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.circle,
                                size: 12,
                                color: conditionColor(
                                  status['condition'] as String?,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  conditionLabels[status['condition']] ??
                                      'Sin datos',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            status['date'] == null
                                ? 'No hay una inspección revisada disponible para este componente.'
                                : 'Estado documentado: ${shortDate(status['date'])}. No es una lectura en tiempo real.',
                            style: const TextStyle(fontSize: 12, height: 1.6),
                          ),
                          for (final finding in findings)
                            Padding(
                              padding: const EdgeInsets.only(top: 18),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    finding['note'] as String,
                                    style: const TextStyle(height: 1.6),
                                  ),
                                  const SizedBox(height: 7),
                                  Text(
                                    '${finding['category']} · ${finding['severity']} · ${shortDate(finding['created_at'])}',
                                    style: const TextStyle(fontSize: 11),
                                  ),
                                  const SizedBox(height: 8),
                                  TextButton(
                                    onPressed: () => openInspectionEditor(
                                      context,
                                      inspectionId:
                                          (finding['inspection'] as Json)['id']
                                              as int,
                                    ),
                                    child: const Text(
                                      'Ver inspección y evidencias',
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          if (!state.isCustomer) ...[
                            const SizedBox(height: 18),
                            OutlinedButton.icon(
                              onPressed: () => createInspectionDialog(
                                context,
                                widget.vehicleId,
                              ),
                              icon: const Icon(Icons.fact_check_outlined),
                              label: const Text('Registrar inspección'),
                            ),
                          ],
                        ],
                      ),
                    );
                    return SingleChildScrollView(
                      padding: EdgeInsets.all(
                        MediaQuery.sizeOf(context).width < 700 ? 18 : 32,
                      ),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 1400),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              PageHeading(
                                title: '${vehicle.name} · ${vehicle.plate}',
                                subtitle:
                                    '${vehicle.json['year']} · ${vehicle.json['mileage']} km registrados${state.isMechanic ? '' : ' · ${vehicle.ownerName}'}',
                              ),
                              const SizedBox(height: 16),
                              VehicleIdentityCard(vehicle: vehicle),
                              const SizedBox(height: 9),
                              Text(
                                template.json['disclaimer'] as String,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF64748B),
                                ),
                              ),
                              const SizedBox(height: 24),
                              LayoutBuilder(
                                builder: (context, constraints) =>
                                    constraints.maxWidth < 940
                                    ? Column(
                                        children: [
                                          diagnostics,
                                          const SizedBox(height: 22),
                                          contextPanel,
                                        ],
                                      )
                                    : Row(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Expanded(flex: 7, child: diagnostics),
                                          const SizedBox(width: 24),
                                          Expanded(
                                            flex: 4,
                                            child: contextPanel,
                                          ),
                                        ],
                                      ),
                              ),
                              if (!state.isCustomer ||
                                  flags.enabled('history')) ...[
                                const SizedBox(height: 26),
                                SectionCard(
                                  title: 'Inspecciones y versiones publicadas',
                                  child: inspected.isEmpty
                                      ? const Text(
                                          'Sin inspecciones disponibles. El gris no representa un diagnóstico normal.',
                                        )
                                      : Column(
                                          children: [
                                            for (final inspection in inspected)
                                              ListTile(
                                                contentPadding: EdgeInsets.zero,
                                                leading: const Icon(
                                                  Icons.fact_check_outlined,
                                                ),
                                                title: Text(
                                                  inspection['title'] as String,
                                                ),
                                                subtitle: Text(
                                                  'v${inspection['revision']} · ${inspection['review_status'] == 'draft' ? 'Borrador interno' : 'Revisada'} · ${shortDate(inspection['created_at'])}${inspection['published_revision'] == null ? '' : ' · Publicada v${inspection['published_revision']}'}',
                                                ),
                                                trailing: const Icon(
                                                  Icons.chevron_right,
                                                ),
                                                onTap: () =>
                                                    openInspectionEditor(
                                                      context,
                                                      inspectionId:
                                                          inspection['id']
                                                              as int,
                                                    ),
                                              ),
                                          ],
                                        ),
                                ),
                                const SizedBox(height: 22),
                                SectionCard(
                                  title: 'Intervenciones registradas',
                                  child: jsonList(data['history']).isEmpty
                                      ? const Text('Sin servicios registrados.')
                                      : Column(
                                          children: [
                                            for (final row in jsonList(
                                              data['history'],
                                            ))
                                              ListTile(
                                                contentPadding: EdgeInsets.zero,
                                                title: Text(
                                                  row['title'] as String,
                                                ),
                                                subtitle: Text(
                                                  'Apertura: ${shortDate(row['date'])}\nTareas realizadas: ${(row['tasks'] as List).isEmpty ? 'Sin finalización registrada' : (row['tasks'] as List).join(' · ')}',
                                                ),
                                                trailing: StatusChip(
                                                  row['status'] as String,
                                                ),
                                              ),
                                          ],
                                        ),
                                ),
                              ],
                              if (!state.isCustomer ||
                                  flags.enabled('maintenance')) ...[
                                const SizedBox(height: 22),
                                SectionCard(
                                  title: 'Órdenes autorizadas',
                                  child: jsonList(data['orders']).isEmpty
                                      ? const Text(
                                          'No hay órdenes visibles para esta cuenta.',
                                        )
                                      : Column(
                                          children: [
                                            for (final row in jsonList(
                                              data['orders'],
                                            ))
                                              ListTile(
                                                contentPadding: EdgeInsets.zero,
                                                title: Text(
                                                  '#${row['id']} · ${row['title']}',
                                                ),
                                                trailing: StatusChip(
                                                  row['status'] as String,
                                                ),
                                                onTap: () => openOrder(
                                                  context,
                                                  row['id'] as int,
                                                ),
                                              ),
                                          ],
                                        ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                );
              },
            ),
    );
  }
}

/// Ficha de identidad del vehículo, al abrir el expediente.
///
/// Distingue lo que el taller **ha documentado** de lo que viene del
/// **catálogo de referencia**. Hoy la cabecera solo repetía el nombre; sin
/// esa separación alguien podría leer «Hyundai i20 1.6» como un dato verificado
/// de ese coche cuando lo que dice es que el modelo existe en el catálogo.
///
/// La referencia del catálogo se muestra como lo que es: **una coincidencia
/// con el catálogo de referencia**, no una identificación. Cuando no resolvió,
/// lo dice con la misma claridad que cuando sí.
class VehicleIdentityCard extends StatelessWidget {
  const VehicleIdentityCard({super.key, required this.vehicle});
  final Vehicle vehicle;

  @override
  Widget build(BuildContext context) {
    final palette = context.atelier;
    final year = vehicle.json['year'];
    final brand = vehicle.json['brand'] as String?;
    final model = vehicle.json['model'] as String?;
    final catalog = vehicle.json['catalog'] as Json?;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            MakeLogo(
              make: brand,
              size: 52,
              radius: 13,
              logoUrl: catalog?['logo_url'] as String?,
              loadCatalog: false,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      const AtelierBadge(
                        'Registro del taller',
                        icon: Icons.description_outlined,
                        dense: true,
                      ),
                      if (brand == null || brand.toString().trim().isEmpty)
                        const AtelierBadge(
                          'Marca sin especificar',
                          icon: Icons.help_outline,
                          dense: true,
                        ),
                      if (year == null)
                        const AtelierBadge(
                          'Año sin registrar',
                          icon: Icons.help_outline,
                          dense: true,
                        ),
                    ],
                  ),
                  if (catalog != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Referencia de catálogo: '
                      '${catalog['make_name']}'
                      '${catalog['model_name'] != null ? ' · ${catalog['model_name']}' : ''}'
                      '${catalog['generation_name'] != null ? ' · ${catalog['generation_name']}' : ''}.',
                      style: TextStyle(
                        fontSize: 12,
                        height: 1.5,
                        color: palette.secondaryText,
                      ),
                    ),
                    if (catalog['generation_name'] == null)
                      Text(
                        'Generación sin seleccionar o sin coincidencia inequívoca.',
                        style: TextStyle(
                          fontSize: 12,
                          height: 1.5,
                          color: palette.secondaryText,
                        ),
                      ),
                    const SizedBox(height: 8),
                    if (catalog['engine'] is Map) ...[
                      Text(
                        'Motor de referencia: ${(catalog['engine'] as Map)['label']}',
                      ),
                      Wrap(
                        spacing: 12,
                        runSpacing: 6,
                        children: [
                          for (final entry in {
                            'displacement_cc': 'cc',
                            'power_hp': 'hp',
                            'torque_nm': 'Nm',
                          }.entries)
                            if ((catalog['engine'] as Map)[entry.key] != null)
                              Text(
                                '${(catalog['engine'] as Map)[entry.key]} ${entry.value}',
                              ),
                        ],
                      ),
                    ] else
                      const Text(
                        'Motor sin seleccionar. No se deduce de la marca, el modelo o el año.',
                      ),
                    const SizedBox(height: 8),
                    const Text(
                      'Datos de referencia; no certifican la motorización ni el estado de este vehículo.',
                    ),
                  ] else ...[
                    const SizedBox(height: 12),
                    Text(
                      'Sin referencia al catálogo guardada para «${brand ?? ''} ${model ?? ''}». '
                      'El vehículo se gestiona igualmente. La referencia puede '
                      'seleccionarse al editar su registro.',
                      style: TextStyle(
                        fontSize: 12,
                        height: 1.5,
                        color: palette.secondaryText,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
