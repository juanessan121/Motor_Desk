import 'package:app_web_1/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Login valida campos sin conectarse a una API', (tester) async {
    await tester.pumpWidget(const MotorDeskApp(initialize: false));
    expect(find.text('¡Bienvenido de nuevo!'), findsOneWidget);
    await tester.tap(find.text('Entrar a mi espacio'));
    await tester.pumpAndSettle();
    expect(find.text('Ingresa tu usuario'), findsOneWidget);
    expect(find.text('Ingresa tu contraseña'), findsOneWidget);
  });

  for (final size in [
    const Size(390, 844),
    const Size(1440, 1000),
    const Size(844, 390),
  ]) {
    testWidgets('Login responsivo en $size', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const MotorDeskApp(initialize: false));
      await tester.pumpAndSettle();
      expect(find.byType(TextFormField), findsNWidgets(2));
      expect(tester.takeException(), isNull);
    });
  }
}
