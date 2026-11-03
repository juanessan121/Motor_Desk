import 'dart:convert';

import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/models/entities.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/state/workshop_controller.dart';
import 'package:app_web_1/features/orders/order_widgets.dart';
import 'package:app_web_1/features/orders/reception_dialog.dart';
import 'package:app_web_1/features/registry/maintenance_editor.dart';
import 'package:app_web_1/features/vehicles/stock_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

Json template() => {
  'id': 3,
  'name': 'Preventivo de referencia',
  'description': 'Verificar manual del fabricante',
  'base_price': '30.00',
  'active': true,
  'revision': 2,
  'price_configured': true,
  'interval_km': 5000,
  'schedule_source': 'Referencia configurable',
  'applicability': <String, dynamic>{},
  'tasks': ['Revisar aceite', 'Revisar filtro'],
  'task_details': [
    {
      'label': 'Revisar aceite',
      'description': 'Según el fabricante',
      'required': true,
      'estimated_minutes': 10,
      'suggested_part_ids': <int>[],
    },
    {
      'label': 'Revisar filtro',
      'required': false,
      'suggested_part_ids': <int>[],
    },
  ],
};
Json vehicle() => {
  'id': 2,
  'owner_id': 1,
  'owner_name': 'Persona de prueba',
  'plate': 'TST1234',
  'brand': 'Marca de prueba',
  'model': 'Modelo',
  'year': 2022,
  'mileage': 10000,
  'active': true,
};
Json order() => {
  'id': 5,
  'vehicle_id': 2,
  'title': 'Preventivo de referencia',
  'plate': 'TST1234',
  'vehicle_name': 'Marca Modelo',
  'status': 'in_progress',
  'operational_stage': 'assigned',
  'base_approval': 'approved',
  'progress': 0.0,
  'revision': 1,
  'priority': 'normal',
  'created_at': '2026-10-22T10:00:00Z',
  'items': [
    {
      'id': 10,
      'label': 'Revisar aceite',
      'status': 'pending',
      'completed': false,
      'required': true,
      'revision': 1,
      'notes': '',
      'responsible_ids': [4],
      'suggested_part_ids': <int>[],
    },
  ],
  'templates': [
    {'id': 3, 'name': 'Preventivo de referencia', 'revision': 2},
  ],
  'quotes': <dynamic>[],
  'photos': <dynamic>[],
  'capabilities': {
    'manage': false,
    'assign': false,
    'inspect': true,
    'upload': true,
    'quote': false,
  },
};
http.Response reply(Object value, [int status = 200]) => http.Response(
  jsonEncode(value),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

Future<WorkshopController> mount(
  WidgetTester tester,
  Widget child, {
  Size size = const Size(1440, 1000),
  String role = 'admin',
  Future<http.Response?> Function(http.Request)? respond,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final api = ApiClient(
    baseUrl: 'http://api.test/api/v1',
    client: MockClient((request) async {
      final custom = await respond?.call(request);
      if (custom != null) return custom;
      final path = request.url.path;
      if (path.endsWith('/maintenance-suggestions')) {
        return reply({
          'items': [template()],
        });
      }
      if (path.endsWith('/staff/mechanics')) {
        return reply([
          {'id': 4, 'username': 'Técnico asignable'},
        ]);
      }
      if (path.endsWith('/catalogs')) return reply([template()]);
      if (path.endsWith('/vehicles')) return reply([vehicle()]);
      if (path.endsWith('/dashboard')) return reply(<String, dynamic>{});
      if (path.endsWith('/orders')) return reply([order()]);
      return reply(<dynamic>[]);
    }),
  );
  final theme = ThemeController(api);
  final state = WorkshopController(api, theme)
    ..user = {'id': 4, 'role': role, 'must_change_password': false}
    ..vehicles = [Vehicle(vehicle())]
    ..catalogs = [MaintenanceCatalog(template())]
    ..orders = [WorkOrder(order())];
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
        home: Scaffold(body: child),
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

void main() {
  for (final size in [const Size(390, 844), const Size(1440, 1000)]) {
    testWidgets(
      'Recepción progresiva reutiliza vehículo y servicios en $size',
      (tester) async {
        await mount(tester, const ReceptionDialog(), size: size);
        await tester.enterText(
          find.widgetWithText(
            TextField,
            'Buscar placa, vehículo o propietario',
          ),
          'Persona de prueba',
        );
        await tester.pumpAndSettle();
        expect(find.text('TST1234 · Marca de prueba Modelo'), findsOneWidget);
        await tester.tap(find.text('TST1234 · Marca de prueba Modelo'));
        await tester.pumpAndSettle();
        expect(
          find.textContaining('Último registro: 10000 km'),
          findsOneWidget,
        );
        expect(find.text('Preventivo de referencia'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
    testWidgets('Editor de plantilla y stock vacío adaptables en $size', (
      tester,
    ) async {
      await mount(
        tester,
        MaintenanceTemplateEditor(catalog: MaintenanceCatalog(template())),
        size: size,
      );
      expect(find.text('Editar plantilla · versión 2'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await mount(tester, const StockPage(), size: size);
      expect(find.text('Sin existencias registradas'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets(
      'Mecánico completa desde su checklist sin formulario en $size',
      (tester) async {
        var current = order();
        Json? sent;
        await mount(
          tester,
          const OrderDetail(orderId: 5),
          size: size,
          role: 'mechanic',
          respond: (request) async {
            if (request.method == 'PATCH') {
              sent = jsonDecode(request.body) as Json;
              current = {
                ...current,
                'progress': 1.0,
                'operational_stage': 'pending_review',
                'items': [
                  {
                    ...jsonList(current['items']).first,
                    'status': 'completed',
                    'completed': true,
                    'revision': 2,
                  },
                ],
              };
              return reply(current);
            }
            if (request.url.path.endsWith('/orders')) return reply([current]);
            return null;
          },
        );
        await tester.ensureVisible(find.text('Completar'));
        await tester.tap(find.text('Completar'));
        await tester.pumpAndSettle();
        expect(sent?['status'], 'completed');
        expect(sent?['expected_revision'], 1);
        expect(find.text('Completada'), findsOneWidget);
        expect(find.text('Checklist · 100%'), findsOneWidget);
        expect(find.text('Registrar entrega'), findsNothing);
        expect(find.text('Revisar y dejar lista para entrega'), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets('Recepción confirma una sola vez con clave de reintento', (
    tester,
  ) async {
    Json? sent;
    var writes = 0;
    await mount(
      tester,
      const ReceptionDialog(vehicleId: 2),
      respond: (request) async {
        if (request.method == 'POST' && request.url.path.endsWith('/orders')) {
          writes++;
          sent = jsonDecode(request.body) as Json;
          return reply(order(), 201);
        }
        return null;
      },
    );
    await tester.tap(find.text('Preventivo de referencia'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirmar orden'));
    await tester.pumpAndSettle();
    expect(writes, 1);
    expect(sent?['vehicle_id'], 2);
    expect(sent?['catalog_ids'], [3]);
    expect(sent?['mileage'], 10000);
    expect(sent?['customer_id'], isNull);
    expect(sent?['request_key'], matches(RegExp(r'^[0-9a-f-]{36}$')));
  });

  testWidgets(
    'Sin autorización se puede observar pero no comenzar ni completar',
    (tester) async {
      final state = await mount(
        tester,
        const OrderDetail(orderId: 5),
        role: 'mechanic',
      );
      state.orders = [
        WorkOrder({...order(), 'base_approval': 'pending'}),
      ];
      state.notifyListeners();
      await tester.pumpAndSettle();
      final button = tester.widget<TextButton>(
        find.widgetWithText(TextButton, 'Completar'),
      );
      expect(button.onPressed, isNull);
      expect(
        find.textContaining('Pendiente de aceptación del cliente'),
        findsOneWidget,
      );
      expect(find.text('Observación'), findsOneWidget);
    },
  );
}
