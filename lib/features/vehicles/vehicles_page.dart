import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';
import '../registry/customer_flow.dart';
import '../registry/registry_page.dart';
import 'garage_view.dart';
import 'catalog_review_page.dart';
import 'automotive_catalog_page.dart';
import 'workshop_map.dart';

class VehiclesPage extends StatefulWidget {
  const VehiclesPage({super.key});
  @override
  State<VehiclesPage> createState() => _VehiclesPageState();
}

class _VehiclesPageState extends State<VehiclesPage> {
  String mode = 'garage';
  String query = '';
  String filter = 'active';
  String brand = 'all';
  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final brands =
        state.vehicles
            .map((row) => row.json['brand'] as String)
            .toSet()
            .toList()
          ..sort();
    final records = state.vehicles
        .where(
          (row) =>
              '${row.plate} ${row.name} ${row.ownerName}'
                  .toLowerCase()
                  .contains(query) &&
              (brand == 'all' || row.json['brand'] == brand) &&
              (filter == 'archived'
                  ? !row.active
                  : filter == 'in_workshop'
                  ? row.active &&
                        state.orders.any(
                          (order) =>
                              order.json['vehicle_id'] == row.id &&
                              !order.closed,
                        )
                  : row.active),
        )
        .toList();
    return Column(
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              for (final entry in {
                'garage': 'Garaje',
                if (state.isAdmin || state.isMechanic) 'workshop': 'Vista del taller',
                'table': 'Tabla',
              }.entries)
                ChoiceChip(
                  label: Text(entry.value),
                  selected: mode == entry.key,
                  onSelected: (_) => setState(() => mode = entry.key),
                ),
              if (state.isAdmin)
                OutlinedButton.icon(
                  icon: const Icon(Icons.fact_check_outlined),
                  label: const Text('Revisar propuestas'),
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const CatalogReviewPage(),
                    ),
                  ),
                ),
              OutlinedButton.icon(
                icon: const Icon(Icons.menu_book_outlined),
                label: const Text('Consultar catálogo'),
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        const AutomotiveCatalogPage(standalone: true),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        Expanded(
          child: mode == 'table'
              ? const RegistryPage(kind: RegistryKind.vehicles)
              : mode == 'workshop' && state.isAdmin
              ? const WorkshopMapPage()
              : SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      PageHeading(
                        title: state.isMechanic
                            ? 'Vehículos de mis asignaciones'
                            : 'Garaje digital',
                        subtitle:
                            'Expedientes reales, siluetas ilustrativas y estados documentados.',
                        action: state.isAdmin
                            ? FilledButton.icon(
                                onPressed: () => startVehicleFlow(context),
                                icon: const Icon(Icons.add),
                                label: const Text('Ingresar vehículo'),
                              )
                            : null,
                      ),
                      const SizedBox(height: 22),
                      Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          SizedBox(
                            width: 300,
                            child: TextField(
                              decoration: const InputDecoration(
                                prefixIcon: Icon(Icons.search),
                                hintText: 'Buscar placa, modelo o propietario',
                              ),
                              onChanged: (text) => setState(
                                () => query = text.toLowerCase().trim(),
                              ),
                            ),
                          ),
                          SizedBox(
                            width: 200,
                            child: DropdownButtonFormField<String>(
                              initialValue: 'all',
                              decoration: const InputDecoration(
                                labelText: 'Marca',
                              ),
                              items: [
                                const DropdownMenuItem(
                                  value: 'all',
                                  child: Text('Todas'),
                                ),
                                for (final item in brands)
                                  DropdownMenuItem(
                                    value: item,
                                    child: Text(item),
                                  ),
                              ],
                              onChanged: (value) =>
                                  setState(() => brand = value ?? 'all'),
                            ),
                          ),
                          for (final entry in {
                            'active': 'Activos',
                            'in_workshop': 'En taller',
                            if (state.isAdmin) 'archived': 'Archivados',
                          }.entries)
                            ChoiceChip(
                              label: Text(entry.value),
                              selected: filter == entry.key,
                              onSelected: (_) =>
                                  setState(() => filter = entry.key),
                            ),
                        ],
                      ),
                      const SizedBox(height: 22),
                      if (records.isEmpty)
                        Card(
                          child: EmptyState(
                            title: state.isMechanic
                                ? 'Sin vehículos asignados'
                                : 'No hay vehículos en esta vista',
                            message: state.isMechanic
                                ? 'El administrador debe asignarte tareas de una orden. No se muestran vehículos ajenos.'
                                : 'Registra un vehículo o ajusta los filtros. No se muestran coches de ejemplo.',
                            icon: Icons.garage_outlined,
                          ),
                        )
                      else
                        LayoutBuilder(
                          builder: (context, constraints) {
                            final columns = constraints.maxWidth >= 1150
                                ? 3
                                : constraints.maxWidth >= 700
                                ? 2
                                : 1;
                            return Wrap(
                              spacing: 18,
                              runSpacing: 18,
                              children: [
                                for (final vehicle in records)
                                  SizedBox(
                                    width:
                                        (constraints.maxWidth -
                                            (columns - 1) * 18) /
                                        columns,
                                    child: VehicleGarageCard(vehicle: vehicle),
                                  ),
                              ],
                            );
                          },
                        ),
                    ],
                  ),
                ),
        ),
      ],
    );
  }
}
