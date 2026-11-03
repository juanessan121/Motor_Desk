import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app_web_1/core/config/app_config_model.dart';
import 'package:app_web_1/core/config/atelier_tokens.dart';
import 'package:app_web_1/core/config/theme_controller.dart';

/// Paletas tal como las publica el servidor. Deben coincidir con
/// `backend/app/branding.py`: si divergen, la interfaz mostraría otra cosa
/// que la que el taller eligió.
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
  'carbon-racing': {
    'navigation': '#0D151C',
    'background': '#0D151C',
    'surface': '#202B34',
    'text': '#F5F8F9',
    'secondary_text': '#A7B3BC',
    'accent': '#FF774D',
    'complementary': '#57CBB4',
    'diagnostic': '#0B1116',
    'success': '#57CBB4',
    'warning': '#E0A458',
    'danger': '#FF6B6B',
    'unknown': '#A7B3BC',
  },
  'electric-blue': {
    'navigation': '#081D2C',
    'background': '#081D2C',
    'surface': '#123547',
    'text': '#F4FAFC',
    'secondary_text': '#A8C4D4',
    'accent': '#34D9DA',
    'complementary': '#B7E860',
    'diagnostic': '#061520',
    'success': '#B7E860',
    'warning': '#F2C14E',
    'danger': '#FF6B81',
    'unknown': '#A8C4D4',
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

AppConfigModel _config(String themeKey, {Map<String, String>? colors}) =>
    AppConfigModel.fromJson({
      'schema_version': 1,
      'branding': {
        'name': 'MotorDesk',
        'tagline': 'Tu taller, conectado.',
        'welcome': 'Cuidamos lo que te mueve',
        'logo': '',
        'colors': {
          ...AppConfigModel.defaults.colors,
          ...?colors,
        },
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
      'theme': _paletas[themeKey],
      'regional': AppConfigModel.defaultRegional,
      'revision': 1,
    });

void main() {
  group('Tokens del tema', () {
    test('cada paleta se convierte sin inventar colores', () {
      for (final entry in _paletas.entries) {
        final tokens = AtelierTokens.fromPalette(entry.value);
        Color expected(String key) =>
            Color(int.parse('FF${entry.value[key]!.substring(1)}', radix: 16));
        expect(tokens.navigation, expected('navigation'));
        expect(tokens.background, expected('background'));
        expect(tokens.success, expected('success'));
        expect(tokens.danger, expected('danger'));
      }
    });

    test('un valor ausente o inválido cae al valor por defecto', () {
      final tokens = AtelierTokens.fromPalette({
        'navigation': 'no-es-un-color',
      });
      const base = AtelierTokens();
      expect(tokens.navigation, base.navigation);
      // Una clave que no llega se comporta igual que una inválida.
      expect(tokens.success, base.success);
    });

    test('estados técnicos tienen color propio y "sin datos" es neutro', () {
      final tokens = AtelierTokens.fromPalette(_paletas['carbon-racing']!);
      expect(conditionColor('normal', tokens), const Color(0xFF57CBB4));
      expect(conditionColor('follow_up', tokens), const Color(0xFFE0A458));
      expect(conditionColor('issue', tokens), const Color(0xFFFF6B6B));
      // Ausencia de inspección no es "todo bien".
      expect(conditionColor(null, tokens), const Color(0xFFA7B3BC));
      expect(conditionLabels['no_data'], 'Sin datos');
    });

    test('estados operativos no se confunden con los técnicos', () {
      final tokens = AtelierTokens.fromPalette(_paletas['pitlane']!);
      expect(statusColor('ready', tokens), const Color(0xFF168B78));
      expect(statusColor('cancelled', tokens), const Color(0xFFC54747));
      expect(statusColor('desconocido', tokens), const Color(0xFF6F7C89));
    });
  });

  group('Construcción del tema', () {
    test('los cuatro temas producen un ThemeData válido', () {
      for (final key in _paletas.keys) {
        final theme = ThemeController.buildTheme(_config(key));
        expect(theme.extension<AtelierTokens>(), isNotNull,
            reason: 'el tema $key debe traer sus tokens');
      }
    });

    test('los temas oscuros pintan fondo oscuro y texto claro', () {
      for (final key in ['carbon-racing', 'electric-blue', 'heritage-garage']) {
        final theme = ThemeController.buildTheme(_config(key));
        expect(theme.colorScheme.brightness, Brightness.dark,
            reason: '$key es un tema oscuro');
        // Texto claro sobre fondo oscuro: nunca blanco sobre blanco.
        final background = theme.scaffoldBackgroundColor;
        final surface = theme.colorScheme.surface;
        final onSurface = theme.colorScheme.onSurface;
        expect(onSurface.computeLuminance(), greaterThan(0.5),
            reason: '$key debe tener texto claro');
        expect(background.computeLuminance(), lessThan(0.3));
        expect(onSurface.computeLuminance(), greaterThan(surface.computeLuminance()));
      }
    });

    test('pitlane es claro y legible', () {
      final theme = ThemeController.buildTheme(_config('pitlane'));
      expect(theme.colorScheme.brightness, Brightness.light);
      expect(theme.colorScheme.onSurface.computeLuminance(), lessThan(0.4));
    });

    test('un color de marca realmente publicado manda sobre el del tema', () {
      // Solo cuenta como publicado si difiere del valor de fábrica: con los
      // colores por defecto manda el tema, y si no, un tema oscuro nunca se
      // aplicaría porque el fondo de fábrica es claro.
      final conMarca = _config('electric-blue', colors: {'primary': '#FF6600'});
      expect(ThemeController.buildTheme(conMarca).colorScheme.primary,
          const Color(0xFFFF6600));

      // Sin publicar nada propio, manda el acento del tema.
      final sinMarca = _config('electric-blue');
      expect(ThemeController.buildTheme(sinMarca).colorScheme.primary,
          const Color(0xFF34D9DA));
    });

    test('un fondo de marca publicado también manda', () {
      final claro = _config('carbon-racing',
          colors: {'background': '#FFFFFF', 'surface': '#FFFFFF'});
      expect(ThemeController.buildTheme(claro).colorScheme.brightness,
          Brightness.light);
    });
  });

  group('Configuración regional', () {
    test('viaja con la configuración y no se pierde al reparsear', () {
      final config = _config('pitlane');
      expect(config.regional['country'], 'EC');
      expect(config.regional['timezone'], 'America/Guayaquil');
      expect(config.regional['currency'], 'USD');
      expect(config.regional['date_format'], 'dd/MM/yyyy');
    });

    test('toJson la incluye: si no, guardarla la borraría', () {
      final json = _config('pitlane').toJson();
      expect(json['regional'], isA<Map<String, dynamic>>());
      expect((json['regional'] as Map)['currency'], 'USD');
      expect((json['branding'] as Map)['theme'], 'pitlane');
    });

    test('una configuración sin región usa los valores de Ecuador', () {
      final config = AppConfigModel.fromJson({
        'schema_version': 1,
        'branding': {
          'name': 'X',
          'tagline': '',
          'welcome': '',
          'colors': {
            'primary': '#2563EB',
            'secondary': '#0D9488',
            'background': '#F4F6FA',
            'surface': '#FFFFFF',
          },
        },
        'features': {},
      });
      expect(config.regional['locale'], 'es-EC');
    });
  });
}