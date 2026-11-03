import 'package:flutter/material.dart';

/// Tokens del sistema visual Automotive Atelier.
///
/// Un `ThemeExtension` en lugar de constantes sueltas: las vistas leen los
/// tokens y no conocen colores literales. Los estados técnicos
/// (normal / seguimiento / incidencia / sin datos) viven aquí, no dentro de un
/// widget, para que "rojo" signifique siempre lo mismo en toda la aplicación.
///
/// Estos son valores por defecto y semántica. Los colores que publica el
/// taller en Personalización mandan sobre los de marca; el tema elegido manda
/// sobre la estructura y los estados.
@immutable
class AtelierTokens extends ThemeExtension<AtelierTokens> {
  const AtelierTokens({
    this.navigation = const Color(0xFF101B2E),
    this.background = const Color(0xFFF4F2EE),
    this.surface = const Color(0xFFFFFFFF),
    this.diagnostic = const Color(0xFF101B28),
    this.text = const Color(0xFF202B36),
    this.secondaryText = const Color(0xFF6F7C89),
    this.accent = const Color(0xFFD56845),
    this.complementary = const Color(0xFF168B78),
    this.success = const Color(0xFF168B78),
    this.warning = const Color(0xFFD99B32),
    this.danger = const Color(0xFFC54747),
    this.unknown = const Color(0xFF6F7C89),
    this.onNavigation = const Color(0xFFFFFFFF),
  });

  /// Fondo de la navegación lateral.
  final Color navigation;

  /// Fondo general de la aplicación.
  final Color background;

  /// Fondo de tarjetas, diálogos y campos.
  final Color surface;

  /// Fondo del visor técnico acotado.
  final Color diagnostic;
  final Color text;
  final Color secondaryText;
  final Color accent;
  final Color complementary;
  final Color success;
  final Color warning;
  final Color danger;
  final Color unknown;
  final Color onNavigation;

  // Se conservan los nombres antiguos: otras vistas ya los usan.
  Color get normal => success;

  static const normalLegacy = Color(0xFF168B78);
  static const warningLegacy = Color(0xFFD99B32);
  static const issue = Color(0xFFC54747);

  /// Traduce la paleta del servidor a tokens. Si falta algo, usa el valor por
  /// defecto en lugar de inventar un tono.
  factory AtelierTokens.fromPalette(Map<String, String> palette) {
    Color pick(String key, Color fallback) {
      final value = palette[key];
      if (value == null || !RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(value)) {
        return fallback;
      }
      return Color(int.parse('FF${value.substring(1)}', radix: 16));
    }

    const base = AtelierTokens();
    return AtelierTokens(
      navigation: pick('navigation', base.navigation),
      background: pick('background', base.background),
      surface: pick('surface', base.surface),
      diagnostic: pick('diagnostic', base.diagnostic),
      text: pick('text', base.text),
      secondaryText: pick('secondary_text', base.secondaryText),
      accent: pick('accent', base.accent),
      complementary: pick('complementary', base.complementary),
      success: pick('success', base.success),
      warning: pick('warning', base.warning),
      danger: pick('danger', base.danger),
      unknown: pick('unknown', base.unknown),
    );
  }

  @override
  AtelierTokens copyWith({
    Color? navigation,
    Color? background,
    Color? surface,
    Color? diagnostic,
    Color? text,
    Color? secondaryText,
    Color? accent,
    Color? complementary,
    Color? success,
    Color? warning,
    Color? danger,
    Color? unknown,
    Color? onNavigation,
  }) => AtelierTokens(
    navigation: navigation ?? this.navigation,
    background: background ?? this.background,
    surface: surface ?? this.surface,
    diagnostic: diagnostic ?? this.diagnostic,
    text: text ?? this.text,
    secondaryText: secondaryText ?? this.secondaryText,
    accent: accent ?? this.accent,
    complementary: complementary ?? this.complementary,
    success: success ?? this.success,
    warning: warning ?? this.warning,
    danger: danger ?? this.danger,
    unknown: unknown ?? this.unknown,
    onNavigation: onNavigation ?? this.onNavigation,
  );

  @override
  AtelierTokens lerp(covariant AtelierTokens? other, double t) => other == null
      ? this
      : AtelierTokens(
          navigation: Color.lerp(navigation, other.navigation, t)!,
          background: Color.lerp(background, other.background, t)!,
          surface: Color.lerp(surface, other.surface, t)!,
          diagnostic: Color.lerp(diagnostic, other.diagnostic, t)!,
          text: Color.lerp(text, other.text, t)!,
          secondaryText: Color.lerp(secondaryText, other.secondaryText, t)!,
          accent: Color.lerp(accent, other.accent, t)!,
          complementary: Color.lerp(complementary, other.complementary, t)!,
          success: Color.lerp(success, other.success, t)!,
          warning: Color.lerp(warning, other.warning, t)!,
          danger: Color.lerp(danger, other.danger, t)!,
          unknown: Color.lerp(unknown, other.unknown, t)!,
          onNavigation: Color.lerp(onNavigation, other.onNavigation, t)!,
        );
}

/// Etiquetas de los estados técnicos. `no_data` es "Sin datos", nunca un
/// diagnóstico: la ausencia de inspección no significa que el componente esté
/// bien.
const conditionLabels = {
  'no_data': 'Sin datos',
  'normal': 'Normal documentado',
  'follow_up': 'Seguimiento',
  'issue': 'Incidencia confirmada',
};

/// Color del estado técnico según los tokens del tema.
Color conditionColor(String? state, [AtelierTokens? tokens]) {
  final palette = tokens ?? const AtelierTokens();
  return switch (state) {
    'normal' => palette.success,
    'follow_up' => palette.warning,
    'issue' => palette.danger,
    _ => palette.unknown,
  };
}

/// Color de estado operativo (listo, en taller, entregado, cancelado).
Color statusColor(String? status, [AtelierTokens? tokens]) {
  final palette = tokens ?? const AtelierTokens();
  return switch (status) {
    'ready' => palette.success,
    'in_progress' => palette.warning,
    'paused' => palette.warning,
    'cancelled' => palette.danger,
    'delivered' => palette.complementary,
    _ => palette.unknown,
  };
}

extension AtelierTheme on BuildContext {
  /// Acceso a los tokens del tema activo.
  AtelierTokens get atelier =>
      Theme.of(this).extension<AtelierTokens>() ?? const AtelierTokens();
}
