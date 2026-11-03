import 'dart:async';
import 'dart:convert';

import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/models/entities.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/state/workshop_controller.dart';
import 'package:app_web_1/features/registry/registry_forms.dart';
import 'package:app_web_1/features/vehicles/catalog_review_page.dart';
import 'package:app_web_1/features/vehicles/vehicle_catalog_picker.dart';
import 'package:app_web_1/features/vehicles/vehicle_passport.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

http.Response response(Object value, [int status = 200]) => http.Response(
  jsonEncode(value),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

const reference = <String, dynamic>{
  'make_id': 1,
  'make_name': 'Referencia',
  'model_id': 2,
  'model_name': 'Uno',
  'generation_id': 3,
  'generation_name': 'Primera',
  'engine_id': 4,
  'engine': {'id': 4, 'label': '1.6 Prueba', 'power_hp': 120},
};

Future<WorkshopController> mount(
  WidgetTester tester,
  Widget child,
  Future<http.Response> Function(http.Request) handler, {
  bool admin = true,
  Size? size,
}) async {
  if (size != null) {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }
  final api = ApiClient(
    client: MockClient(handler),
    baseUrl: 'http://api.test/api/v1',
  )..token = 'prueba';
  final theme = ThemeController(api);
  final state = WorkshopController(api, theme)
    ..user = {
      'id': 1,
      'username': 'prueba',
      'role': admin ? 'admin' : 'mechanic',
      'must_change_password': false,
    };
  state.customers = [
    Customer({
      'id': 1,
      'first_name': 'Cliente',
      'last_name': 'Prueba',
      'active': true,
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

Widget picker(
  TextEditingController brand,
  TextEditingController model,
  ValueChanged<Json?> changed,
) => Builder(
  builder: (context) => SingleChildScrollView(
    child: VehicleCatalogPicker(
      api: context.read<WorkshopController>().api,
      brandController: brand,
      modelController: model,
      showYear: false,
      onChanged: changed,
    ),
  ),
);

Future<http.Response> catalogApi(http.Request request) async {
  final path = request.url.path;
  if (path.endsWith('/catalog/makes')) {
    return response([
      {'id': 1, 'name': 'Referencia'},
    ]);
  }
  if (path.endsWith('/catalog/models')) {
    return response([
      {'id': 2, 'name': 'Uno'},
    ]);
  }
  if (path.endsWith('/catalog/generations')) {
    return response([
      {'id': 3, 'name': 'Primera'},
    ]);
  }
  if (path.endsWith('/catalog/engines')) {
    return response([
      {'id': 4, 'label': '1.6 Prueba'},
    ]);
  }
  if (path.endsWith('/dashboard')) return response(<String, dynamic>{});
  return response(<dynamic>[]);
}

void main() {
  testWidgets('La cascada carga motores y conserva sus IDs', (tester) async {
    final brand = TextEditingController();
    final model = TextEditingController();
    addTearDown(brand.dispose);
    addTearDown(model.dispose);
    Json? selection;
    await mount(
      tester,
      picker(brand, model, (value) => selection = value),
      catalogApi,
    );
    for (final label in ['Referencia', 'Uno', 'Primera', '1.6 Prueba']) {
      await tester.ensureVisible(find.text(label));
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
    }
    expect((selection?['generation'] as Map)['id'], 3);
    expect((selection?['engine'] as Map)['id'], 4);
    expect(brand.text, 'Referencia');
    expect(model.text, 'Uno');
    // Cambiar el texto a mano invalida descendientes en vez de enviar IDs viejos.
    model.text = 'Otro modelo';
    await tester.pumpAndSettle();
    expect(selection?['model'], isNull);
    expect(selection?['engine'], isNull);
  });

  testWidgets('El formulario envía la selección completa a la API', (
    tester,
  ) async {
    Json? submitted;
    final existing = Vehicle({
      'id': 7,
      'owner_id': 1,
      'plate': 'REF1234',
      'brand': 'Referencia',
      'model': 'Uno',
      'year': 2018,
      'mileage': 1000,
      'active': true,
    });
    await mount(
      tester,
      Builder(
        builder: (context) => TextButton(
          onPressed: () => editVehicle(context, existing),
          child: const Text('Editar'),
        ),
      ),
      (request) async {
        if (request.method == 'PUT') {
          submitted = jsonDecode(request.body) as Json;
          return response({});
        }
        return catalogApi(request);
      },
      size: const Size(1000, 1800),
    );
    await tester.tap(find.text('Editar'));
    await tester.pumpAndSettle();
    // Los resultados del selector no son los campos de texto del formulario.
    for (final label in ['Referencia', 'Uno', 'Primera', '1.6 Prueba']) {
      final matches = find.descendant(
        of: find.byType(VehicleCatalogPicker),
        matching: find.text(label),
      );
      expect(
        matches,
        findsAtLeastNWidgets(1),
        reason: 'Resultado del catálogo: $label',
      );
      final target = matches.last;
      await tester.ensureVisible(target);
      await tester.tap(target);
      await tester.pumpAndSettle();
    }
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();
    expect(submitted?['catalog_make_id'], 1);
    expect(submitted?['catalog_model_id'], 2);
    expect(submitted?['catalog_generation_id'], 3);
    expect(submitted?['catalog_engine_id'], 4);
    expect(submitted?['year'], 2018);
  });

  testWidgets('Registrar marca sin resultados no falla por índice negativo', (
    tester,
  ) async {
    final brand = TextEditingController();
    final model = TextEditingController();
    addTearDown(brand.dispose);
    addTearDown(model.dispose);
    await mount(
      tester,
      picker(brand, model, (_) {}),
      (_) async => response(<dynamic>[]),
    );
    await tester.tap(find.text('no encuentro marca'));
    await tester.pumpAndSettle();
    expect(find.text('Registrar marca'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Una respuesta antigua no mezcla modelos de otra marca', (
    tester,
  ) async {
    final brand = TextEditingController();
    final model = TextEditingController();
    addTearDown(brand.dispose);
    addTearDown(model.dispose);
    final slow = Completer<http.Response>();
    await mount(tester, picker(brand, model, (_) {}), (request) async {
      if (request.url.path.endsWith('/makes')) {
        return response([
          {'id': 1, 'name': 'A'},
          {'id': 2, 'name': 'B'},
        ]);
      }
      if (request.url.queryParameters['make_id'] == '1') return slow.future;
      return response([
        {'id': 22, 'name': 'Modelo B'},
      ]);
    });
    await tester.tap(find.text('A'));
    await tester.pump();
    await tester.tap(find.byIcon(Icons.close).first);
    await tester.pump();
    await tester.tap(find.text('B'));
    await tester.pumpAndSettle();
    slow.complete(
      response([
        {'id': 11, 'name': 'Modelo A'},
      ]),
    );
    await tester.pumpAndSettle();
    expect(find.text('Modelo B'), findsOneWidget);
    expect(find.text('Modelo A'), findsNothing);
  });

  for (final size in [const Size(390, 844), const Size(1440, 1000)]) {
    testWidgets('El Pasaporte distingue referencia y verificación en $size', (
      tester,
    ) async {
      await mount(
        tester,
        SingleChildScrollView(
          child: VehicleIdentityCard(
            vehicle: Vehicle({
              'brand': 'Referencia',
              'model': 'Uno',
              'year': 2018,
              'catalog': reference,
            }),
          ),
        ),
        catalogApi,
        size: size,
      );
      expect(
        find.textContaining('Motor de referencia: 1.6 Prueba'),
        findsOneWidget,
      );
      expect(find.textContaining('no certifican'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Sin enlace el Pasaporte no afirma que el modelo no exista', (
    tester,
  ) async {
    await mount(
      tester,
      VehicleIdentityCard(
        vehicle: Vehicle({'brand': 'Toyota', 'model': 'Corolla'}),
      ),
      catalogApi,
    );
    expect(
      find.textContaining('Sin referencia al catálogo guardada'),
      findsOneWidget,
    );
    expect(find.textContaining('no coincide con ninguna ficha'), findsNothing);
  });

  Json reviewRow() => {
    'entity_type': 'part',
    'entity_id': 9,
    'record': {'id': 9, 'title': 'Rodamiento propuesto', 'sku': 'REV-9'},
    'revision': 1,
    'created_by_name': 'mecanico',
    'created_at': '2026-10-19T12:00:00Z',
    'review_note': '',
    'terms': <dynamic>[],
    'parents': <dynamic>[],
  };

  testWidgets('Verificar exige confirmación y conserva la revisión esperada', (
    tester,
  ) async {
    Json? decision;
    var verified = false;
    await mount(tester, const CatalogReviewPage(), (request) async {
      if (request.method == 'POST') {
        decision = jsonDecode(request.body) as Json;
        verified = true;
        return response({});
      }
      return response({
        'items': verified ? <dynamic>[] : [reviewRow()],
        'total': verified ? 0 : 1,
      });
    });
    await tester.tap(find.text('Verificar registro'));
    await tester.pumpAndSettle();
    expect(decision, isNull);
    await tester.enterText(find.byType(TextField), 'Contrastado con la ficha');
    await tester.tap(find.text('Confirmar verificación'));
    await tester.pumpAndSettle();
    expect(decision, {
      'expected_revision': 1,
      'decision': 'verify',
      'note': 'Contrastado con la ficha',
    });
    expect(find.text('Sin registros en esta vista'), findsOneWidget);
  });

  testWidgets('Un error conserva la nota y un conflicto obliga a refrescar', (
    tester,
  ) async {
    var attempts = 0;
    await mount(tester, const CatalogReviewPage(), (request) async {
      if (request.method == 'POST') {
        attempts++;
        return response({
          'detail': attempts == 1 ? 'Sin conexión' : 'Revisión desactualizada',
        }, attempts == 1 ? 503 : 409);
      }
      return response({
        'items': [reviewRow()],
        'total': 1,
      });
    });
    await tester.tap(find.text('Dejar pendiente'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Guardar motivo'));
    await tester.pumpAndSettle();
    expect(attempts, 0);
    await tester.enterText(
      find.byType(TextField),
      'Falta contrastar el código',
    );
    await tester.tap(find.text('Guardar motivo'));
    await tester.pumpAndSettle();
    expect(find.text('Falta contrastar el código'), findsOneWidget);
    await tester.tap(find.text('Guardar motivo'));
    await tester.pumpAndSettle();
    expect(find.text('Actualizar cola'), findsOneWidget);
    expect(find.text('Guardar motivo'), findsNothing);
  });

  testWidgets('El mecánico no consulta la cola administrativa', (tester) async {
    var requests = 0;
    await mount(tester, const CatalogReviewPage(), (_) async {
      requests++;
      return response({});
    }, admin: false);
    expect(find.text('Acceso restringido'), findsOneWidget);
    expect(requests, 0);
  });

  for (final size in [const Size(390, 844), const Size(1440, 1000)]) {
    testWidgets('La cola de revisión se adapta a $size', (tester) async {
      await mount(
        tester,
        const CatalogReviewPage(),
        (_) async => response({
          'items': [reviewRow()],
          'total': 1,
        }),
        size: size,
      );
      expect(find.textContaining('Rodamiento propuesto'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
