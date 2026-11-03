import 'dart:convert';

import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/state/workshop_controller.dart';
import 'package:app_web_1/features/dashboard/admin_shell.dart';
import 'package:app_web_1/features/vehicles/automotive_catalog_page.dart';
import 'package:app_web_1/features/vehicles/catalog_parts_page.dart';
import 'package:app_web_1/features/vehicles/workshop_layout_page.dart';
import 'package:app_web_1/features/vehicles/workshop_map.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

http.Response reply(Object body, [int status = 200]) => http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json; charset=utf-8'});

Future<void> mount(WidgetTester tester, Widget child, Future<http.Response> Function(http.Request) handler,
    {Size size = const Size(1440, 1100), String role = 'admin'}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final api = ApiClient(baseUrl: 'http://api.test/api/v1', client: MockClient(handler));
  final theme = ThemeController(api);
  final state = WorkshopController(api, theme)..user = {'id': 1, 'role': role, 'username': 'usuario-prueba', 'must_change_password': false};
  await tester.pumpWidget(MultiProvider(providers: [ChangeNotifierProvider.value(value: theme), ChangeNotifierProvider.value(value: state)],
    child: MaterialApp(theme: theme.theme, locale: const Locale('es'), supportedLocales: const [Locale('es')], localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Scaffold(body: Padding(padding: const EdgeInsets.all(16), child: child)))));
  await tester.pumpAndSettle();
  addTearDown(() { state.dispose(); theme.dispose(); });
}

Json emptyPlan() => {'revision': 1, 'configured': false, 'name': 'Taller aislado', 'zones': <dynamic>[], 'bays': <dynamic>[], 'orders': <dynamic>[]};
Json savedPlan({bool occupied = false}) => {
  'revision': 2, 'configured': true, 'name': 'Taller aislado',
  'zones': [{'id': 1, 'name': 'Zona real de prueba', 'kind': 'service', 'capacity': 6, 'x': 0, 'y': 0, 'width': 1, 'height': 1, 'revision': 1, 'active': true}],
  'bays': [for (var index = 0; index < 2; index++) {
    'id': index + 1, 'zone_id': 1, 'name': 'B0${index + 1}', 'kind': 'mechanical', 'capacity': 1,
    'x': .1 + index * .45, 'y': .2, 'width': .3, 'height': .4, 'revision': 1, 'active': true,
    'occupancies': occupied && index == 0 ? [{'id': 501, 'order_id': 11, 'plate': 'TST1234', 'title': 'Servicio de prueba', 'status': 'in_progress', 'mechanics': [{'id': 4, 'username': 'Técnico asignado'}]}] : <dynamic>[],
  }],
  'orders': occupied ? [{'id': 11, 'plate': 'TST1234', 'title': 'Servicio de prueba', 'status': 'in_progress', 'occupancy_id': 501,
    'mechanics': [{'id': 4, 'username': 'Técnico asignado'}]}] : <dynamic>[],
};

Json part() => {'id': 10, 'sku': 'REF-10', 'title': 'Brake pad', 'name_es': 'Pastillas de freno', 'system': 'frenos', 'origin': 'imported', 'source_key': 'part_terms', 'compatibilities_count': 0};

Future<http.Response> catalog(http.Request request) async {
  final path = request.url.path;
  if (path.endsWith('/overview')) return reply({'counts': {'make': 165, 'model': 2645, 'generation': 6790, 'engine': 30535, 'part': 1802}, 'sources': <dynamic>[]});
  if (path.endsWith('/parts/filters')) return reply({'systems': ['frenos'], 'sources': ['part_terms'], 'manufacturers': ['Proveedor'], 'categories': ['Frenos']});
  if (path.endsWith('/parts')) return reply({'items': [part()], 'total': 21, 'available': 1802, 'mode': 'text', 'empty_reason': null});
  if (path.endsWith('/browse')) {
    final entity = request.url.queryParameters['entity'];
    return reply({'items': [{'id': 2, 'name': entity == 'make' ? 'Toyota' : 'Corolla', 'origin': 'imported', 'source_key': 'vehicles'}], 'total': 1, 'available': 1});
  }
  if (path.contains('/records/')) return reply({'record': part(), 'source': {'title': 'lifeofcapo/car-api', 'url': 'https://github.com/lifeofcapo/car-api', 'license_url': 'https://example.test/MIT', 'license': 'MIT', 'attribution': 'lifeofcapo/car-api — MIT'}, 'parents': <dynamic>[], 'details': <dynamic>[], 'details_total': 0, 'notice': 'Información de referencia, no inventario.'});
  return reply(<dynamic>[]);
}

void main() {
  test('Estados operativos se derivan de datos, no del SVG', () {
    expect(workshopBayState({'active': false, 'occupancies': []}), BayState.unavailable);
    expect(workshopBayState({'active': true, 'occupancies': []}), BayState.available);
    expect(workshopBayState({'active': true, 'occupancies': [{'status': 'ready'}]}), BayState.ready);
    expect(workshopBayState({'active': true, 'occupancies': [{'status': 'in_progress'}]}), BayState.maintenance);
    expect(workshopBayState({'active': true, 'occupancies': [{'status': 'in_progress', 'attention_required': true}]}), BayState.attention);
  });

  for (final size in [const Size(390, 844), const Size(1440, 1100)]) {
    testWidgets('Plano vacío muestra SVG y configuración en $size', (tester) async {
      await mount(tester, const WorkshopMapPage(), (_) async => reply(emptyPlan()), size: size);
      expect(find.text('No hay plano configurado'), findsOneWidget);
      expect(find.byType(SvgPicture), findsOneWidget);
      expect(find.text('Configurar zonas y bahías'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets('Plano guardado renderiza puestos SVG en $size', (tester) async {
      await mount(tester, const WorkshopMapPage(), (_) async => reply(savedPlan()), size: size);
      expect(find.byType(SvgPicture), findsOneWidget);
      expect(find.text('B01'), findsAtLeastNWidgets(1));
      expect(find.textContaining('No hay vehículos con órdenes activas'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
    testWidgets('Consulta de repuestos no depende de propuestas en $size', (tester) async {
      await mount(tester, const CatalogPartsPage(), catalog, size: size);
      expect(find.text('Pastillas de freno'), findsOneWidget);
      expect(find.textContaining('1802 repuestos accesibles'), findsOneWidget);
      expect(find.textContaining('lifeofcapo/car-api'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('La plantilla no se guarda antes de confirmarla', (tester) async {
    var data = emptyPlan();
    var writes = 0;
    await mount(tester, const WorkshopLayoutPage(), (request) async {
      if (request.method == 'POST') { writes++; data = savedPlan(); return reply(data, 201); }
      return reply(data);
    });
    await tester.tap(find.text('Usar plantilla de 6 bahías'));
    await tester.pumpAndSettle();
    expect(writes, 0);
    await tester.tap(find.text('Confirmar'));
    await tester.pumpAndSettle();
    expect(writes, 1);
    expect(find.text('B01'), findsOneWidget);
  });

  testWidgets('Crear bahía envía zona entera y geometría válida', (tester) async {
    Json? submitted;
    await mount(tester, const WorkshopLayoutPage(), (request) async {
      if (request.method == 'POST') { submitted = jsonDecode(request.body) as Json; return reply({'id': 9}, 201); }
      return reply(savedPlan());
    });
    await tester.tap(find.text('Nueva bahía'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byWidgetPredicate((widget) => widget is TextField && widget.decoration?.labelText == 'Nombre'), 'Puesto nuevo');
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();
    expect(submitted?['zone_id'], 1);
    expect(submitted?['kind'], 'mechanical');
    expect(submitted?['capacity'], 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Arrastrar una orden usa su ocupación guardada', (tester) async {
    var plan = savedPlan(occupied: true);
    Json? movement;
    await mount(tester, const WorkshopMapPage(), (request) async {
      if (request.method == 'POST' && request.url.path.endsWith('/location')) {
        movement = jsonDecode(request.body) as Json;
        final bays = plan['bays'] as List;
        (bays[1] as Json)['occupancies'] = (bays[0] as Json)['occupancies'];
        (bays[0] as Json)['occupancies'] = <dynamic>[];
        return reply({'location': {'id': 502}, 'order_status': 'in_progress'});
      }
      if (request.url.path.endsWith('/workshop/layout')) return reply(plan);
      if (request.url.path.endsWith('/dashboard')) return reply(<String, dynamic>{});
      return reply(<dynamic>[]);
    }, size: const Size(1440, 2300));
    final source = tester.getCenter(find.byType(Draggable<int>));
    final target = tester.getCenter(find.byType(DragTarget<int>).at(1));
    await tester.timedDragFrom(source, target - source, const Duration(seconds: 1));
    await tester.pumpAndSettle();
    expect(find.text('Confirmar movimiento'), findsOneWidget);
    await tester.tap(find.text('Confirmar movimiento'));
    await tester.pumpAndSettle();
    expect(movement?['expected_occupancy_id'], 501);
    expect(movement?['bay_id'], 2);
  });

  testWidgets('Búsqueda codifica símbolos y reinicia la paginación', (tester) async {
    final queries = <Map<String, String>>[];
    await mount(tester, const CatalogPartsPage(), (request) async {
      if (request.url.path.endsWith('/parts')) queries.add(request.url.queryParameters);
      return catalog(request);
    });
    await tester.tap(find.byTooltip('Siguiente'));
    await tester.pumpAndSettle();
    expect(queries.last['offset'], '20');
    await tester.enterText(find.byType(TextField).first, 'balatas & código');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();
    expect(queries.last['q'], 'balatas & código');
    expect(queries.last['offset'], '0');
  });

  testWidgets('Error HTTP se distingue de catálogo sin coincidencias', (tester) async {
    await mount(tester, const CatalogPartsPage(), (request) async => request.url.path.endsWith('/parts') ? reply({'detail': 'API temporalmente inaccesible'}, 503) : catalog(request));
    expect(find.text('No se pudo consultar el catálogo'), findsOneWidget);
    expect(find.text('Sin coincidencias'), findsNothing);
  });

  testWidgets('Catálogo vehicular navega de marca a su modelo', (tester) async {
    final queries = <Map<String, String>>[];
    await mount(tester, const AutomotiveCatalogPage(), (request) async {
      if (request.url.path.endsWith('/browse')) queries.add(request.url.queryParameters);
      return catalog(request);
    });
    await tester.tap(find.text('Toyota'));
    await tester.pumpAndSettle();
    expect(queries.last['entity'], 'model');
    expect(queries.last['make_id'], '2');
    expect(find.text('Corolla'), findsOneWidget);
  });

  testWidgets('Mecánico conserva Notificaciones y consulta técnica, no plano', (tester) async {
    await mount(tester, const AdminShell(), catalog, role: 'mechanic');
    expect(find.text('Notificaciones'), findsOneWidget);
    expect(find.text('Catálogo automotriz'), findsOneWidget);
    expect(find.text('Clientes'), findsNothing);
    await tester.tap(find.text('Notificaciones'));
    await tester.pumpAndSettle();
    expect(find.text('Centro de notificaciones'), findsOneWidget);
  });
}
