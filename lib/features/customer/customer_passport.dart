import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/config/regional_format.dart';
import '../../core/config/theme_controller.dart';
import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';
import '../orders/order_widgets.dart';
import '../vehicles/inspection_editor.dart';
import '../vehicles/vehicle_diagnostic_viewer.dart';
import '../vehicles/vehicle_passport.dart' show VehicleIdentityCard;
import '../vehicles/vehicle_template.dart';

/// Presentación de solo lectura del Pasaporte existente, no otro módulo.
class CustomerPassportBody extends StatelessWidget {
  const CustomerPassportBody({super.key, required this.data, required this.template});
  final Json data;
  final VehicleTemplate template;

  @override
  Widget build(BuildContext context) {
    final flags = context.watch<ThemeController>().config;
    final vehicle = Vehicle(data['vehicle'] as Json);
    final format = RegionalFormat(flags.regional);
    final states = Map<String, dynamic>.from(data['component_states'] as Map);
    final inspections = jsonList(data['inspections']);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(18),
      child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 860), child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('${vehicle.name} · ${vehicle.plate}', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Text('${vehicle.json['year']} · ${format.distance(vehicle.json['mileage'])} registrados'),
          const SizedBox(height: 16),
          VehicleIdentityCard(vehicle: vehicle),
          if (flags.enabled('history')) ...[
            const SizedBox(height: 18),
            SectionCard(title: 'Estados documentados', subtitle: 'Información publicada por el taller. No son sensores ni un diagnóstico en tiempo real.',
              child: Column(children: [
                for (final component in template.components)
                  ListTile(contentPadding: EdgeInsets.zero,
                    title: Text(component['label'] as String),
                    subtitle: Text((states[component['id']] as Map?)?['date'] == null ? 'Sin inspección publicada' :
                      'Documentado: ${format.date((states[component['id']] as Map)['date'])}'),
                    trailing: AtelierStateBadge.condition((states[component['id']] as Map?)?['condition'] as String?, context, dense: true)),
              ])),
            const SizedBox(height: 18),
            Card(child: ExpansionTile(title: const Text('Ver diagrama ilustrativo'),
              subtitle: const Text('Alternativa visual a la lista de componentes'),
              children: [VehicleDiagnosticViewer(template: template,
                view: template.views.firstWhere((view) => view.id == 'vehicle_side'),
                states: states, height: 260,
                onPoint: (point) => showDialog<void>(context: context, builder: (context) => AlertDialog(
                  title: Text(template.label(point.componentId)),
                  content: Text(conditionLabels[(states[point.componentId] as Map?)?['condition']] ?? 'Sin datos'),
                  actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cerrar'))],
                ))),
              ])),
            const SizedBox(height: 18),
            SectionCard(title: 'Informes publicados', child: inspections.isEmpty
              ? const Text('No hay inspecciones publicadas para esta cuenta.')
              : Column(children: [for (final report in inspections)
                ListTile(contentPadding: EdgeInsets.zero, title: Text(report['title'] as String),
                  subtitle: Text('Publicado: ${format.date(report['published_at'])} · v${report['published_revision']}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => openInspectionEditor(context, inspectionId: report['id'] as int)),
              ])),
            const SizedBox(height: 18),
            SectionCard(title: 'Intervenciones documentadas', subtitle: 'Solo tareas registradas como completadas. No acredita cambios de piezas ni reparaciones no documentadas.',
              child: jsonList(data['history']).isEmpty ? const Text('Sin intervenciones registradas.') :
                Column(children: [for (final entry in jsonList(data['history']))
                  ListTile(contentPadding: EdgeInsets.zero, title: Text(entry['title'] as String),
                    subtitle: Text('${format.date(entry['date'])}\n${(entry['tasks'] as List).isEmpty ? 'Sin tareas finalizadas registradas' : (entry['tasks'] as List).join(' · ')}')),
                ])),
          ] else ...[
            const SizedBox(height: 18),
            const Text('El historial técnico no está habilitado para esta cuenta o dispositivo.'),
          ],
          if (flags.enabled('maintenance')) ...[
            const SizedBox(height: 18),
            SectionCard(title: 'Mis servicios autorizados', child: jsonList(data['orders']).isEmpty ? const Text('Sin servicios visibles para tu cuenta.') :
              Column(children: [for (final entry in jsonList(data['orders']))
                OrderSummaryTile(order: WorkOrder(entry), onTap: () => openOrder(context, entry['id'] as int)),
              ])),
          ],
        ],
      ))),
    );
  }
}
