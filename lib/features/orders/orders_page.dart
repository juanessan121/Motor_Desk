import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';
import 'order_widgets.dart';
import 'reception_dialog.dart';

Future<void> createOrder(BuildContext context, {int? vehicleId}) async {
  final state = context.read<WorkshopController>();
  if (!state.isAdmin) {
    showMessage(
      context,
      'Abrir órdenes es una operación autorizada del administrador.',
      error: true,
    );
    return;
  }
  final id = await showDialog<int>(
    context: context,
    barrierDismissible: false,
    builder: (_) => ReceptionDialog(vehicleId: vehicleId),
  );
  if (context.mounted && id != null) await openOrder(context, id);
}

class OrdersPage extends StatefulWidget {
  const OrdersPage({super.key});
  @override
  State<OrdersPage> createState() => _OrdersPageState();
}

class _OrdersPageState extends State<OrdersPage> {
  String filter = 'all';
  String search = '';
  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final mechanic = state.isMechanic;
    final orders = state.orders
        .where(
          (row) =>
              (filter == 'all' ||
                  row.status == filter ||
                  row.json['operational_stage'] == filter) &&
              '${row.plate} ${row.title} ${row.customerName}'
                  .toLowerCase()
                  .contains(search),
        )
        .toList();
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PageHeading(
            title: mechanic ? 'Mis órdenes' : 'Órdenes de trabajo',
            subtitle: mechanic
                ? 'Solo las asignaciones vigentes autorizadas por el administrador.'
                : 'Del ingreso a la entrega, cada paso a la vista.',
            action: state.isAdmin
                ? FilledButton.icon(
                    onPressed: () => createOrder(context),
                    icon: const Icon(Icons.add_rounded, size: 20),
                    label: const Text('Nueva orden'),
                  )
                : null,
          ),
          const SizedBox(height: 26),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final entry in {
                'all': 'Todas',
                'in_progress': 'En taller',
                'pending_authorization': 'Por autorizar',
                'assigned': 'Asignadas',
                'waiting': 'En espera',
                'pending_review': 'Por revisar',
                'ready': 'Listas',
                'delivered': 'Entregadas',
                'cancelled': 'Canceladas',
              }.entries)
                ChoiceChip(
                  label: Text(entry.value),
                  selected: filter == entry.key,
                  onSelected: (_) => setState(() => filter = entry.key),
                ),
            ],
          ),
          const SizedBox(height: 20),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: TextField(
              decoration: InputDecoration(
                hintText: mechanic
                    ? 'Buscar placa o mantenimiento'
                    : 'Buscar placa, cliente o mantenimiento',
                prefixIcon: const Icon(Icons.search),
              ),
              onChanged: (value) =>
                  setState(() => search = value.toLowerCase().trim()),
            ),
          ),
          const SizedBox(height: 24),
          if (orders.isEmpty)
            Card(
              child: EmptyState(
                title: mechanic
                    ? 'No tienes órdenes asignadas'
                    : 'No hay órdenes en esta vista',
                message: mechanic
                    ? 'Cuando el administrador te asigne tareas aparecerán '
                          'aquí. No se muestran trabajos ajenos.'
                    : 'Abre una orden para comenzar el seguimiento.',
                icon: mechanic
                    ? Icons.engineering_outlined
                    : Icons.build_circle_outlined,
              ),
            )
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth > 1200
                    ? 3
                    : constraints.maxWidth > 720
                    ? 2
                    : 1;
                return Wrap(
                  spacing: 20,
                  runSpacing: 20,
                  children: [
                    for (final order in orders)
                      SizedBox(
                        width:
                            (constraints.maxWidth - (columns - 1) * 20) /
                            columns,
                        child: OrderCard(order: order),
                      ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}
