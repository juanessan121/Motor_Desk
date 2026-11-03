import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../network/api_client.dart';
import 'app_config_model.dart';
import 'atelier_tokens.dart';

class ThemeController extends ChangeNotifier {
  ThemeController(this.api);
  final ApiClient api;
  AppConfigModel config = AppConfigModel.defaults;
  String? loadError;

  Future<void> initialize() async {
    final preferences = await SharedPreferences.getInstance();
    final cached = preferences.getString('public_branding_v1');
    if (cached != null) {
      try {
        config = AppConfigModel.fromJson(jsonDecode(cached) as Json);
        notifyListeners();
      } catch (_) {
        await preferences.remove('public_branding_v1');
      }
    }
    try {
      await refresh(public: true);
    } catch (error) {
      loadError = error.toString();
      notifyListeners();
    }
  }

  Future<void> refresh({bool public = false}) async {
    final token = api.token;
    final data =
        await api.request('GET', public ? '/public/config' : '/config') as Json;
    if (api.token != token) return;
    config = AppConfigModel.fromJson(data);
    loadError = null;
    if (public) {
      final preferences = await SharedPreferences.getInstance();
      await preferences.setString('public_branding_v1', jsonEncode(data));
    }
    notifyListeners();
  }

  Future<void> save(AppConfigModel value) async {
    final data =
        await api.request('PUT', '/config/global', body: value.toSaveJson())
            as Json;
    config = AppConfigModel.fromJson(data);
    notifyListeners();
  }

  ThemeData get theme => buildTheme(config);

  static ThemeData buildTheme(AppConfigModel config) {
    // La paleta del tema elegido la resuelve el servidor; los tokens se
    // derivan de ella. Si no llega, se usan los valores por defecto.
    final tokens = AtelierTokens.fromPalette(config.theme);

    // Los cuatro colores que publica el taller mandan sobre los del tema,
    // pero solo si los publicó de verdad: mientras sigan siendo los valores
    // de fábrica, manda el tema. Sin esta distinción, elegir Carbon Racing
    // dejaba el fondo en `#F4F6FA` y el tema oscuro no se aplicaba nunca.
    bool published(String key) =>
        config.colors[key] != AppConfigModel.defaults.colors[key];

    Color brandOrTheme(String key, Color fallback) =>
        published(key) ? config.color(key) : fallback;

    final background = brandOrTheme('background', tokens.background);
    final dark =
        ThemeData.estimateBrightnessForColor(background) == Brightness.dark;
    final brightness = dark ? Brightness.dark : Brightness.light;
    Color contrast(Color color) =>
        ThemeData.estimateBrightnessForColor(color) == Brightness.dark
            ? Colors.white
            : const Color(0xFF14213D);

    final brandPrimary = brandOrTheme('primary', tokens.accent);
    final surface = brandOrTheme(
      'surface',
      dark
          ? Color.alphaBlend(Colors.white.withValues(alpha: .04), background)
          : Colors.white,
    );

    final scheme = ColorScheme.fromSeed(
      seedColor: brandPrimary,
      brightness: brightness,
    ).copyWith(
      primary: brandPrimary,
      onPrimary: contrast(brandPrimary),
      secondary: brandOrTheme('secondary', tokens.complementary),
      onSecondary: contrast(brandOrTheme('secondary', tokens.complementary)),
      surface: surface,
      onSurface: dark ? Colors.white : tokens.text,
      onSurfaceVariant: tokens.secondaryText,
      error: tokens.danger,
    );

    final border = OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: scheme.outlineVariant),
    );
    final subtle = dark
        ? Color.alphaBlend(Colors.white.withValues(alpha: .04), surface)
        : surface;

    return ThemeData(
      extensions: [tokens],
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      fontFamily: 'Inter',
      visualDensity: VisualDensity.standard,
      appBarTheme: AppBarTheme(
        backgroundColor: background,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        foregroundColor: scheme.onSurface,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: subtle,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: scheme.outlineVariant.withValues(alpha: .7)),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant.withValues(alpha: .45),
        space: 1,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: subtle,
        border: border,
        enabledBorder: border,
        focusedBorder:
            border.copyWith(borderSide: BorderSide(color: brandPrimary, width: 2)),
        labelStyle: TextStyle(color: tokens.secondaryText),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 17),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 19),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          disabledBackgroundColor: brandPrimary.withValues(alpha: .35),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
          side: BorderSide(color: scheme.outline),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        side: BorderSide(color: scheme.outlineVariant),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      dataTableTheme: DataTableThemeData(
        headingRowColor: WidgetStatePropertyAll(
          dark
              ? Color.alphaBlend(Colors.white.withValues(alpha: .05), surface)
              : scheme.surfaceContainerLowest,
        ),
        headingTextStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: tokens.secondaryText,
        ),
        dataRowMinHeight: 68,
        dataRowMaxHeight: 78,
        horizontalMargin: 22,
        columnSpacing: 28,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
    );
  }
}