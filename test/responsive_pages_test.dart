import 'package:app_web_1/core/config/app_config_model.dart';
import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/models/entities.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/state/workshop_controller.dart';
import 'package:app_web_1/features/branding/branding_page.dart';
import 'package:app_web_1/features/customer/customer_home.dart';
import 'package:app_web_1/features/dashboard/admin_shell.dart';
import 'package:app_web_1/features/dashboard/overview_page.dart';
import 'package:app_web_1/features/notifications/notifications_page.dart';
import 'package:app_web_1/features/orders/order_widgets.dart';
import 'package:app_web_1/features/orders/orders_page.dart';
import 'package:app_web_1/features/registry/registry_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

void main() {
  Future<WorkshopController> mount(
    WidgetTester tester,
    Widget page,
    Size size, {
    bool customer = false,
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = ApiClient(
      client: MockClient((request) async {
        if (request.url.path.endsWith('/notification-settings')) {
          return http.Response('{}', 200);
        }
        return http.Response('[]', 200);
      }),
    );
    final theme = ThemeController(api);
    final state = WorkshopController(api, theme)
      ..user = {
        'id': 1,
        'username': 'pruebas',
        'role': customer ? 'customer' : 'admin',
        'must_change_password': false,
      };
    state.orders = [
      WorkOrder({
        'id': 1,
        'vehicle_id': 1,
        'customer_id': 1,
        'plate': 'ABC-123',
        'title': 'Mantenimiento 50.000 km',
        'customer_name': 'Cliente de prueba',
        'vehicle_name': 'Toyota Corolla',
        'status': 'in_progress',
        'progress': .5,
        'base_total': '100.00',
        'total': '100.00',
        'notes': '',
        'created_at': '2026-10-18T12:00:00Z',
        'items': [
          {'id': 1, 'label': 'Aceite', 'completed': true},
          {'id': 2, 'label': 'Filtros', 'completed': false},
        ],
        'quotes': [],
        'photos': [],
      }),
    ];
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: theme),
          ChangeNotifierProvider.value(value: state),
        ],
        child: MaterialApp(
          theme: theme.theme,
          locale: const Locale('es'),
          supportedLocales: const [Locale('es')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: Scaffold(
            body: Padding(padding: const EdgeInsets.all(16), child: page),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    addTearDown(() {
      state.dispose();
      theme.dispose();
    });
    return state;
  }

  for (final size in [const Size(390, 844), const Size(1440, 1000)]) {
    for (final kind in RegistryKind.values) {
      testWidgets('Tabla $kind en $size', (tester) async {
        await mount(tester, RegistryPage(kind: kind), size);
        expect(tester.takeException(), isNull);
      });
    }
    testWidgets('Dashboard en $size', (tester) async {
      await mount(tester, OverviewPage(onNavigate: (_) {}), size);
      expect(find.text('Todo bajo control'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets('Órdenes y detalle en $size', (tester) async {
      await mount(tester, const OrdersPage(), size);
      await tester.tap(find.text('ABC-123'));
      await tester.pumpAndSettle();
      expect(find.byType(OrderDetail), findsOneWidget);
      expect(find.text('Aceite'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets('Editor de marca en $size', (tester) async {
      await mount(tester, const BrandingPage(), size);
      expect(find.text('Tu marca. Tu experiencia.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets('Notificaciones en $size', (tester) async {
      await mount(tester, const NotificationsPage(), size);
      expect(find.text('Centro de notificaciones'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets('Espacio de cliente en $size', (tester) async {
      await mount(tester, const CustomerHome(), size, customer: true);
      expect(find.text('ABC-123'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets('Shell administrativo en $size', (tester) async {
      await mount(tester, const AdminShell(), size);
      expect(find.text('Todo bajo control'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('JSON remoto oculta módulos del cliente reactivamente', (
    tester,
  ) async {
    final state = await mount(
      tester,
      const CustomerHome(),
      const Size(390, 844),
      customer: true,
    );
    expect(find.text('Mis vehículos'), findsOneWidget);
    final payload = state.theme.config.toJson();
    payload['features'] = {
      'vehicles': false,
      'maintenance': false,
      'quotes': false,
      'photos': false,
      'history': false,
    };
    state.theme.config = AppConfigModel.fromJson(payload);
    state.theme.notifyListeners();
    await tester.pumpAndSettle();
    expect(find.text('Mis vehículos'), findsNothing);
    expect(find.text('Mis servicios'), findsNothing);
    expect(find.text('Actividad'), findsOneWidget);
  });
}
