import 'dart:convert';

import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/features/notifications/notifications_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'maintenance_flow_test.dart' as fixture;

Json notification() => {
  'id': 7,
  'user_id': 2,
  'customer_id': 3,
  'recipient_name': 'Cliente de prueba',
  'email': 'cliente@example.com',
  'notification_channel': 'email',
  'telegram_chat_id': null,
  'kind': 'credentials',
  'channel': 'email',
  'status': 'pending',
  'effective_status': 'paused',
  'blocked_reason': 'Email / SMTP no conectado',
  'last_error': 'Email / SMTP no conectado',
  'attempts': 0,
  'can_retry': false,
  'created_at': '2026-10-22T10:00:00Z',
};

void main() {
  testWidgets('Cancelar no guarda la desvinculación de Telegram', (
    tester,
  ) async {
    var writes = 0;
    final row = {
      ...notification(),
      'telegram_chat_id': '123456789',
      'notification_channel': 'telegram',
    };
    final state = await fixture.mount(
      tester,
      const NotificationsPage(),
      respond: (request) async {
        if (request.method == 'PATCH' || request.method == 'DELETE') writes++;
        if (request.url.path.endsWith('/notification-settings'))
          return fixture.reply({
            'email_configured': false,
            'telegram_configured': false,
            'paused_count': 1,
          });
        if (request.url.path.endsWith('/notifications'))
          return fixture.reply([row]);
        return null;
      },
    );
    state.notifications = [row];
    state.notifyListeners();
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byTooltip('Editar contacto y canal'));
    await tester.tap(find.byTooltip('Editar contacto y canal'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byTooltip('Desvincular Telegram'));
    await tester.tap(find.byTooltip('Desvincular Telegram'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();
    expect(writes, 0);
    expect(state.notifications.single['telegram_chat_id'], '123456789');
  });
  for (final size in [const Size(390, 844), const Size(1440, 1000)]) {
    testWidgets(
      'Notificaciones pausadas y edición sin navegar a Clientes en $size',
      (tester) async {
        var settingsReads = 0, writes = 0;
        Json? sent;
        var row = notification();
        final state = await fixture.mount(
          tester,
          const NotificationsPage(),
          size: size,
          respond: (request) async {
            if (request.url.path.endsWith('/notification-settings')) {
              settingsReads++;
              return fixture.reply({
                'email_configured': false,
                'telegram_configured': false,
                'paused_count': 1,
              });
            }
            if (request.method == 'PATCH') {
              writes++;
              sent = jsonDecode(request.body) as Json;
              row = {...row, ...sent!};
              return fixture.reply({'customer_id': 3});
            }
            if (request.url.path.endsWith('/notifications')) {
              return fixture.reply([row]);
            }
            return null;
          },
        );
        state.notifications = [row];
        state.notifyListeners();
        await tester.pumpAndSettle();
        expect(find.text('En pausa'), findsOneWidget);
        expect(
          tester
              .widget<IconButton>(
                find.byWidgetPredicate(
                  (widget) =>
                      widget is IconButton &&
                      widget.tooltip == 'Reintentar envío',
                ),
              )
              .onPressed,
          isNull,
        );
        await tester.pump(const Duration(minutes: 3));
        expect(settingsReads, 1);
        expect(writes, 0);
        await tester.ensureVisible(find.byTooltip('Editar contacto y canal'));
        await tester.tap(find.byTooltip('Editar contacto y canal'));
        await tester.pumpAndSettle();
        expect(find.text('Contacto para notificaciones'), findsOneWidget);
        final field = find.byWidgetPredicate(
          (widget) =>
              widget is TextField &&
              widget.decoration?.labelText == 'Correo del cliente',
        );
        await tester.enterText(field, 'corregido@example.com');
        final telegram = find.byWidgetPredicate(
          (widget) =>
              widget is TextField &&
              widget.decoration?.labelText == 'Telegram Chat ID',
        );
        await tester.ensureVisible(telegram);
        await tester.enterText(telegram, '123456789');
        await tester.tap(find.text('Guardar'));
        await tester.pumpAndSettle();
        expect(writes, 1);
        expect(sent?['email'], 'corregido@example.com');
        expect(sent?['notification_channel'], 'email');
        expect(sent?['telegram_chat_id'], '123456789');
        expect(tester.takeException(), isNull);
      },
    );
  }
}
