import 'dart:convert';

import 'package:app_web_1/core/config/app_config_model.dart';
import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('Colores hexadecimales opacos y fallback seguro', () {
    expect(AppConfigModel.parseColor('#FF5500'), const Color(0xFFFF5500));
    expect(AppConfigModel.parseColor('incorrecto'), const Color(0xFF2563EB));
  });

  test('Round-trip JSON y control de revisión', () {
    final config = AppConfigModel.defaults.copyWith(
      features: {...AppConfigModel.defaults.features, 'photos': false},
    );
    final parsed = AppConfigModel.fromJson(config.toJson());
    expect(parsed.enabled('photos'), isFalse);
    expect(parsed.enabled('unknown'), isFalse);
    expect(parsed.toSaveJson()['expected_revision'], 1);
    expect(parsed.toSaveJson().containsKey('revision'), isFalse);
    expect(
      () => AppConfigModel.fromJson({'schema_version': 2}),
      throwsFormatException,
    );
  });

  test('ThemeController guarda JSON y reconstruye ThemeData', () async {
    final api = ApiClient(
      baseUrl: 'https://workshop.test/api/v1',
      client: MockClient((request) async {
        expect(request.method, 'PUT');
        expect(request.url.path, '/api/v1/config/global');
        final body = jsonDecode(request.body) as Json;
        expect(body['branding']['colors']['primary'], '#FF5500');
        expect(body['expected_revision'], 1);
        return http.Response(
          jsonEncode({...body..remove('expected_revision'), 'revision': 2}),
          200,
        );
      }),
    );
    final theme = ThemeController(api);
    var changes = 0;
    theme.addListener(() => changes++);
    await theme.save(
      AppConfigModel.defaults.copyWith(
        colors: {...AppConfigModel.defaults.colors, 'primary': '#FF5500'},
      ),
    );
    expect(theme.config.revision, 2);
    expect(theme.theme.colorScheme.primary, const Color(0xFFFF5500));
    expect(changes, 1);
    theme.dispose();
    api.dispose();
  });

  test('Errores de API conservan estado y mensaje', () async {
    final api = ApiClient(
      client: MockClient(
        (_) async => http.Response('{"detail":"Sesión revocada"}', 401),
      ),
    );
    await expectLater(
      api.request('GET', '/auth/me'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.statusCode,
          'statusCode',
          401,
        ),
      ),
    );
    api.dispose();
  });
}
