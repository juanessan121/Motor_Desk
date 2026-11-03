import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:intl/intl.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/config/theme_controller.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';
import '../orders/order_widgets.dart';
import '../orders/orders_page.dart';
import '../orders/order_execution_widgets.dart';
import '../registry/customer_flow.dart';

class OverviewPage extends StatelessWidget {
  const OverviewPage({super.key, required this.onNavigate});
  final ValueChanged<int> onNavigate;
  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final palette = context.atelier;
    final mechanic = state.isMechanic;
    // El servidor decide qué métricas existen: un mecánico nunca recibe cifras del taller.
    // Los colores salen de los tokens del tema. Con literales, estas cuatro
    // tarjetas quedaban igual en los cuatro temas y era el único bloque del
    // resumen que norespondía al tema elegido.
    final metrics = mechanic
        ? [
            (
              'Mis órdenes',
              '${state.summary['assigned_orders'] ?? 0}',
              Icons.assignment_outlined,
              palette.accent,
              'Asignaciones vigentes',
              4,
            ),
            (
              'Trabajos pendientes',
              '${state.summary['pending_tasks'] ?? 0}',
              Icons.pending_actions_outlined,
              palette.warning,
              'Tareas sin completar',
              4,
            ),
            (
              'Tareas completadas',
              '${state.summary['completed_tasks'] ?? 0}',
              Icons.task_alt_rounded,
              palette.success,
              'Trabajo documentado por ti',
              4,
            ),
            (
              'En progreso',
              '${state.summary['in_progress'] ?? 0}',
              Icons.build_outlined,
              palette.complementary,
              'Órdenes abiertas asignadas',
              4,
            ),
          ]
        : [
            (
              'Clientes activos',
              '${state.summary['customers'] ?? 0}',
              Icons.people_outline,
              palette.accent,
              'Personas que confían en tu taller',
              1,
            ),
            (
              'En mantenimiento',
              '${state.summary['in_progress'] ?? 0}',
              Icons.build_outlined,
              palette.complementary,
              'Órdenes de trabajo en curso',
              4,
            ),
            (
              'Listos para retirar',
              '${state.summary['ready'] ?? 0}',
              Icons.task_alt_rounded,
              palette.success,
              'Todos los trabajos completados',
              4,
            ),
            (
              'Total entregado',
              money(state.summary['delivered_total'] ?? 0),
              Icons.payments_outlined,
              palette.warning,
              'Valor de las órdenes entregadas',
              4,
            ),
          ];
    final recent = state.orders
        .where((order) => !order.closed)
        .take(5)
        .toList();
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PageHeading(
            title: mechanic ? 'Mi jornada' : 'Todo bajo control',
            subtitle: mechanic
                ? 'Tus trabajos asignados, sin datos de otros talleres ni clientes.'
                : 'Una vista clara de lo que está pasando en tu taller.',
            action: state.isAdmin
                ? AtelierAction(
                    label: 'Nueva orden',
                    icon: Icons.add_rounded,
                    onPressed: () => createOrder(context),
                  )
                : null,
          ),
          const SizedBox(height: 22),
          _CommandBanner(mechanic: mechanic),
          const SizedBox(height: 22),
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth > 1080
                  ? 4
                  : constraints.maxWidth > 570
                  ? 2
                  : 1;
              return Wrap(
                spacing: 18,
                runSpacing: 18,
                children: [
                  for (final metric in metrics)
                    SizedBox(
                      width:
                          (constraints.maxWidth - 18 * (columns - 1)) / columns,
                      child: Card(
                        child: InkWell(
                          borderRadius: BorderRadius.circular(18),
                          // La flecha del concepto no era decorativa: cada
                          // cifra lleva a su destino. Una tarjeta que no lleva
                          // a ninguna parte es solo un número grande.
                          onTap: () => onNavigate(metric.$6),
                          child: Padding(
                            padding: const EdgeInsets.all(23),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.all(10),
                                      decoration: BoxDecoration(
                                        color: metric.$4.withValues(alpha: .09),
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Icon(
                                        metric.$3,
                                        color: metric.$4,
                                        size: 22,
                                      ),
                                    ),
                                    const Spacer(),
                                    Icon(
                                      Icons.north_east,
                                      size: 17,
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.outline,
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 22),
                                Text(
                                  metric.$2,
                                  style: const TextStyle(
                                    fontSize: 31,
                                    fontWeight: FontWeight.w800,
                                    letterSpacing: -1,
                                  ),
                                ),
                                const SizedBox(height: 7),
                                Text(
                                  metric.$1,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 13,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  metric.$5,
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: Theme.of(
                                      context,
                                    ).colorScheme.onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: 28),
          if (state.isAdmin) ...[
            SectionCard(
              title: 'Mesa operativa · excepciones y siguientes pasos',
              subtitle:
                  'Abre una orden para asignar, resolver solicitudes, revisar ejecución o registrar entrega.',
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final stage in [
                    'received',
                    'pending_authorization',
                    'waiting',
                    'pending_review',
                    'ready',
                  ])
                    ActionChip(
                      label: Text(
                        '${operationStageLabels[stage]}: ${state.orders.where((order) => order.json['operational_stage'] == stage).length}',
                      ),
                      onPressed: () {
                        final order = state.orders
                            .where(
                              (order) =>
                                  order.json['operational_stage'] == stage,
                            )
                            .firstOrNull;
                        if (order != null) {
                          openOrder(context, order.id);
                        } else {
                          onNavigate(4);
                        }
                      },
                    ),
                  Text(
                    'Repuestos pendientes: ${state.summary['pending_parts'] ?? 0} · Actividades en atención: ${state.summary['attention_tasks'] ?? 0}',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 22),
          ],
          LayoutBuilder(
            builder: (context, constraints) {
              final activity = SectionCard(
                title: mechanic ? 'Mis trabajos' : 'Actividad del taller',
                trailing: TextButton(
                  onPressed: () => onNavigate(4),
                  child: const Text('Ver todas →'),
                ),
                child: recent.isEmpty
                    ? EmptyState(
                        title: mechanic
                            ? 'Sin trabajos asignados'
                            : 'Tu próxima orden empieza aquí',
                        message: mechanic
                            ? 'El administrador debe asignarte tareas de una '
                                  'orden. No se muestran trabajos ajenos.'
                            : 'Registra un cliente, su vehículo y asigna un '
                                  'mantenimiento.',
                        icon: mechanic
                            ? Icons.engineering_outlined
                            : Icons.car_repair_outlined,
                      )
                    : Column(
                        children: [
                          for (final order in recent)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 14),
                              child: OrderSummaryTile(
                                order: order,
                                onTap: () => openOrder(context, order.id),
                              ),
                            ),
                        ],
                      ),
              );
              final quick = SectionCard(
                title: mechanic ? 'Mi espacio' : 'Accesos rápidos',
                child: Column(
                  children: [
                    if (state.isAdmin)
                      _QuickAction(
                        icon: Icons.person_add_alt_1_outlined,
                        title: 'Registrar cliente',
                        subtitle: 'Crea su cuenta automáticamente',
                        onTap: state.isAdmin
                            ? () => startCustomerFlow(context)
                            : null,
                      ),
                    const SizedBox(height: 12),
                    if (state.isAdmin)
                      _QuickAction(
                        icon: Icons.directions_car_outlined,
                        title: 'Ingresar vehículo',
                        subtitle: 'Asócialo a su propietario',
                        onTap: state.isAdmin
                            ? () => startVehicleFlow(context)
                            : null,
                      ),
                    const SizedBox(height: 12),
                    if (state.isAdmin)
                      _QuickAction(
                        icon: Icons.palette_outlined,
                        title: 'Personalizar la app',
                        subtitle: 'Tu marca, sin recompilar',
                        onTap: state.isAdmin ? () => onNavigate(5) : null,
                      ),
                    if (!mechanic) ...[
                      const SizedBox(height: 24),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(18),
                        decoration: BoxDecoration(
                          color: Theme.of(
                            context,
                          ).colorScheme.primary.withValues(alpha: .06),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'APROBACIONES PENDIENTES',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                letterSpacing: .7,
                              ),
                            ),
                            const SizedBox(height: 9),
                            Text(
                              '${state.summary['pending_quotes'] ?? 0} cotizaciones',
                              style: const TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 7),
                            const Text(
                              'El cliente decide. Tu equipo recibe la actualización.',
                              style: TextStyle(fontSize: 12, height: 1.6),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              );
              if (constraints.maxWidth < 940) {
                return Column(
                  children: [activity, const SizedBox(height: 22), quick],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 7, child: activity),
                  const SizedBox(width: 24),
                  Expanded(flex: 4, child: quick),
                ],
              );
            },
          ),
          const SizedBox(height: 24),
          Text(
            mechanic
                ? 'Solo se muestran trabajos asignados. Los clientes, el '
                      'facturación no forma parte de tu espacio. Puedes consultar el catálogo técnico.'
                : 'Los importes corresponden a órdenes de servicio; no '
                      'sustituyen una factura fiscal.',
            style: TextStyle(
              fontSize: 11,
              color: context.atelier.secondaryText,
            ),
          ),
        ],
      ),
    );
  }
}

/// Banner del Command Center.
///
/// La fecha es la de hoy, calculada en el dispositivo. El concepto la muestra
/// junto al título; es la única señal de que estos datos son de ahora, y sin
/// ella un número puede ser de hace una hora sin que nadie lo note.
class _CommandBanner extends StatelessWidget {
  const _CommandBanner({required this.mechanic});
  final bool mechanic;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final config = context.watch<ThemeController>().config;
    final palette = context.atelier;
    final hoy = DateFormat(
      'EEEE d \'de\' MMMM \'de\' y',
      'es',
    ).format(DateTime.now());
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 26),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        gradient: LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [palette.navigation, palette.diagnostic],
        ),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) => Row(
          children: [
            Expanded(
              flex: 6,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    mechanic
                        ? 'Tu jornada, en marcha'
                        : 'Tu taller, en movimiento',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 25,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -.6,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Text(
                    'Hoy · ${_mayuscula(hoy)}',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: .6),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            if (constraints.maxWidth >= 620) ...[
              const SizedBox(width: 28),
              Expanded(
                flex: 4,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      config.tagline.isEmpty
                          ? 'Cada servicio deja un registro.'
                          : config.tagline,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: .82),
                        fontSize: 14,
                        height: 1.55,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Container(
                          width: 7,
                          height: 7,
                          decoration: BoxDecoration(
                            color: state.eventConnected
                                ? palette.success
                                : palette.warning,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          state.eventConnected
                              ? 'Datos en vivo'
                              : 'Reconectando con el taller',
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: .6),
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// «lunes» no es un encabezado: en español los días y los meses empiezan en
  /// minúscula salvo que estén al principio de la frase.
  static String _mayuscula(String value) =>
      value.isEmpty ? value : value[0].toUpperCase() + value.substring(1);
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => ListTile(
    enabled: onTap != null,
    contentPadding: EdgeInsets.zero,
    leading: Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(icon, size: 22),
    ),
    title: Text(
      title,
      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
    ),
    subtitle: Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(subtitle, style: const TextStyle(fontSize: 11)),
    ),
    trailing: const Icon(Icons.chevron_right, size: 18),
    onTap: onTap,
  );
}
