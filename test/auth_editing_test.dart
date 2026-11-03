import 'dart:async';
import 'dart:convert';

import 'package:app_web_1/app.dart';
import 'package:app_web_1/core/config/app_config_model.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const temporaryPassword = 'temporary-test-password';
const validPassword = 'new-password-for-testing-2026';

ApiClient authApi({
  Future<http.Response> Function(http.Request)? changePassword,
}) => ApiClient(
  client: MockClient((request) async {
    if (request.url.path == '/api/v1/auth/login') {
      return http.Response(
        jsonEncode({
          'access_token': 'test-session-token',
          'user': {
            'id': 1,
            'username': 'admin',
            'role': 'admin',
            'must_change_password': true,
          },
        }),
        200,
      );
    }
    if (request.url.path == '/api/v1/auth/password' && changePassword != null) {
      return changePassword(request);
    }
    if (request.url.path == '/api/v1/public/config') {
      return http.Response(jsonEncode(AppConfigModel.defaults.toJson()), 200);
    }
    return http.Response('{"detail":"Solicitud inesperada"}', 400);
  }),
);

TextField input(WidgetTester tester, String key) => tester.widget<TextField>(
  find.descendant(
    of: find.byKey(ValueKey(key)),
    matching: find.byType(TextField),
  ),
);

Future<void> openPasswordForm(WidgetTester tester, ApiClient api) async {
  tester.view.physicalSize = const Size(1440, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MotorDeskApp(api: api, initialize: false));
  await tester.enterText(find.byKey(const ValueKey('auth.username')), 'admin');
  await tester.enterText(
    find.byKey(const ValueKey('auth.password')),
    temporaryPassword,
  );
  await tester.tap(find.text('Entrar a mi espacio'));
  await tester.pumpAndSettle();
}

Future<void> enterPasswordFields(WidgetTester tester, String next) async {
  await tester.enterText(
    find.byKey(const ValueKey('auth.current-password')),
    temporaryPassword,
  );
  await tester.enterText(find.byKey(const ValueKey('auth.new-password')), next);
  await tester.enterText(
    find.byKey(const ValueKey('auth.confirm-password')),
    next,
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('Login y cambio de clave no reutilizan los editores de texto', (
    tester,
  ) async {
    final api = ApiClient(
      client: MockClient((request) async {
        expect(request.url.path, '/api/v1/auth/login');
        return http.Response(
          jsonEncode({
            'access_token': 'test-session-token',
            'user': {
              'id': 1,
              'username': 'admin',
              'role': 'admin',
              'must_change_password': true,
            },
          }),
          200,
        );
      }),
    );
    await tester.pumpWidget(MotorDeskApp(api: api, initialize: false));
    final loginEditors = tester
        .stateList<EditableTextState>(find.byType(EditableText))
        .toSet();
    await tester.enterText(find.byType(TextFormField).at(0), 'admin');
    await tester.enterText(
      find.byType(TextFormField).at(1),
      'temporary-test-password',
    );
    await tester.tap(find.text('Entrar a mi espacio'));
    await tester.pumpAndSettle();
    expect(find.text('Protege tu cuenta'), findsOneWidget);
    final passwordEditors = tester.stateList<EditableTextState>(
      find.byType(EditableText),
    );
    expect(
      passwordEditors.every((editor) => !loginEditors.contains(editor)),
      isTrue,
      reason:
          'Cada fase necesita su propia conexión de entrada y contexto de autofill, especialmente en Web.',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('Una clave corta no bloquea borrar, sustituir ni confirmar', (
    tester,
  ) async {
    var requests = 0;
    await openPasswordForm(
      tester,
      authApi(
        changePassword: (_) async {
          requests++;
          return http.Response('{}', 400);
        },
      ),
    );
    await enterPasswordFields(tester, 'corta');
    await tester.ensureVisible(find.text('Guardar y continuar'));
    await tester.tap(find.text('Guardar y continuar'));
    await tester.pumpAndSettle();
    expect(find.text('Usa al menos 12 caracteres'), findsOneWidget);
    expect(requests, 0);
    for (final key in [
      'auth.current-password',
      'auth.new-password',
      'auth.confirm-password',
    ]) {
      expect(input(tester, key).readOnly, isFalse);
      await tester.enterText(find.byKey(ValueKey(key)), '');
      expect(input(tester, key).controller!.text, isEmpty);
    }
    await enterPasswordFields(tester, validPassword);
    expect(input(tester, 'auth.new-password').controller!.text, validPassword);
    expect(
      input(tester, 'auth.confirm-password').controller!.text,
      validPassword,
    );
    expect(
      input(tester, 'auth.new-password').autofillHints,
      contains(AutofillHints.newPassword),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Mostrar una contraseña conserva selección y no revela las otras',
    (tester) async {
      await openPasswordForm(tester, authApi());
      await enterPasswordFields(tester, validPassword);
      await tester.tap(find.byKey(const ValueKey('auth.new-password')));
      final controller = input(tester, 'auth.new-password').controller!;
      const selection = TextSelection(baseOffset: 1, extentOffset: 5);
      controller.selection = selection;
      await tester.pump();
      await tester.tap(find.byTooltip('Mostrar nueva contraseña'));
      await tester.pumpAndSettle();
      expect(input(tester, 'auth.new-password').obscureText, isFalse);
      expect(input(tester, 'auth.new-password').focusNode!.hasFocus, isTrue);
      expect(controller.selection, selection);
      expect(input(tester, 'auth.current-password').obscureText, isTrue);
      expect(input(tester, 'auth.confirm-password').obscureText, isTrue);
      await tester.enterText(
        find.byKey(const ValueKey('auth.new-password')),
        '',
      );
      expect(controller.text, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Tras un error del servidor se puede editar y reintentar sin doble envío',
    (tester) async {
      final response = Completer<http.Response>();
      var requests = 0;
      Json? requestBody;
      await openPasswordForm(
        tester,
        authApi(
          changePassword: (request) {
            requests++;
            requestBody = jsonDecode(request.body) as Json;
            return response.future;
          },
        ),
      );
      await enterPasswordFields(tester, validPassword);
      // Dos pulsaciones reales sobre el botón de la librería, no dos llamadas
      // al callback: así se comprueba que `loading` bloquea de verdad.
      final boton = find.text('Guardar y continuar');
      await tester.tap(boton);
      await tester.pump();
      await tester.tap(boton, warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 16));
      expect(requests, 1);
      expect(requestBody!['current_password'], temporaryPassword);
      expect(requestBody!.containsKey('confirmation'), isFalse);
      expect(input(tester, 'auth.new-password').readOnly, isTrue);
      response.complete(
        http.Response('{"detail":"Contraseña actual incorrecta"}', 400),
      );
      await tester.pumpAndSettle();
      expect(find.text('Contraseña actual incorrecta'), findsOneWidget);
      expect(input(tester, 'auth.current-password').readOnly, isFalse);
      expect(input(tester, 'auth.new-password').readOnly, isFalse);
      expect(
        input(tester, 'auth.new-password').controller!.text,
        validPassword,
      );
      await tester.enterText(
        find.byKey(const ValueKey('auth.new-password')),
        '',
      );
      expect(input(tester, 'auth.new-password').controller!.text, isEmpty);
      await enterPasswordFields(tester, '${validPassword}2');
      await tester.ensureVisible(find.text('Guardar y continuar'));
      await tester.tap(find.text('Guardar y continuar'));
      await tester.pumpAndSettle();
      expect(requests, 2);
      expect(input(tester, 'auth.new-password').readOnly, isFalse);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('La confirmación impide enviar contraseñas distintas', (
    tester,
  ) async {
    var requests = 0;
    await openPasswordForm(
      tester,
      authApi(
        changePassword: (_) async {
          requests++;
          return http.Response('{}', 400);
        },
      ),
    );
    await enterPasswordFields(tester, validPassword);
    await tester.enterText(
      find.byKey(const ValueKey('auth.confirm-password')),
      '${validPassword}other',
    );
    await tester.ensureVisible(find.text('Guardar y continuar'));
    await tester.tap(find.text('Guardar y continuar'));
    await tester.pumpAndSettle();
    expect(find.text('Las contraseñas no coinciden'), findsOneWidget);
    expect(requests, 0);
  });
}
