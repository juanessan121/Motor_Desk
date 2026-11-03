import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/config/regional_format.dart';
import '../../core/config/theme_controller.dart';
import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/make_logo_cache.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';
import '../orders/order_widgets.dart';
import '../vehicles/inspection_editor.dart';
import '../vehicles/vehicle_passport.dart';

/// Mis servicios, Mis vehículos y Actividad reutilizan la misma sesión y API.
/// Las listas se construyen a demanda; cargar otra página requiere una acción.
class CustomerHome extends StatefulWidget {
  const CustomerHome({super.key});
  @override
  State<CustomerHome> createState() => _CustomerHomeState();
}

class _CustomerHomeState extends State<CustomerHome> {
  String selected = 'maintenance';

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final config = context.watch<ThemeController>().config;
    final scheme = Theme.of(context).colorScheme;
    final format = RegionalFormat(config.regional);
    final tabs = [
      if (config.enabled('maintenance')) ('maintenance', 'Mis servicios', Icons.build_outlined),
      if (config.enabled('vehicles')) ('vehicles', 'Mis vehículos', Icons.directions_car_outlined),
      ('notifications', 'Actividad', Icons.notifications_none_rounded),
    ];
    final current = tabs.any((tab) => tab.$1 == selected) ? selected : tabs.first.$1;
    final index = tabs.indexWhere((tab) => tab.$1 == current);
    final resource = current == 'maintenance' ? 'orders' : current;
    final count = switch (current) {
      'maintenance' => state.orders.length,
      'vehicles' => state.vehicles.length,
      _ => state.notifications.length,
    };
    final horizontal = math.max(16.0, (MediaQuery.sizeOf(context).width - 820) / 2);
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    return Scaffold(
      bottomNavigationBar: tabs.length < 2 ? null : NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => selected = tabs[value].$1),
        destinations: [for (final tab in tabs) NavigationDestination(icon: Icon(tab.$3), label: tab.$2)],
      ),
      body: RefreshIndicator(
        onRefresh: () => runAction(context, () => state.refresh(configuration: true)),
        child: CustomScrollView(
          key: PageStorageKey(current),
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverAppBar(
              pinned: true,
              expandedHeight: math.max(205, 150 + textScale * 65),
              backgroundColor: scheme.primary,
              foregroundColor: scheme.onPrimary,
              title: Row(children: [
                BrandLogo(config: config, size: 32),
                const SizedBox(width: 10),
                Expanded(child: Text(config.name, overflow: TextOverflow.ellipsis)),
              ]),
              actions: [
                IconButton(tooltip: 'Actualizar', onPressed: state.loading ? null :
                    () => runAction(context, () => state.refresh(configuration: true)), icon: const Icon(Icons.refresh)),
                IconButton(tooltip: 'Cerrar sesión', onPressed: () => runAction(context, state.logout), icon: const Icon(Icons.logout_rounded)),
              ],
              flexibleSpace: FlexibleSpaceBar(
                background: DecoratedBox(
                  decoration: BoxDecoration(gradient: LinearGradient(
                    begin: Alignment.topLeft, end: Alignment.bottomRight,
                    colors: [scheme.primary, Color.lerp(scheme.primary, context.atelier.navigation, .3)!],
                  )),
                  child: SafeArea(bottom: false, child: Padding(
                    padding: EdgeInsets.fromLTRB(horizontal + 6, 70, horizontal + 6, 18),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.end, children: [
                      Text(config.welcome, maxLines: 2, overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: scheme.onPrimary, fontSize: 26, fontWeight: FontWeight.w800)),
                      const SizedBox(height: 8),
                      Text(config.tagline, maxLines: 2, overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: scheme.onPrimary.withValues(alpha: .8))),
                    ]),
                  )),
                ),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(horizontal, 22, horizontal, 16),
              sliver: SliverToBoxAdapter(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(tabs[index].$2, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                Text(state.lastLoadedAt == null ? 'Desliza para actualizar' : 'Actualizado: ${format.dateTime(state.lastLoadedAt)}'),
                Semantics(liveRegion: true, child: Text(state.eventConnected ? 'Actualizaciones en vivo' : 'Sin conexión en vivo · Puedes actualizar manualmente',
                    style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 12))),
                if (state.loading) const Padding(padding: EdgeInsets.only(top: 12), child: LinearProgressIndicator()),
                if (state.error != null) ...[
                  const SizedBox(height: 12),
                  Text(state.error!, style: TextStyle(color: scheme.error)),
                  TextButton.icon(onPressed: () => runAction(context, () => state.refresh(configuration: true)),
                    icon: const Icon(Icons.refresh), label: const Text('Reintentar conexión')),
                ],
              ])),
            ),
            if (!state.loading && count == 0)
              SliverPadding(padding: EdgeInsets.symmetric(horizontal: horizontal), sliver: SliverToBoxAdapter(child: Card(
                child: EmptyState(
                  title: current == 'maintenance' ? 'Aún no hay servicios' : current == 'vehicles' ? 'Aún no hay vehículos' : 'Todo al día',
                  message: current == 'maintenance' ? 'Cuando tu vehículo ingrese al taller podrás seguir aquí los trabajos autorizados.' :
                    current == 'vehicles' ? 'El taller asociará tus vehículos a esta cuenta.' : 'Aquí aparecerán las novedades que el taller publique para ti.',
                ),
              ))),
            SliverPadding(
              padding: EdgeInsets.symmetric(horizontal: horizontal),
              sliver: SliverList.separated(
                itemCount: count,
                separatorBuilder: (_, _) => const SizedBox(height: 16),
                itemBuilder: (context, row) => switch (current) {
                  'maintenance' => OrderCard(order: state.orders[row]),
                  'vehicles' => _CustomerVehicleCard(vehicle: state.vehicles[row]),
                  _ => _CustomerActivity(event: state.notifications[row]),
                },
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(horizontal, 18, horizontal, 28),
              sliver: SliverToBoxAdapter(child: Column(children: [
                if (state.customerPageError(resource) != null)
                  Text(state.customerPageError(resource)!, style: TextStyle(color: scheme.error)),
                if (state.customerHasMore(resource))
                  AtelierAction(label: 'Cargar más', family: AtelierButton.secondary,
                    icon: Icons.expand_more, loading: state.customerLoadingMore(resource),
                    onPressed: state.loading ? null : () => state.loadMoreCustomer(resource)),
                const SizedBox(height: 18),
                Text(format.timezoneLabel, style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 11)),
                Text(config.tagline, textAlign: TextAlign.center, style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 11)),
              ])),
            ),
          ],
        ),
      ),
    );
  }
}

class _CustomerVehicleCard extends StatelessWidget {
  const _CustomerVehicleCard({required this.vehicle});
  final Vehicle vehicle;
  @override
  Widget build(BuildContext context) {
    final config = context.watch<ThemeController>().config;
    final catalog = vehicle.json['catalog'] as Json?;
    return Card(child: Padding(padding: const EdgeInsets.all(20), child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          MakeLogo(make: vehicle.json['brand'] as String?, logoUrl: catalog?['logo_url'] as String?, loadCatalog: false),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(vehicle.plate, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800)),
            Text(vehicle.name),
          ])),
        ]),
        const SizedBox(height: 14),
        Text('${vehicle.json['year']} · ${RegionalFormat(config.regional).distance(vehicle.json['mileage'])} registrados'),
        const SizedBox(height: 14),
        AtelierAction(label: 'Ver pasaporte digital', family: AtelierButton.secondary,
          icon: Icons.badge_outlined, onPressed: () => openPassport(context, vehicle.id)),
      ],
    )));
  }
}

class _CustomerActivity extends StatelessWidget {
  const _CustomerActivity({required this.event});
  final Json event;
  @override
  Widget build(BuildContext context) {
    final flags = context.watch<ThemeController>().config;
    final inspection = event['kind'] == 'inspection_published' && event['inspection_id'] != null && flags.enabled('history');
    VoidCallback? open;
    if (inspection) {
      open = () => openInspectionEditor(context, inspectionId: event['inspection_id'] as int);
    } else if (flags.enabled('maintenance') && event['order_id'] != null) {
      open = () => openOrder(context, event['order_id'] as int);
    }
    return Card(child: InkWell(onTap: open, borderRadius: BorderRadius.circular(18),
      child: Padding(padding: const EdgeInsets.all(20), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(inspection ? Icons.fact_check_outlined : Icons.notifications_outlined, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 12),
            Expanded(child: Text(event['title'] as String, style: const TextStyle(fontWeight: FontWeight.w700))),
            if (open != null) const Icon(Icons.chevron_right),
          ]),
          const SizedBox(height: 12),
          Text(event['body'] as String, style: const TextStyle(height: 1.5)),
          const SizedBox(height: 12),
          Text(RegionalFormat(flags.regional).dateTime(event['created_at']), style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ],
      )),
    ));
  }
}
