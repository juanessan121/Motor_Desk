import 'dart:convert';
import 'package:app_web_1/features/registry/customer_flow.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'maintenance_flow_test.dart' as fixture;

void main() {
  for (final size in [const Size(390, 844), const Size(1440, 1000)]) {
    testWidgets(
      'Nuevo cliente continúa con su vehículo y recepción en $size; cancelar conserva ambos',
      (tester) async {
        final customers = <Map<String, dynamic>>[];
        final vehicles = <Map<String, dynamic>>[];
        var writes = 0;
        await fixture.mount(
          tester,
          Builder(
            builder: (context) => TextButton(
              onPressed: () => startCustomerFlow(context),
              child: const Text('Comenzar'),
            ),
          ),
          size: size,
          respond: (request) async {
            final path = request.url.path;
            if (path.endsWith('/customers')) {
              if (request.method == 'POST') {
                writes++;
                final row = <String, dynamic>{
                  ...jsonDecode(request.body) as Map<String, dynamic>,
                  'id': 71,
                  'full_name': 'Ana Prueba',
                };
                customers.add(row);
                return fixture.reply(row, 201);
              }
              return fixture.reply(customers);
            }
            if (path.endsWith('/vehicles')) {
              if (request.method == 'POST') {
                writes++;
                final row = <String, dynamic>{
                  ...jsonDecode(request.body) as Map<String, dynamic>,
                  'id': 82,
                  'owner_name': 'Ana Prueba',
                  'active': true,
                };
                vehicles.add(row);
                return fixture.reply(row, 201);
              }
              return fixture.reply(vehicles);
            }
            return null;
          },
        );
        Future<void> fill(String label, String value) async {
          final field = find.byWidgetPredicate(
            (w) => w is TextField && w.decoration?.labelText == label,
          );
          await tester.ensureVisible(field);
          await tester.enterText(field, value);
        }

        await tester.tap(find.text('Comenzar'));
        await tester.pumpAndSettle();
        await fill('Cédula / identificación', '1234567890');
        await fill('Nombre', 'Ana');
        await fill('Apellido', 'Prueba');
        await fill('Correo electrónico', 'ana@example.test');
        await tester.tap(find.text('Guardar y continuar al vehículo'));
        await tester.pumpAndSettle();
        expect(find.text('Paso 2 de 3 · Ingresar vehículo'), findsOneWidget);
        await fill('Placa / matrícula', 'ABC1234');
        await fill('Marca', 'Marca');
        await fill('Modelo', 'Modelo');
        await tester.tap(find.text('Guardar y continuar a la orden'));
        await tester.pumpAndSettle();
        expect(vehicles.single['owner_id'], 71);
        expect(find.text('Paso 3 de 3 · Servicios y orden'), findsOneWidget);
        expect(find.textContaining('ABC1234'), findsWidgets);
        expect(writes, 2);
        await tester.tap(find.text('Cancelar').last);
        await tester.pumpAndSettle();
        expect(customers, hasLength(1));
        expect(vehicles, hasLength(1));
        expect(writes, 2);
      },
    );
  }
  testWidgets('Cancelar el primer paso no abre vehículo', (tester) async {
    await fixture.mount(
      tester,
      Builder(
        builder: (context) => TextButton(
          onPressed: () => startCustomerFlow(context),
          child: const Text('Comenzar'),
        ),
      ),
    );
    await tester.tap(find.text('Comenzar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();
    expect(find.text('Paso 2 de 3 · Ingresar vehículo'), findsNothing);
  });
}
