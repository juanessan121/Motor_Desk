import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

import 'package:app_web_1/core/config/app_config_model.dart';
import 'package:app_web_1/core/config/atelier_tokens.dart';
import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/state/workshop_controller.dart';
import 'package:app_web_1/features/auth/login_page.dart';
import 'package:app_web_1/features/dashboard/admin_shell.dart';
import 'package:app_web_1/features/dashboard/overview_page.dart';

/// Paletas reales, para comprobar que la interfaz responde al tema.
const _paletas = <String, Map<String, String>>{
  'pitlane': {
    'navigation': '#101B2E',
    'background': '#F4F2EE',
    'surface': '#FFFFFF',
    'text': '#202B36',
    'secondary_text': '#6F7C89',
    'accent': '#D56845',
    'complementary': '#168B78',
    'diagnostic': '#101B28',
    'success': '#168B78',
    'warning': '#D99B32',
    'danger': '#C54747',
    'unknown': '#6F7C89',
  },
  'heritage-garage': {
    'navigation': '#183A34',
    'background': '#183A34',
    'surface': '#275047',
    'text': '#FAF5E9',
    'secondary_text': '#C3CFC6',
    'accent': '#E4B86A',
    'complementary': '#D9C7A3',
    'diagnostic': '#122B26',
    'success': '#9CC08A',
    'warning': '#E4B86A',
    'danger': '#D98A7A',
    'unknown': '#C3CFC6',
  },
};

AppConfigModel _config(String themeKey) => AppConfigModel.fromJson({
  'schema_version': 1,
  'branding': {
    'name': 'MotorDesk',
    'tagline': 'Tu taller, conectado.',
    'welcome': 'Cuidamos lo que te mueve',
    'logo': '',
    'colors': Map.of(AppConfigModel.defaults.colors),
    'theme': themeKey,
  },
  'features': {
    'vehicles': true,
    'maintenance': true,
    'quotes': true,
    'photos': true,
    'history': true,
  },
  'theme_key': themeKey,
  'theme': _paletas[themeKey]!,
  'revision': 1,
});

void main() {
  Future<ThemeController> mount(
    WidgetTester tester,
    Widget page, {
    String theme = 'pitlane',
    Size size = const Size(1440, 1000),
    WorkshopController? state,
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = ApiClient(
      client: MockClient((request) async => http.Response('[]', 200)),
    );
    final controller = ThemeController(api)..config = _config(theme);
    final workshop = state ?? WorkshopController(api, controller);
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: controller),
          ChangeNotifierProvider.value(value: workshop),
        ],
        child: MaterialApp(
          theme: controller.theme,
          locale: const Locale('es'),
          supportedLocales: const [Locale('es')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: Scaffold(
            body: Padding(padding: const EdgeInsets.all(12), child: page),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    addTearDown(() {
      if (state == null) workshop.dispose();
      controller.dispose();
    });
    return controller;
  }

  group('Command Center', () {
    testWidgets('el banner dice qué día es', (tester) async {
      await mount(tester, OverviewPage(onNavigate: (_) {}));
      expect(find.textContaining('Tu taller, en movimiento'), findsOneWidget);
      expect(find.textContaining('Hoy ·'), findsOneWidget);
      expect(find.textContaining('Thursday'), findsNothing);
      expect(find.textContaining('October'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('cada cifra lleva a su destino', (tester) async {
      var destino = -1;
      await mount(tester, OverviewPage(onNavigate: (index) => destino = index));
      await tester.tap(find.text('Clientes activos'));
      await tester.pumpAndSettle();
      // La flecha del concepto no era decorativa: la tarjeta navega.
      expect(destino, 1, reason: 'Clientes activos lleva a Clientes');

      await mount(tester, OverviewPage(onNavigate: (index) => destino = index));
      await tester.tap(find.text('En mantenimiento'));
      await tester.pumpAndSettle();
      expect(destino, 4, reason: 'En mantenimiento lleva a Órdenes');
    });

    testWidgets('las métricas usan el tema, no colores fijos', (tester) async {
      await mount(
        tester,
        OverviewPage(onNavigate: (_) {}),
        theme: 'heritage-garage',
      );
      final icon = tester.widget<Icon>(
        find.descendant(
          of: find.ancestor(
            of: find.text('Clientes activos'),
            matching: find.byType(Card),
          ),
          matching: find.byIcon(Icons.people_outline),
        ),
      );
      // #E4B86A de Heritage Garage, no el azul de fábrica.
      expect(icon.color, const Color(0xFFE4B86A));
    });
  });

  group('Barra lateral', () {
    for (final entry in _paletas.entries) {
      testWidgets('la barra usa el token de navegación de ${entry.key}', (
        tester,
      ) async {
        await mount(tester, const AdminShell(), theme: entry.key);
        final barra = tester.widget<Container>(
          find
              .ancestor(
                of: find.text('ESPACIO DE TRABAJO'),
                matching: find.byType(Container),
              )
              .first,
        );
        expect(
          barra.color,
          isNotNull,
          reason: 'una barra sin color se transparentaría',
        );
        // El literal #0E182A quedaba azul marino en los cuatro temas.
        expect(
          barra.color,
          Color(
            int.parse(
              'FF${entry.value['navigation']!.substring(1)}',
              radix: 16,
            ),
          ),
        );
        expect(tester.takeException(), isNull);
      });
    }
  });

  group('Inicio de sesión', () {
    testWidgets('el panel explica las tres razones para usarlo', (
      tester,
    ) async {
      await mount(tester, const LoginPage(), size: const Size(1440, 1000));
      expect(find.text('Gestión completa'), findsOneWidget);
      expect(find.text('Seguimiento en tiempo real'), findsOneWidget);
      expect(find.text('Historial siempre disponible'), findsOneWidget);
    });

    testWidgets('no inventa cifras antes de iniciar sesión', (tester) async {
      await mount(tester, const LoginPage(), size: const Size(1440, 1000));
      // El concepto muestra «2 clientes activos» en esta pantalla. Aquí no hay
      // sesión: cualquier número sería inventado.
      expect(find.textContaining('Clientes activos'), findsNothing);
      expect(find.textContaining('0'), findsNothing);
    });

    testWidgets('el formulario no depende del ancho', (tester) async {
      for (final size in [const Size(390, 844), const Size(1440, 1000)]) {
        await mount(tester, const LoginPage(), size: size);
        expect(find.text('¡Bienvenido de nuevo!'), findsOneWidget);
        expect(find.text('Entrar a mi espacio'), findsOneWidget);
        expect(tester.takeException(), isNull);
      }
    });

    testWidgets('el botón de acceso no cambia de rótulo al enviar', (
      tester,
    ) async {
      await mount(tester, const LoginPage());
      expect(find.text('Entrar a mi espacio'), findsOneWidget);
      // Vacío: la validación local debe avisar antes de tocar la red.
      await tester.tap(find.text('Entrar a mi espacio'));
      await tester.pumpAndSettle();
      expect(find.text('Entrar a mi espacio'), findsOneWidget);
      expect(find.text('Ingresa tu usuario'), findsOneWidget);
    });
  });

  group('Tokens', () {
    test('la navegación del tema es la del tema, no un azul fijo', () {
      for (final entry in _paletas.entries) {
        final tokens = AtelierTokens.fromPalette(entry.value);
        expect(
          tokens.navigation,
          Color(
            int.parse(
              'FF${entry.value['navigation']!.substring(1)}',
              radix: 16,
            ),
          ),
        );
      }
    });
  });
}
