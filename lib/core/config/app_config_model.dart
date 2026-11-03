import 'package:flutter/material.dart';

import '../network/api_client.dart';

const featureLabels = {
  'vehicles': 'Mis vehículos',
  'maintenance': 'Seguimiento del mantenimiento',
  'quotes': 'Aprobación de repuestos',
  'photos': 'Fotografías de recepción',
  'history': 'Historial técnico',
};

/// Región por defecto. El servidor la vuelve a mandar; esto solo cubre el
/// primer arranque sin red. Se declara antes de `defaults` porque una
/// constante no puede referenciar a otra declarada más abajo en la clase.
const defaultRegionalMap = <String, dynamic>{
  'country': 'EC',
  'locale': 'es-EC',
  'timezone': 'America/Guayaquil',
  'currency': 'USD',
  'currency_symbol': r'$',
  'date_format': 'dd/MM/yyyy',
  'distance_unit': 'km',
  'temperature_unit': 'C',
  'power_unit': 'hp',
  'displacement_unit': 'cc',
};

class AppConfigModel {
  const AppConfigModel({
    required this.name,
    required this.tagline,
    required this.welcome,
    required this.logo,
    required this.colors,
    required this.features,
    this.themeKey = 'pitlane',
    this.theme = const {},
    this.regional = const {},
    this.revision = 1,
  });

  final String name;
  final String tagline;
  final String welcome;
  final String logo;
  final Map<String, String> colors;
  final Map<String, bool> features;
  /// Clave del tema elegido en Personalización.
  final String themeKey;
  /// Paleta resuelta por el servidor; la interfaz no la adivina.
  final Map<String, String> theme;
  final Map<String, dynamic> regional;
  final int revision;

  static const defaults = AppConfigModel(
    name: 'MotorDesk',
    tagline: 'Tu taller, conectado.',
    welcome: 'Cuidamos lo que te mueve',
    logo: '',
    colors: {
      'primary': '#2563EB',
      'secondary': '#0D9488',
      'background': '#F4F6FA',
      'surface': '#FFFFFF',
    },
    features: {
      'vehicles': true,
      'maintenance': true,
      'quotes': true,
      'photos': true,
      'history': true,
    },
    regional: defaultRegionalMap,
  );

  static const defaultRegional = defaultRegionalMap;

  factory AppConfigModel.fromJson(Json json) {
    if (json['schema_version'] != 1) {
      throw const FormatException('Versión de configuración no soportada');
    }
    final branding = Map<String, dynamic>.from(
        (json['branding'] as Map?) ?? const {});
    final incomingColors =
        Map<String, dynamic>.from((branding['colors'] as Map?) ?? const {});
    final incomingFlags =
        Map<String, dynamic>.from((json['features'] as Map?) ?? const {});
    final incomingTheme = Map<String, dynamic>.from(
        (json['theme'] as Map?) ?? const {});
    final incomingRegional =
        Map<String, dynamic>.from((json['regional'] as Map?) ?? const {});
    return AppConfigModel(
      name: branding['name'] as String? ?? defaults.name,
      tagline: branding['tagline'] as String? ?? defaults.tagline,
      welcome: branding['welcome'] as String? ?? defaults.welcome,
      logo: branding['logo'] as String? ?? '',
      colors: {
        for (final entry in defaults.colors.entries)
          entry.key: incomingColors[entry.key] as String? ?? entry.value,
      },
      features: {
        for (final key in featureLabels.keys) key: incomingFlags[key] == true,
      },
      themeKey: json['theme_key'] as String? ?? 'pitlane',
      theme: {
        for (final entry in incomingTheme.entries)
          entry.key: entry.value?.toString() ?? '',
      },
      regional: {
        ...defaultRegional,
        ...incomingRegional,
      },
      revision: json['revision'] as int? ?? 1,
    );
  }

  bool enabled(String feature) => features[feature] ?? false;

  static Color parseColor(
    String value, {
    Color fallback = const Color(0xFF2563EB),
  }) {
    final hex = value.replaceFirst('#', '');
    if (!RegExp(r'^[0-9a-fA-F]{6}$').hasMatch(hex)) return fallback;
    return Color(int.parse('FF$hex', radix: 16));
  }

  Color color(String key) => parseColor(colors[key] ?? defaults.colors[key]!);

  Json toJson() => {
    'schema_version': 1,
    'branding': {
      'name': name,
      'tagline': tagline,
      'welcome': welcome,
      'logo': logo,
      'colors': colors,
      'theme': themeKey,
    },
    'features': features,
    // Sin esta clave, guardar el diseño borraría la región: el backend
    // reemplaza el payload entero.
    'regional': regional,
    'revision': revision,
  };

  Json toSaveJson() => {
    ...toJson()..remove('revision'),
    'expected_revision': revision,
  };

  AppConfigModel copyWith({
    String? name,
    String? tagline,
    String? welcome,
    String? logo,
    Map<String, String>? colors,
    Map<String, bool>? features,
    String? themeKey,
    Map<String, dynamic>? regional,
  }) => AppConfigModel(
    name: name ?? this.name,
    tagline: tagline ?? this.tagline,
    welcome: welcome ?? this.welcome,
    logo: logo ?? this.logo,
    colors: colors ?? this.colors,
    features: features ?? this.features,
    themeKey: themeKey ?? this.themeKey,
    theme: themeKey == null || themeKey == this.themeKey ? theme : const {},
    regional: regional ?? this.regional,
    revision: revision,
  );
}
