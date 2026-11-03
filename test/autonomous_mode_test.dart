import 'dart:convert';

import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/network/autonomous_engine.dart';
import 'package:app_web_1/core/state/workshop_controller.dart';
import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Motor Autónomo (Sin Docker/API)', () {
    late ApiClient api;
    late AutonomousWorkshopEngine engine;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      engine = AutonomousWorkshopEngine.instance;
      await engine.resetToSeeds();
      api = ApiClient(autonomousMode: true);
    });

    test('Obtener configuración inicial y temas sin backend', () async {
      final config = await api.request('GET', '/config') as Json;
      expect(config['schema_version'], 1);
      expect((config['branding'] as Map)['name'], 'MotorDesk');
    });

    test('Login autónomo para administrador, mecánico y cliente', () async {
      // 1. Admin
      final adminLogin = await api.request(
        'POST',
        '/auth/login',
        body: {'username': 'admin', 'password': 'any'},
      ) as Json;
      expect(adminLogin['access_token'], isNotEmpty);
      expect((adminLogin['user'] as Json)['role'], 'admin');

      // 2. Mecánico
      final mechLogin = await api.request(
        'POST',
        '/auth/login',
        body: {'username': 'carlos.mecanico', 'password': 'any'},
      ) as Json;
      expect((mechLogin['user'] as Json)['role'], 'mechanic');

      // 3. Cliente
      final custLogin = await api.request(
        'POST',
        '/auth/login',
        body: {'username': 'patricio.mendez', 'password': 'any'},
      ) as Json;
      expect((custLogin['user'] as Json)['role'], 'customer');
    });

    test('Listar y crear clientes de forma autónoma', () async {
      final initial = await api.request('GET', '/customers') as List;
      expect(initial.length, greaterThanOrEqualTo(2));

      final created = await api.request('POST', '/customers', body: {
        'cedula_ruc': '1723456789',
        'first_name': 'Andrés',
        'last_name': 'Pérez',
        'email': 'aperez@correo.ec',
        'whatsapp': '+593987112233',
        'has_portal_access': true,
      }) as Json;

      expect(created['name'], 'Andrés Pérez');
      expect(created['portal_access_status'], 'pendiente_activacion');

      final updatedList = await api.request('GET', '/customers') as List;
      expect(updatedList.length, initial.length + 1);
    });

    test('Listar vehículos y catálogo de plantillas', () async {
      final vehicles = await api.request('GET', '/vehicles') as List;
      expect(vehicles.isNotEmpty, isTrue);
      expect(vehicles.first['plate'], isNotNull);

      final catalogs = await api.request('GET', '/catalogs') as List;
      expect(catalogs.isNotEmpty, isTrue);
      expect(catalogs.first['tasks'], isNotNull);
    });

    test('Crear orden con checklist híbrido y actualizar ítem', () async {
      final createdOrder = await api.request('POST', '/orders', body: {
        'vehicle_id': 1,
        'maintenance_type': 'preventivo',
        'mileage': 45200,
        'included_tasks': [
          'Cambio de aceite y filtro',
          'Inspección de frenos',
          'Revisión de suspensión personalizada',
        ],
        'symptoms': 'Ruido leve al frenar',
        'technical_diagnosis': 'Desgaste moderado en pastillas',
        'notes': 'Cliente espera en sala',
        'mechanic_id': 2,
        'priority': 'normal',
      }) as Json;

      expect(createdOrder['id'], isNotNull);
      final items = createdOrder['items'] as List;
      expect(items.length, 3);
      expect(items.first['status'], 'pending');

      // Actualizar estado de ítem a completed
      final orderId = createdOrder['id'] as int;
      final patched = await api.request('PATCH', '/orders/$orderId', body: {
        'items': [
          {
            ...items[0] as Map,
            'status': 'completed',
            'completed': true,
          },
          items[1],
          items[2],
        ],
      }) as Json;

      expect(patched['progress'], closeTo(0.33, 0.05));
    });

    test('Consultar plano del taller y bahías', () async {
      final layout = await api.request('GET', '/workshop/layout') as Json;
      expect(layout['bays'], isNotEmpty);
      expect(layout['width'], 920);

      final mechanicView =
          await api.request('GET', '/workshop/mechanic-view') as Json;
      expect(mechanicView['bays'], isNotNull);
    });

    test('Gestión de actividades reutilizables y notificaciones', () async {
      final acts = await api.request('GET', '/activities') as List;
      expect(acts.length, greaterThanOrEqualTo(8));

      final notifs = await api.request('GET', '/notifications') as List;
      expect(notifs.isNotEmpty, isTrue);

      final cleanup = await api.request('POST', '/notifications/cleanup') as Json;
      expect(cleanup['status'], 'success');
    });

    test('WorkshopController integra modo autónomo con reactividad', () async {
      final theme = ThemeController(api);
      final workshop = WorkshopController(api, theme);

      expect(workshop.isAutonomous, isTrue);
      await workshop.login('admin', 'admin123');
      expect(workshop.signedIn, isTrue);
      expect(workshop.isAdmin, isTrue);
      expect(workshop.customers.isNotEmpty, isTrue);
      expect(workshop.vehicles.isNotEmpty, isTrue);
      expect(workshop.orders.isNotEmpty, isTrue);
      expect(workshop.catalogs.isNotEmpty, isTrue);

      workshop.dispose();
      theme.dispose();
    });
  });
}
