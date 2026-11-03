import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

import 'package:app_web_1/core/config/app_config_model.dart';
import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/state/make_logo_cache.dart';
import 'package:app_web_1/shared/atelier_controls.dart';

AppConfigModel _config(String themeKey) => AppConfigModel.fromJson({
      'schema_version': 1,
      'branding': {
        'name': 'MotorDesk',
        'tagline': '',
        'welcome': '',
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
      'theme': const {},
      'revision': 1,
    });

Widget _app(
  Widget child, {
  String theme = 'pitlane',
}) {
  return MaterialApp(
    theme: ThemeController.buildTheme(_config(theme)),
    home: Scaffold(body: SingleChildScrollView(child: child)),
  );
}

/// Busca el `Semantics` del botón, no el de la aplicación.
Semantics _buttonSemantics(WidgetTester tester) => tester.widget<Semantics>(
      find
          .descendant(
            of: find.byType(AtelierAction),
            matching: find.byType(Semantics),
          )
          .first,
    );

void main() {
  group('AtelierAction · estados', () {
    testWidgets('un botón deshabilitado no ejecuta su acción', (tester) async {
      await tester.pumpWidget(_app(const AtelierAction(
        label: 'Guardar',
        onPressed: null,
      )));
      await tester.tap(find.text('Guardar'));
      expect(tester.takeException(), isNull);
    });

    testWidgets('cargando bloquea un segundo envío', (tester) async {
      var pressed = 0;
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Publicar diseño',
        loading: true,
        onPressed: () => pressed++,
      )));
      // El rótulo no cambia al cargar: el usuario no debe dudar de si pulsó.
      expect(find.text('Publicar diseño'), findsOneWidget);
      await tester.tap(find.text('Publicar diseño'));
      expect(pressed, 0, reason: 'un botón cargando no debe enviar dos veces');
    });

    testWidgets('un botón cargado no se puede pulsar aunque la acción exista',
        (tester) async {
      var pressed = 0;
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Guardar',
        loading: true,
        onPressed: () => pressed++,
      )));
      await tester.tap(find.text('Guardar'), warnIfMissed: false);
      await tester.pump();
      expect(pressed, 0,
          reason: 'cargando bloquea aunque la acción exista');
    });

    testWidgets('el error permanece visible hasta que se solucione',
        (tester) async {
      await tester.pumpWidget(_app(const AtelierAction(
        label: 'Guardar',
        onPressed: null,
        error: 'No se pudo conectar con el servidor',
      )));
      expect(find.text('No se pudo conectar con el servidor'), findsOneWidget);
      // Sigue ahí tras varios fotogramas: un error que se va solo obliga a
      // repetir la acción a ciegas.
      await tester.pump(const Duration(seconds: 5));
      expect(find.text('No se pudo conectar con el servidor'), findsOneWidget);
    });

    testWidgets('sin error no hay línea de error', (tester) async {
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Guardar',
        onPressed: () {},
      )));
      expect(find.byType(AtelierAction), findsOneWidget);
    });

    testWidgets('selected cambia el aspecto y se anuncia', (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Aprobada',
        selected: true,
        onPressed: () {},
      )));
      expect(_buttonSemantics(tester).properties.selected, isTrue);
      handle.dispose();
    });

    testWidgets('cargando se anuncia como ocupado, no desaparece',
        (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Guardando',
        loading: true,
        onPressed: () {},
      )));
      expect(find.text('Guardando'), findsOneWidget);
      // Sigue siendo un botón, no un spinner suelto: el lector de pantalla
      // tiene que poder nombrarlo.
      expect(_buttonSemantics(tester).properties.button, isTrue);
      expect(_buttonSemantics(tester).properties.enabled, isFalse,
          reason: 'cargando no es pulsable');
      handle.dispose();
    });
  });

  group('AtelierAction · familias', () {
    testWidgets('una acción crítica pide confirmación antes de ejecutar',
        (tester) async {
      var pressed = 0;
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Eliminar orden',
        family: AtelierButton.critical,
        onPressed: () => pressed++,
      )));
      await tester.tap(find.text('Eliminar orden'));
      await tester.pumpAndSettle();
      expect(find.text('Confirmar acción'), findsOneWidget);
      expect(pressed, 0, reason: 'no debe ejecutarse sin confirmar');

      await tester.tap(find.text('Cancelar'));
      await tester.pumpAndSettle();
      expect(pressed, 0, reason: 'cancelar no ejecuta');
    });

    testWidgets('confirmar ejecuta la acción', (tester) async {
      var pressed = 0;
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Eliminar orden',
        family: AtelierButton.critical,
        onPressed: () => pressed++,
      )));
      await tester.tap(find.text('Eliminar orden'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sí, continuar'));
      await tester.pumpAndSettle();
      expect(pressed, 1);
    });

    testWidgets('una acción primaria no pide confirmación', (tester) async {
      var pressed = 0;
      await tester.pumpWidget(_app(AtelierAction(
        label: 'Guardar',
        onPressed: () => pressed++,
      )));
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();
      expect(pressed, 1);
      expect(find.text('Confirmar acción'), findsNothing);
    });

    testWidgets('las cinco familias se distinguen por color', (tester) async {
      final colors = <Color>{};
      for (final family in AtelierButton.values) {
        await tester.pumpWidget(_app(AtelierAction(
          label: family.name,
          family: family,
          onPressed: () {},
        )));
        await tester.pump();
        final container = tester.widget<AnimatedContainer>(
          find.descendant(
            of: find.byType(AtelierAction),
            matching: find.byType(AnimatedContainer),
          ),
        );
        final box = container.decoration as BoxDecoration;
        colors.add(box.color!);
      }
      // Si dos familias compartieran color, el taller no distinguiría una
      // acción crítica de una primaria.
      expect(colors.length, AtelierButton.values.length,
          reason: 'cada familia necesita su propio color');
    });
  });

  group('Estados de estado y medida', () {
    testWidgets('el estado operativo sale de los tokens del tema', (tester) async {
      await tester.pumpWidget(_app(
        Builder(builder: (context) => AtelierStateBadge.operational(
            'ready', context)),
        theme: 'carbon-racing',
      ));
      final container = tester.widget<Container>(find.byType(Container));
      final box = container.decoration as BoxDecoration;
      // #57CBB4 de Carbon Racing, no el verde de fábrica.
      expect(box.color, isNot(contains('#059669')));
      expect(find.text('Listo para retirar'), findsOneWidget);
    });

    testWidgets('un estado desconocido no es "todo bien"', (tester) async {
      await tester.pumpWidget(_app(Builder(
        builder: (context) => AtelierStateBadge.operational(null, context),
      )));
      expect(find.text('Sin estado'), findsOneWidget);
    });

    testWidgets('sin datos no se pinta como normal documentado', (tester) async {
      await tester.pumpWidget(_app(Builder(
        builder: (context) => AtelierStateBadge.condition(null, context),
      )));
      expect(find.text('Sin datos'), findsOneWidget);
      expect(find.text('Normal documentado'), findsNothing);
    });

    testWidgets('el medidor acota el valor y anuncia el porcentaje',
        (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(_app(const Column(children: [
        AtelierMeter(value: 0.42, label: 'Documentado'),
        AtelierMeter(value: 3.5),
        AtelierMeter(value: double.nan),
      ])));
      expect(find.text('Documentado'), findsOneWidget);
      expect(tester.takeException(), isNull);
      handle.dispose();
    });
  });

  group('Caché de logotipos de marca', () {
    /// Cliente que responde lo que se le pase, o falla si [status] no es 200.
    ApiClient api(Object body, {int status = 200}) => ApiClient(
          client: MockClient((request) async =>
              status == 200 ? http.Response(jsonEncode(body), 200)
                            : http.Response('{"detail":"sin permiso"}', status)),
          baseUrl: 'http://api.test/api/v1',
        );

    test('normaliza para que «CHEVROLET» encuentre «Chevrolet»', () {
      expect(MakeLogoCache.normalize('CHEVROLET'),
          MakeLogoCache.normalize('chevrolet'));
      expect(MakeLogoCache.normalize('  Chevrolet  '), 'chevrolet');
    });

    test('normaliza tildes y separadores', () {
      expect(MakeLogoCache.normalize('Ómnibus'), 'omnibus');
      expect(MakeLogoCache.normalize('Kia Motor'), 'kiamotor');
      expect(MakeLogoCache.normalize('Alfa Romeo'), 'alfaromeo');
    });

    test('una marca vacía o nula no busca nada', () {
      expect(MakeLogoCache.normalize(''), '');
      expect(MakeLogoCache.normalize('   '), '');
      final cache = MakeLogoCache(api(<dynamic>[]));
      expect(cache.logoFor(null), isNull);
      expect(cache.logoFor(''), isNull);
      expect(cache.logoFor('   '), isNull);
    });

    test('una marca sin logotipo en el catálogo devuelve null', () async {
      final cache = MakeLogoCache(api([
        {'name': 'Hyundai', 'slug': 'hyundai', 'logo_url': 'https://x.test/h.png'},
      ]));
      await cache.load();
      // Chevrolet no vino en la respuesta: no es un fallo, es una ausencia.
      expect(cache.logoFor('Chevrolet'), isNull);
      expect(cache.loaded, isTrue);
    });

    test('una cuenta sin acceso al catálogo no rompe la pantalla', () async {
      // Un cliente no puede consultar el catálogo: la pantalla de garaje es
      // suya y no debe caerse por pedir un logotipo.
      final cache = MakeLogoCache(api({}, status: 403));
      await cache.load();
      expect(cache.logoFor('Chevrolet'), isNull);
      expect(cache.loaded, isTrue, reason: 'se marca como consultado');
    });

    test('sin catálogo cargado devuelve null y no lanza', () {
      final cache = MakeLogoCache(api(<dynamic>[]));
      expect(cache.logoFor('Chevrolet'), isNull);
      expect(cache.logoFor(''), isNull);
      expect(cache.logoFor(null), isNull);
    });

    test('el logotipo se encuentra por nombre y por slug', () async {
      final cache = MakeLogoCache(api([
        {'name': 'Hyundai', 'slug': 'hyundai', 'logo_url': 'https://x.test/h.png'},
      ]));
      await cache.load();
      expect(cache.logoFor('HYUNDAI'), 'https://x.test/h.png');
      expect(cache.logoFor('hyundai'), 'https://x.test/h.png');
      expect(cache.logoFor(' Hyundai '), 'https://x.test/h.png');
    });

    group('coincidencia por prefijo', () {
      MakeLogoCache catalogo() => MakeLogoCache(api([
            {'name': 'Kia', 'slug': 'kia', 'logo_url': 'https://x.test/kia.png'},
            {'name': 'Toyota', 'slug': 'toyota', 'logo_url': 'https://x.test/toyota.png'},
            {'name': 'Chevrolet', 'slug': 'chevrolet', 'logo_url': 'https://x.test/chevy.png'},
            {'name': 'Alfa Romeo', 'slug': 'alfa-romeo', 'logo_url': 'https://x.test/ar.png'},
          ]));

      test('el taller escribe la marca con el modelo dentro', () async {
        final cache = catalogo();
        await cache.load();
        expect(cache.logoFor('Kia Motors'), 'https://x.test/kia.png');
        expect(cache.logoFor('Toyota Corolla'), 'https://x.test/toyota.png');
        expect(cache.logoFor('Chevrolet Sail'), 'https://x.test/chevy.png');
      });

      test('un nombre con espacios y tildes también', () async {
        final cache = catalogo();
        await cache.load();
        expect(cache.logoFor('alfa  romeo'), 'https://x.test/ar.png');
        expect(cache.logoFor('Árbol'), isNull);
      });

      test('la coincidencia exacta gana sobre la por prefijo', () async {
        final cache = MakeLogoCache(api([
          {'name': 'Toyota', 'slug': 'toyota', 'logo_url': 'https://x.test/t.png'},
          {'name': 'Toyota Pro', 'slug': 'toyota-pro', 'logo_url': 'https://x.test/tp.png'},
        ]));
        await cache.load();
        expect(cache.logoFor('Toyota Pro'), 'https://x.test/tp.png');
        expect(cache.logoFor('Toyota'), 'https://x.test/t.png');
      });

      test('la marca va con el modelo pegado', () async {
        // Acortar la consulta es justo lo que se busca: el taller escribe la
        // marca con el modelo dentro en el mismo campo.
        final cache = MakeLogoCache(api([
          {'name': 'Lamborghini', 'slug': 'lamborghini', 'logo_url': 'https://x.test/l.png'},
        ]));
        await cache.load();
        expect(cache.logoFor('Lamborghini Aventador'), 'https://x.test/l.png');
      });

      test('no acorta por debajo de tres letras', () async {
        // Con el catálogo «AB», la consulta «ABC» solo podría emparejar
        // acortando a dos letras. Con dos letras el riesgo de confundir marcas
        // es real, así que se corta antes.
        final cache = MakeLogoCache(api([
          {'name': 'AB', 'slug': 'ab', 'logo_url': 'https://x.test/ab.png'},
        ]));
        await cache.load();
        expect(cache.logoFor('ABC'), isNull);
        expect(cache.logoFor('AB'), 'https://x.test/ab.png',
            reason: 'la coincidencia exacta no tiene ese límite');
      });

      test('nunca empareja con una marca más larga', () async {
        // La búsqueda acorta la consulta, nunca alarga el catálogo: «MG» no
        // puede emparejar con «MG Rover» ni con nada que empiece por mg.
        final cache = MakeLogoCache(api([
          {'name': 'MG Rover', 'slug': 'mg-rover', 'logo_url': 'https://x/test/mg.png'},
        ]));
        await cache.load();
        expect(cache.logoFor('MG'), isNull);
      });
    });

    testWidgets('sin provider la tarjeta muestra la marca escrita',
        (tester) async {
      await tester.pumpWidget(_app(const MakeLogo(make: 'Hyundai')));
      // Iniciales en vez de una excepción.
      expect(find.text('H'), findsOneWidget);
    });

    testWidgets('sin provider y sin marca no rompe nada', (tester) async {
      await tester.pumpWidget(_app(const MakeLogo(make: null)));
      expect(find.text('·'), findsOneWidget);
    });

    testWidgets('con catálogo, la tarjeta deja de pintar iniciales',
        (tester) async {
      final cache = MakeLogoCache(api([
        {'name': 'Hyundai', 'slug': 'hyundai', 'logo_url': 'https://x.test/h.png'},
      ]));
      await cache.load();
      await tester.pumpWidget(_app(MultiProvider(
        providers: [ChangeNotifierProvider.value(value: cache)],
        child: const MakeLogo(make: 'Hyundai'),
      )));
      expect(find.text('H'), findsNothing);
      expect(find.byType(Image), findsOneWidget);
    });
  });
}