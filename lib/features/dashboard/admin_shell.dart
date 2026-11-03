import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/config/theme_controller.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';
import '../branding/branding_page.dart';
import '../notifications/notifications_page.dart';
import '../orders/orders_page.dart';
import '../registry/registry_page.dart';
import '../vehicles/automotive_catalog_page.dart';
import '../vehicles/vehicles_page.dart';
import 'overview_page.dart';

class AdminShell extends StatefulWidget {
  const AdminShell({super.key});
  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> {
  int selected = 0;
  bool collapsed = false;
  final scaffold = GlobalKey<ScaffoldState>();
  static const items = [
    ('Resumen', Icons.space_dashboard_outlined),
    ('Clientes', Icons.people_outline),
    ('Vehículos', Icons.directions_car_outlined),
    ('Mantenimientos', Icons.fact_check_outlined),
    ('Órdenes de trabajo', Icons.build_circle_outlined),
    ('Personalización', Icons.palette_outlined),
    ('Notificaciones', Icons.notifications_none_rounded),
    ('Catálogo automotriz', Icons.inventory_outlined),
  ];

  /// El mecánico trabaja dentro de estos destinos; el resto no aparece en su espacio.
  static bool visibleFor(WorkshopController state, int index) {
    if (state.isAdmin) return true;
    return const {0, 2, 4, 6, 7}.contains(index);
  }

  Widget sidebar(bool compact, {bool drawer = false}) {
    final config = context.watch<ThemeController>().config;
    final state = context.watch<WorkshopController>();
    final palette = context.atelier;
    // La barra lateral se pintaba con trece colores literales: con un tema
    // oscuro quedaba azul marino sobre fondo oscuro y con uno claro quedaba
    // una franja casi negra. Ahora sale del token `navigation` y de transparencias
    // sobre él, que funcionan en los cuatro temas.
    Color onNav(double opacity) =>
        palette.onNavigation.withValues(alpha: opacity);
    final navCard = Color.alphaBlend(
      Colors.white.withValues(alpha: .07),
      palette.navigation,
    );
    return Container(
      width: compact ? 84 : 252,
      color: palette.navigation,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(compact ? 20 : 24, 28, 20, 34),
              child: Row(
                children: [
                  BrandLogo(config: config, size: 42),
                  if (!compact) ...[
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            config.name,
                            style: const TextStyle(
                              fontSize: 21,
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            'WORKSHOP MANAGER',
                            style: TextStyle(
                              color: onNav(.45),
                              fontSize: 8,
                              letterSpacing: 1.6,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (!compact)
              Padding(
                padding: const EdgeInsets.fromLTRB(26, 0, 0, 14),
                child: Text(
                  'ESPACIO DE TRABAJO',
                  style: TextStyle(
                    color: onNav(.5),
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.5,
                  ),
                ),
              ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                children: [
                  for (var index = 0; index < items.length; index++)
                    if (visibleFor(state, index))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 7),
                        child: Tooltip(
                          message: compact ? items[index].$1 : '',
                          child: Material(
                            color: selected == index
                                ? config.color('primary')
                                : Colors.transparent,
                            borderRadius: BorderRadius.circular(11),
                            child: InkWell(
                              borderRadius: BorderRadius.circular(11),
                              onTap: () {
                                setState(() => selected = index);
                                if (drawer) Navigator.pop(context);
                              },
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 15,
                                ),
                                child: Row(
                                  children: [
                                    Icon(
                                      items[index].$2,
                                      color: selected == index
                                          ? Colors.white
                                          : onNav(.62),
                                      size: 21,
                                    ),
                                    if (!compact) ...[
                                      const SizedBox(width: 14),
                                      Expanded(
                                        child: Text(
                                          items[index].$1,
                                          style: TextStyle(
                                            fontWeight: selected == index
                                                ? FontWeight.w600
                                                : FontWeight.w400,
                                            fontSize: 13,
                                            color: selected == index
                                                ? Colors.white
                                                : onNav(.78),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                ],
              ),
            ),
            if (!compact)
              Padding(
                padding: const EdgeInsets.all(20),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: navCard,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.hub_outlined, color: palette.accent, size: 24),
                      const SizedBox(height: 12),
                      const Text(
                        'Tu taller, sincronizado',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        config.tagline,
                        style: TextStyle(
                          color: onNav(.6),
                          height: 1.5,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 22),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 18,
                    backgroundColor: onNav(.14),
                    child: Icon(
                      Icons.person_outline,
                      color: onNav(.8),
                      size: 20,
                    ),
                  ),
                  if (!compact) ...[
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            state.user?['username'] as String? ?? '',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 12,
                            ),
                          ),
                          Text(
                            state.isAdmin ? 'Administrador' : 'Mecánico',
                            style: TextStyle(color: onNav(.55), fontSize: 10),
                          ),
                        ],
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

  void _showExecutionModeDialog(BuildContext context) {
    final state = context.read<WorkshopController>();
    showDialog<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) {
          final isAuto = state.isAutonomous;
          return AlertDialog(
            title: Row(
              children: [
                Icon(
                  isAuto ? Icons.bolt_rounded : Icons.cloud_done_outlined,
                  color: isAuto
                      ? ctx.atelier.success
                      : Theme.of(ctx).colorScheme.primary,
                ),
                const SizedBox(width: 10),
                const Text('Modo de Ejecución', style: TextStyle(fontSize: 16)),
              ],
            ),
            content: SizedBox(
              width: 440,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    isAuto
                        ? 'Estás en Modo Autónomo: La aplicación corre al 100% en tu navegador con datos en memoria y persistencia local. No requiere ningún backend, Docker ni base de datos externa.'
                        : 'Estás en Modo Conectado: La aplicación se comunica mediante API REST con el servidor backend FastAPI / Docker.',
                    style: const TextStyle(fontSize: 13, height: 1.4),
                  ),
                  const SizedBox(height: 16),
                  SwitchListTile(
                    title: const Text(
                      'Modo Autónomo (Sin Docker/API)',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(
                      isAuto
                          ? 'Activo (100% autónomo y local)'
                          : 'Desactivado (conectando a ${state.api.baseUrl})',
                      style: const TextStyle(fontSize: 11),
                    ),
                    value: isAuto,
                    onChanged: (val) async {
                      await state.setAutonomousMode(val);
                      setDialogState(() {});
                    },
                  ),
                  if (isAuto) ...[
                    const Divider(height: 24),
                    ListTile(
                      leading: const Icon(Icons.restore_rounded),
                      title: const Text(
                        'Restablecer datos demo',
                        style: TextStyle(fontSize: 13),
                      ),
                      subtitle: const Text(
                        'Restaura las semillas iniciales de clientes, vehículos, órdenes y catálogo.',
                        style: TextStyle(fontSize: 11),
                      ),
                      onTap: () async {
                        await state.resetAutonomousData();
                        if (ctx.mounted) {
                          Navigator.pop(ctx);
                          showMessage(context, 'Datos demo restablecidos.');
                        }
                      },
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cerrar'),
              ),
            ],
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final palette = context.atelier;
    // Si el destino actual deja de estar autorizado, se vuelve a Resumen.
    if (!visibleFor(state, selected)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => selected = 0);
      });
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final mobile = constraints.maxWidth < 800;
        final compact = collapsed || constraints.maxWidth < 1180;
        return Scaffold(
          key: scaffold,
          drawer: mobile
              ? Drawer(width: 252, child: sidebar(false, drawer: true))
              : null,
          body: Row(
            children: [
              if (!mobile) sidebar(compact),
              Expanded(
                child: SafeArea(
                  child: Column(
                    children: [
                      Container(
                        height: 78,
                        padding: EdgeInsets.symmetric(
                          horizontal: mobile ? 14 : 30,
                        ),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.surface,
                          border: Border(
                            bottom: BorderSide(
                              color: Theme.of(context)
                                  .colorScheme
                                  .outlineVariant
                                  .withValues(alpha: .5),
                            ),
                          ),
                        ),
                        child: Row(
                          children: [
                            IconButton(
                              tooltip: 'Mostrar u ocultar menú',
                              onPressed: () {
                                if (mobile) {
                                  scaffold.currentState!.openDrawer();
                                } else {
                                  setState(() => collapsed = !collapsed);
                                }
                              },
                              icon: const Icon(Icons.menu_rounded, size: 21),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Mi taller  /  ${items[selected].$1}',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Theme.of(
                                    context,
                                  ).colorScheme.onSurfaceVariant,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            if (!mobile) ...[
                              Semantics(
                                label: state.isAutonomous
                                    ? 'Modo Autónomo (Sin Docker ni API)'
                                    : state.eventConnected
                                        ? 'Conectado en vivo'
                                        : 'Reconectando con el servidor',
                                child: InkWell(
                                  borderRadius: BorderRadius.circular(16),
                                  onTap: () => _showExecutionModeDialog(context),
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 5,
                                    ),
                                    decoration: BoxDecoration(
                                      color: state.isAutonomous
                                          ? palette.success.withValues(alpha: .12)
                                          : state.eventConnected
                                              ? palette.success.withValues(alpha: .12)
                                              : palette.warning.withValues(alpha: .12),
                                      borderRadius: BorderRadius.circular(16),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(
                                          state.isAutonomous
                                              ? Icons.bolt_rounded
                                              : Icons.circle,
                                          size: state.isAutonomous ? 13 : 7,
                                          color: state.isAutonomous
                                              ? palette.success
                                              : state.eventConnected
                                                  ? palette.success
                                                  : palette.warning,
                                        ),
                                        const SizedBox(width: 6),
                                        Text(
                                          state.isAutonomous
                                              ? 'Modo Autónomo'
                                              : state.eventConnected
                                                  ? 'En vivo'
                                                  : 'Reconectando',
                                          style: TextStyle(
                                            fontSize: 11,
                                            fontWeight: FontWeight.w600,
                                            color: state.isAutonomous
                                                ? palette.success
                                                : state.eventConnected
                                                    ? palette.success
                                                    : palette.warning,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 14),
                            ],
                            IconButton(
                              tooltip: 'Actualizar datos y diseño',
                              onPressed: state.loading
                                  ? null
                                  : () => runAction(
                                      context,
                                      () => state.refresh(configuration: true),
                                    ),
                              icon: const Icon(Icons.sync_rounded, size: 21),
                            ),
                            IconButton(
                              tooltip: 'Cerrar sesión',
                              onPressed: () => runAction(context, state.logout),
                              icon: const Icon(Icons.logout_rounded, size: 21),
                            ),
                          ],
                        ),
                      ),
                      SizedBox(
                        height: 2,
                        child: state.loading
                            ? const LinearProgressIndicator(minHeight: 2)
                            : null,
                      ),
                      if (state.error != null)
                        MaterialBanner(
                          content: Text(
                            state.error!,
                            style: const TextStyle(fontSize: 12),
                          ),
                          leading: const Icon(Icons.cloud_off_outlined),
                          actions: [
                            TextButton(
                              onPressed: () =>
                                  runAction(context, () => state.resume()),
                              child: const Text('Reintentar'),
                            ),
                          ],
                        ),
                      Expanded(
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 180),
                          child: Padding(
                            key: ValueKey(selected),
                            padding: EdgeInsets.all(mobile ? 18 : 32),
                            child: switch (selected) {
                              0 => OverviewPage(
                                onNavigate: (index) =>
                                    setState(() => selected = index),
                              ),
                              1 => const RegistryPage(
                                kind: RegistryKind.customers,
                              ),
                              2 => const VehiclesPage(),
                              3 => const RegistryPage(
                                kind: RegistryKind.catalogs,
                              ),
                              4 => const OrdersPage(),
                              5 => const BrandingPage(),
                              6 => const NotificationsPage(),
                              7 => const AutomotiveCatalogPage(),
                              _ => const NotificationsPage(),
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
