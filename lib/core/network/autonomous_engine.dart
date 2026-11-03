import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

/// Motor autónomo de ejecución local para MotorDesk.
///
/// Permite ejecutar la aplicación al 100% en modo autónomo directamente en el
/// navegador (o cualquier entorno Flutter) SIN necesidad de tener un servidor
/// FastAPI, Python o contenedores Docker en ejecución.
///
/// Implementa emulación completa de las rutas `/api/v1/*`, persistencia local
/// mediante [SharedPreferences], ciclo de vida de órdenes con checklist híbrido,
/// gestión de bahías, notificaciones, vehículos y clientes.
class AutonomousWorkshopEngine {
  AutonomousWorkshopEngine._();
  static final AutonomousWorkshopEngine instance = AutonomousWorkshopEngine._();

  bool _initialized = false;
  final StreamController<Json> _eventsController =
      StreamController<Json>.broadcast();

  Stream<Json> get eventsStream => _eventsController.stream;

  // Estado en memoria
  late Map<String, dynamic> _config;
  late List<Json> _users;
  late List<Json> _customers;
  late List<Json> _vehicles;
  late List<Json> _catalogs;
  late List<Json> _activities;
  late List<Json> _orders;
  late List<Json> _bays;
  late List<Json> _notifications;
  late Map<String, dynamic> _deliverySettings;

  int _customerSeq = 10;
  int _vehicleSeq = 10;
  int _orderSeq = 10;
  int _itemSeq = 500;
  int _activitySeq = 20;
  int _baySeq = 10;

  Json? _currentUser;

  Future<void> initialize() async {
    if (_initialized) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final cached = prefs.getString('motordesk_autonomous_db_v2');

      if (cached != null) {
        final db = jsonDecode(cached) as Map<String, dynamic>;
        _config = Map<String, dynamic>.from(db['config'] as Map? ?? _seedConfig);
        _users = List<Json>.from(db['users'] as List? ?? _seedUsers);
        _customers = List<Json>.from(db['customers'] as List? ?? _seedCustomers);
        _vehicles = List<Json>.from(db['vehicles'] as List? ?? _seedVehicles);
        _catalogs = List<Json>.from(db['catalogs'] as List? ?? _seedCatalogs);
        _activities = List<Json>.from(db['activities'] as List? ?? _seedActivities);
        _orders = List<Json>.from(db['orders'] as List? ?? _seedOrders);
        _bays = List<Json>.from(db['bays'] as List? ?? _seedBays);
        _notifications =
            List<Json>.from(db['notifications'] as List? ?? _seedNotifications);
        _deliverySettings = Map<String, dynamic>.from(
          db['deliverySettings'] as Map? ?? _seedDeliverySettings,
        );
        _initialized = true;
        return;
      }
    } catch (e) {
      debugPrint('[AutonomousEngine] SharedPreferences no disponible o vacío: $e');
    }

    _loadSeedData();
    _initialized = true;
  }

  void _loadSeedData() {
    _config = Map<String, dynamic>.from(_seedConfig);
    _users = List<Json>.from(_seedUsers.map((u) => Map<String, dynamic>.from(u)));
    _customers = List<Json>.from(
      _seedCustomers.map((c) => Map<String, dynamic>.from(c)),
    );
    _vehicles = List<Json>.from(
      _seedVehicles.map((v) => Map<String, dynamic>.from(v)),
    );
    _catalogs = List<Json>.from(
      _seedCatalogs.map((cat) => Map<String, dynamic>.from(cat)),
    );
    _activities = List<Json>.from(
      _seedActivities.map((a) => Map<String, dynamic>.from(a)),
    );
    _orders = List<Json>.from(_seedOrders.map((o) => Map<String, dynamic>.from(o)));
    _bays = List<Json>.from(_seedBays.map((b) => Map<String, dynamic>.from(b)));
    _notifications = List<Json>.from(
      _seedNotifications.map((n) => Map<String, dynamic>.from(n)),
    );
    _deliverySettings = Map<String, dynamic>.from(_seedDeliverySettings);
  }

  Future<void> resetToSeeds() async {
    _loadSeedData();
    await _persist();
    _emitEvent('reset', {});
  }

  Future<void> _persist() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final payload = jsonEncode({
        'config': _config,
        'users': _users,
        'customers': _customers,
        'vehicles': _vehicles,
        'catalogs': _catalogs,
        'activities': _activities,
        'orders': _orders,
        'bays': _bays,
        'notifications': _notifications,
        'deliverySettings': _deliverySettings,
      });
      await prefs.setString('motordesk_autonomous_db_v2', payload);
    } catch (e) {
      debugPrint('[AutonomousEngine] Falló persistencia local: $e');
    }
  }

  void _emitEvent(String type, Json data) {
    _eventsController.add({
      'type': type,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
      'data': data,
    });
  }

  /// Despacha una solicitud REST hacia el motor autónomo en memoria.
  Future<dynamic> dispatch(String method, String fullPath, {Json? body}) async {
    await initialize();
    final uri = Uri.parse(fullPath.startsWith('/') ? fullPath : '/$fullPath');
    final path = uri.path;
    final query = uri.queryParameters;

    // 1. Configuración y temas
    if (path == '/config' || path == '/public/config') {
      if (method == 'GET') return Map<String, dynamic>.from(_config);
      if (method == 'PUT' || method == 'PATCH') {
        if (body != null) {
          _config.addAll(body);
          await _persist();
          _emitEvent('config', _config);
        }
        return Map<String, dynamic>.from(_config);
      }
    }
    if (path == '/config/global') {
      if (body != null) {
        _config.addAll(body);
        await _persist();
        _emitEvent('config', _config);
      }
      return Map<String, dynamic>.from(_config);
    }

    // 2. Autenticación
    if (path == '/auth/login' && method == 'POST') {
      final u = (body?['username'] as String? ?? '').trim().toLowerCase();
      // En modo autónomo, permitimos ingresar de forma flexible con usuarios estándar
      Json matched;
      if (u.contains('mecanic') || u.contains('carlos')) {
        matched = _users.firstWhere((x) => x['role'] == 'mechanic');
      } else if (u.contains('client') || u.contains('patricio')) {
        matched = _users.firstWhere((x) => x['role'] == 'customer');
      } else {
        matched = _users.firstWhere(
          (x) => x['username'].toString().toLowerCase() == u,
          orElse: () => _users.firstWhere((x) => x['role'] == 'admin'),
        );
      }
      _currentUser = matched;
      return {
        'access_token': 'autonomous-token-${matched['username']}',
        'token_type': 'bearer',
        'user': matched,
      };
    }

    if (path == '/auth/me' && method == 'GET') {
      return _currentUser ?? _users.firstWhere((x) => x['role'] == 'admin');
    }

    if (path == '/auth/logout' && method == 'POST') {
      _currentUser = null;
      return {'message': 'Sesión cerrada exitosamente'};
    }

    if (path == '/auth/password' && method == 'POST') {
      final user = _currentUser ?? _users.first;
      user['must_change_password'] = false;
      await _persist();
      return {
        'access_token': 'autonomous-token-${user['username']}',
        'token_type': 'bearer',
        'user': user,
      };
    }

    // 3. Clientes
    if (path == '/customers') {
      if (method == 'GET') {
        return _customers.map((c) => Map<String, dynamic>.from(c)).toList();
      }
      if (method == 'POST') {
        final id = ++_customerSeq;
        final newCustomer = <String, dynamic>{
          'id': id,
          'cedula_ruc': body?['cedula_ruc'] ?? '179000${id}001',
          'first_name': body?['first_name'] ?? body?['nombre'] ?? '',
          'last_name': body?['last_name'] ?? body?['apellido'] ?? '',
          'name':
              '${body?['first_name'] ?? ''} ${body?['last_name'] ?? ''}'.trim(),
          'email': body?['email'] ?? 'cliente$id@correo.ec',
          'phone': body?['phone'] ?? body?['telefono'] ?? '09900000$id',
          'telefono': body?['phone'] ?? body?['telefono'] ?? '09900000$id',
          'whatsapp': body?['whatsapp'] ?? '',
          'address': body?['address'] ?? body?['direccion'] ?? 'Quito, Ecuador',
          'direccion': body?['address'] ?? body?['direccion'] ?? 'Quito, Ecuador',
          'notes': body?['notes'] ?? '',
          'active': true,
          'notification_channel': body?['notification_channel'] ?? 'whatsapp',
          'email_notifications_enabled':
              body?['email_notifications_enabled'] ?? true,
          'whatsapp_notifications_enabled':
              body?['whatsapp_notifications_enabled'] ?? true,
          'telegram_notifications_enabled':
              body?['telegram_notifications_enabled'] ?? false,
          'telegram_chat_id': body?['telegram_chat_id'],
          'has_portal_access': body?['has_portal_access'] ?? false,
          'portal_access_status': body?['has_portal_access'] == true
              ? 'pendiente_activacion'
              : 'sin_cuenta',
        };
        _customers.insert(0, newCustomer);
        await _persist();
        _emitEvent('customers', newCustomer);
        return newCustomer;
      }
    }

    final customerMatch = RegExp(r'^/customers/(\d+)$').firstMatch(path);
    if (customerMatch != null) {
      final cid = int.parse(customerMatch.group(1)!);
      final idx = _customers.indexWhere((c) => c['id'] == cid);
      if (idx == -1) throw ApiException('Cliente no encontrado', 404);

      if (method == 'GET') return Map<String, dynamic>.from(_customers[idx]);
      if (method == 'PATCH' || method == 'PUT') {
        if (body != null) {
          _customers[idx].addAll(body);
          if (body.containsKey('first_name') || body.containsKey('last_name')) {
            _customers[idx]['name'] =
                '${_customers[idx]['first_name']} ${_customers[idx]['last_name']}'
                    .trim();
          }
          await _persist();
          _emitEvent('customers', _customers[idx]);
        }
        return Map<String, dynamic>.from(_customers[idx]);
      }
      if (method == 'DELETE') {
        _customers[idx]['active'] = false;
        await _persist();
        return {'status': 'archived'};
      }
    }

    // 4. Vehículos
    if (path == '/vehicles') {
      if (method == 'GET') {
        final ownerId = query['owner_id'] != null
            ? int.tryParse(query['owner_id']!)
            : null;
        var list = _vehicles;
        if (ownerId != null) {
          list = list.where((v) => v['owner_id'] == ownerId).toList();
        }
        if (query['include_inactive'] != 'true') {
          list = list.where((v) => v['active'] != false).toList();
        }
        return list.map((v) => Map<String, dynamic>.from(v)).toList();
      }
      if (method == 'POST') {
        final id = ++_vehicleSeq;
        final ownerId = body?['owner_id'] as int?;
        final owner = _customers.where((c) => c['id'] == ownerId).firstOrNull;
        final newVehicle = <String, dynamic>{
          'id': id,
          'plate': (body?['plate'] ?? 'ABC-00$id').toString().toUpperCase(),
          'brand': body?['brand'] ?? body?['make'] ?? 'Genérica',
          'model': body?['model'] ?? 'Estándar',
          'year': body?['year'] ?? 2022,
          'vin': body?['vin'] ?? 'VIN-AUTONOMOUS-$id',
          'color': body?['color'] ?? 'Plata',
          'fuel_type': body?['fuel_type'] ?? 'gasolina',
          'mileage': body?['mileage'] ?? 20000,
          'notes': body?['notes'] ?? '',
          'active': true,
          'owner_id': ownerId,
          'owner_name': owner?['name'] ?? 'Propietario Demo',
        };
        _vehicles.insert(0, newVehicle);
        await _persist();
        _emitEvent('vehicles', newVehicle);
        return newVehicle;
      }
    }

    final vehicleMatch = RegExp(r'^/vehicles/(\d+)$').firstMatch(path);
    if (vehicleMatch != null) {
      final vid = int.parse(vehicleMatch.group(1)!);
      final idx = _vehicles.indexWhere((v) => v['id'] == vid);
      if (idx == -1) throw ApiException('Vehículo no encontrado', 404);

      if (method == 'GET') return Map<String, dynamic>.from(_vehicles[idx]);
      if (method == 'PATCH' || method == 'PUT') {
        if (body != null) {
          _vehicles[idx].addAll(body);
          await _persist();
          _emitEvent('vehicles', _vehicles[idx]);
        }
        return Map<String, dynamic>.from(_vehicles[idx]);
      }
    }

    final suggestionsMatch =
        RegExp(r'^/vehicles/(\d+)/maintenance-suggestions$').firstMatch(path);
    if (suggestionsMatch != null && method == 'GET') {
      return {
        'items': _catalogs.map((c) => Map<String, dynamic>.from(c)).toList(),
      };
    }

    final passportMatch = RegExp(r'^/vehicles/(\d+)/passport$').firstMatch(path);
    if (passportMatch != null && method == 'GET') {
      final vid = int.parse(passportMatch.group(1)!);
      final v = _vehicles.where((x) => x['id'] == vid).firstOrNull;
      final vehicleOrders = _orders.where((o) => o['vehicle_id'] == vid).toList();
      return {
        'vehicle': v,
        'orders_count': vehicleOrders.length,
        'orders': vehicleOrders,
        'inspections': <dynamic>[],
      };
    }

    // 5. Catálogo de plantillas (MaintenanceCatalog)
    if (path == '/catalogs') {
      if (method == 'GET') {
        return _catalogs.map((c) => Map<String, dynamic>.from(c)).toList();
      }
      if (method == 'POST') {
        final id = _catalogs.length + 1;
        final cat = <String, dynamic>{
          'id': id,
          'name': body?['name'] ?? 'Nueva Plantilla',
          'description': body?['description'] ?? '',
          'base_price': body?['base_price']?.toString() ?? '50.00',
          'active': true,
          'revision': 1,
          'price_configured': true,
          'interval_km': body?['interval_km'],
          'tasks': body?['tasks'] ?? <dynamic>[],
        };
        _catalogs.add(cat);
        await _persist();
        _emitEvent('catalogs', cat);
        return cat;
      }
    }

    final catalogMatch = RegExp(r'^/catalogs/(\d+)$').firstMatch(path);
    if (catalogMatch != null) {
      final cid = int.parse(catalogMatch.group(1)!);
      final idx = _catalogs.indexWhere((c) => c['id'] == cid);
      if (idx == -1) throw ApiException('Plantilla no encontrada', 404);
      if (method == 'GET') return Map<String, dynamic>.from(_catalogs[idx]);
      if (method == 'PATCH' || method == 'PUT') {
        if (body != null) {
          _catalogs[idx].addAll(body);
          _catalogs[idx]['revision'] = (_catalogs[idx]['revision'] as int? ?? 1) + 1;
          await _persist();
          _emitEvent('catalogs', _catalogs[idx]);
        }
        return Map<String, dynamic>.from(_catalogs[idx]);
      }
    }

    // 6. Catálogo central de actividades reutilizables (MaintenanceActivity)
    if (path == '/activities') {
      if (method == 'GET') {
        return _activities.map((a) => Map<String, dynamic>.from(a)).toList();
      }
      if (method == 'POST') {
        final id = ++_activitySeq;
        final act = <String, dynamic>{
          'id': id,
          'name': body?['name'] ?? 'Actividad personalizada',
          'system': body?['system'] ?? 'general',
          'description': body?['description'] ?? '',
          'estimated_duration_min': body?['estimated_duration_min'] ?? 30,
          'technical_notes': body?['technical_notes'] ?? '',
          'active': body?['active'] ?? true,
        };
        _activities.insert(0, act);
        await _persist();
        _emitEvent('activities', act);
        return act;
      }
    }

    if (path == '/activities/seed-standard' && method == 'POST') {
      return {
        'message': 'Catálogo estándar disponible',
        'count': _activities.length,
      };
    }

    final activityMatch = RegExp(r'^/activities/(\d+)$').firstMatch(path);
    if (activityMatch != null) {
      final aid = int.parse(activityMatch.group(1)!);
      final idx = _activities.indexWhere((a) => a['id'] == aid);
      if (idx == -1) throw ApiException('Actividad no encontrada', 404);
      if (method == 'PATCH' || method == 'PUT') {
        if (body != null) {
          _activities[idx].addAll(body);
          await _persist();
          _emitEvent('activities', _activities[idx]);
        }
        return Map<String, dynamic>.from(_activities[idx]);
      }
    }

    // 7. Órdenes de trabajo (WorkOrder & Checklist Híbrido)
    if (path == '/orders') {
      if (method == 'GET') {
        return _orders.map((o) => Map<String, dynamic>.from(o)).toList();
      }
      if (method == 'POST') {
        final id = ++_orderSeq;
        final vid = body?['vehicle_id'] as int?;
        final vehicle = _vehicles.where((v) => v['id'] == vid).firstOrNull;
        final includedTasks = (body?['included_tasks'] as List?)?.cast<String>() ??
            ['Revisión general de seguridad'];

        final items = <Json>[];
        for (final label in includedTasks) {
          items.add({
            'id': ++_itemSeq,
            'label': label,
            'status': 'pending',
            'completed': false,
            'required': true,
            'revision': 1,
            'notes': '',
            'responsible_ids': body?['mechanic_id'] != null
                ? [body?['mechanic_id'] as int]
                : [2],
            'suggested_part_ids': <int>[],
          });
        }

        final newOrder = <String, dynamic>{
          'id': id,
          'vehicle_id': vid,
          'customer_id': body?['customer_id'] ?? vehicle?['owner_id'],
          'title': body?['title'] ??
              'Mantenimiento ${body?['maintenance_type'] ?? 'Preventivo'}',
          'plate': vehicle?['plate'] ?? 'ABC-1234',
          'vehicle_name':
              '${vehicle?['brand'] ?? 'Vehículo'} ${vehicle?['model'] ?? ''}'.trim(),
          'status': 'in_progress',
          'operational_stage': 'assigned',
          'base_approval': 'approved',
          'progress': 0.0,
          'revision': 1,
          'priority': body?['priority'] ?? 'normal',
          'created_at': DateTime.now().toUtc().toIso8601String(),
          'mileage': body?['mileage'] ?? vehicle?['mileage'] ?? 10000,
          'symptoms': body?['symptoms'] ?? body?['problem_description'] ?? '',
          'problem_description':
              body?['problem_description'] ?? body?['symptoms'] ?? '',
          'technical_diagnosis': body?['technical_diagnosis'] ?? '',
          'notes': body?['notes'] ?? '',
          'delay_reason': null,
          'mechanic_id': body?['mechanic_id'] ?? 2,
          'items': items,
          'templates': [
            for (final catId in (body?['catalog_ids'] as List? ?? [1]))
              {
                'id': catId,
                'name': _catalogs
                        .where((c) => c['id'] == catId)
                        .firstOrNull?['name'] ??
                    'Mantenimiento',
                'revision': 1,
              },
          ],
          'quotes': <dynamic>[
            {
              'id': id,
              'labor': '40.00',
              'parts': '35.00',
              'subtotal': '75.00',
              'tax_rate': '0.15',
              'tax_amount': '11.25',
              'total': '86.25',
              'status': 'approved',
            },
          ],
          'photos': <dynamic>[],
          'capabilities': {
            'manage': true,
            'assign': true,
            'inspect': true,
            'upload': true,
            'quote': true,
          },
        };

        _orders.insert(0, newOrder);
        await _persist();
        _emitEvent('orders', newOrder);
        return newOrder;
      }
    }

    final orderMatch = RegExp(r'^/orders/(\d+)$').firstMatch(path);
    if (orderMatch != null) {
      final oid = int.parse(orderMatch.group(1)!);
      final idx = _orders.indexWhere((o) => o['id'] == oid);
      if (idx == -1) throw ApiException('Orden de trabajo no encontrada', 404);

      if (method == 'GET') return Map<String, dynamic>.from(_orders[idx]);
      if (method == 'PATCH' || method == 'PUT') {
        if (body != null) {
          final target = _orders[idx];
          if (body.containsKey('status')) target['status'] = body['status'];
          if (body.containsKey('operational_stage')) {
            target['operational_stage'] = body['operational_stage'];
          }
          if (body.containsKey('priority')) target['priority'] = body['priority'];
          if (body.containsKey('delay_reason')) {
            target['delay_reason'] = body['delay_reason'];
          }
          if (body.containsKey('notes')) target['notes'] = body['notes'];
          if (body.containsKey('symptoms')) target['symptoms'] = body['symptoms'];
          if (body.containsKey('technical_diagnosis')) {
            target['technical_diagnosis'] = body['technical_diagnosis'];
          }

          // Actualización de ítems del checklist operativo
          if (body.containsKey('items')) {
            target['items'] = body['items'];
          } else if (body.containsKey('task_id') ||
              body.containsKey('expected_revision')) {
            // Actualización granular de ítem
            final items = List<Json>.from(target['items'] as List? ?? []);
            for (final it in items) {
              if (body['status'] != null) {
                it['status'] = body['status'];
                it['completed'] = body['status'] == 'completed';
              }
            }
            target['items'] = items;
          }

          // Recalcular progreso
          final items = target['items'] as List? ?? [];
          if (items.isNotEmpty) {
            final done =
                items.where((it) => (it as Map)['status'] == 'completed').length;
            target['progress'] = done / items.length;
          }

          target['revision'] = (target['revision'] as int? ?? 1) + 1;
          await _persist();
          _emitEvent('orders', target);
        }
        return Map<String, dynamic>.from(_orders[idx]);
      }
    }

    // 8. Bahías y plano del taller
    if (path == '/workshop/layout' && method == 'GET') {
      return {
        'bays': _bays.map((b) => Map<String, dynamic>.from(b)).toList(),
        'width': 920,
        'height': 600,
        'scale': 1.0,
      };
    }

    if (path == '/workshop/mechanic-view' && method == 'GET') {
      // Para mecánicos, devuelve bahías asignadas a sus órdenes
      final mechId = _currentUser?['id'] ?? 2;
      final myOrders = _orders
          .where((o) => o['mechanic_id'] == mechId)
          .map((o) => o['id'])
          .toSet();
      final filtered = _bays.where((b) {
        final aOrderId = b['assigned_order_id'];
        return aOrderId != null && myOrders.contains(aOrderId);
      }).toList();
      return {
        'bays': filtered.map((b) => Map<String, dynamic>.from(b)).toList(),
        'assigned_orders_count': myOrders.length,
      };
    }

    if (path == '/workshop/bays') {
      if (method == 'GET') {
        return _bays.map((b) => Map<String, dynamic>.from(b)).toList();
      }
      if (method == 'POST') {
        final id = ++_baySeq;
        final bay = <String, dynamic>{
          'id': id,
          'name': body?['name'] ?? 'Bahía $id',
          'zone': body?['zone'] ?? 'mecanica_rapida',
          'status': 'available',
          'x': body?['x'] ?? 100,
          'y': body?['y'] ?? 100,
          'width': body?['width'] ?? 220,
          'height': body?['height'] ?? 140,
          'assigned_order_id': null,
        };
        _bays.add(bay);
        await _persist();
        _emitEvent('workshop', bay);
        return bay;
      }
    }

    final bayAssignMatch = RegExp(r'^/workshop/bays/(\d+)/assign$').firstMatch(path);
    if (bayAssignMatch != null && method == 'POST') {
      final bid = int.parse(bayAssignMatch.group(1)!);
      final idx = _bays.indexWhere((b) => b['id'] == bid);
      if (idx != -1) {
        _bays[idx]['assigned_order_id'] = body?['order_id'];
        _bays[idx]['status'] = 'occupied';
        await _persist();
        _emitEvent('workshop', _bays[idx]);
        return _bays[idx];
      }
    }

    final bayVacateMatch = RegExp(r'^/workshop/bays/(\d+)/vacate$').firstMatch(path);
    if (bayVacateMatch != null && method == 'POST') {
      final bid = int.parse(bayVacateMatch.group(1)!);
      final idx = _bays.indexWhere((b) => b['id'] == bid);
      if (idx != -1) {
        _bays[idx]['assigned_order_id'] = null;
        _bays[idx]['status'] = 'available';
        await _persist();
        _emitEvent('workshop', _bays[idx]);
        return _bays[idx];
      }
    }

    // 9. Personal y Mecánicos
    if (path == '/staff/mechanics' && method == 'GET') {
      return [
        {
          'id': 2,
          'username': 'carlos.mecanico',
          'full_name': 'Carlos Mendoza',
          'role': 'mechanic',
        },
        {
          'id': 3,
          'username': 'roberto.mecanico',
          'full_name': 'Roberto Vaca',
          'role': 'mechanic',
        },
      ];
    }

    // 10. Notificaciones
    if (path == '/notifications') {
      if (method == 'GET') {
        return _notifications.map((n) => Map<String, dynamic>.from(n)).toList();
      }
    }

    if (path == '/notifications/recipients' && method == 'GET') {
      return _customers.map((c) => {
            'id': c['id'],
            'name': c['name'],
            'email': c['email'],
            'whatsapp': c['whatsapp'],
            'telegram_chat_id': c['telegram_chat_id'],
            'notification_channel': c['notification_channel'] ?? 'whatsapp',
            'email_enabled': c['email_notifications_enabled'] ?? true,
            'whatsapp_enabled': c['whatsapp_notifications_enabled'] ?? true,
            'telegram_enabled': c['telegram_notifications_enabled'] ?? false,
          }).toList();
    }

    if (path == '/notifications/delivery-settings') {
      if (method == 'GET') return Map<String, dynamic>.from(_deliverySettings);
      if (method == 'PUT' || method == 'PATCH') {
        if (body != null) {
          _deliverySettings.addAll(body);
          await _persist();
        }
        return Map<String, dynamic>.from(_deliverySettings);
      }
    }

    if (path == '/notifications/cleanup' && method == 'POST') {
      var count = 0;
      for (final n in _notifications) {
        if (n['status'] == 'dismissed' || n['archivado'] == true) {
          n['cleaned'] = true;
          count++;
        }
      }
      await _persist();
      return {'cleaned': count, 'status': 'success'};
    }

    if (path == '/notifications/archive-cleaned' && method == 'POST') {
      final initial = _notifications.length;
      _notifications.removeWhere((n) => n['cleaned'] == true);
      final removed = initial - _notifications.length;
      await _persist();
      return {'archived': removed, 'remaining': _notifications.length};
    }

    // 11. Dashboard
    if (path == '/dashboard' && method == 'GET') {
      final inProgress =
          _orders.where((o) => o['status'] == 'in_progress').length;
      final occupiedBays = _bays.where((b) => b['status'] == 'occupied').length;
      return {
        'vehicles_in_shop': _vehicles.length,
        'orders_in_progress': inProgress,
        'orders_pending_approval': 0,
        'ready_for_delivery': 0,
        'occupancy_rate': _bays.isEmpty ? 0.0 : occupiedBays / _bays.length,
        'bays_occupied': occupiedBays,
        'bays_total': _bays.length,
      };
    }

    // 12. Catálogo automotriz de marcas y modelos
    if (path == '/catalog/makes' && method == 'GET') {
      return _catalogMakes;
    }
    if (path == '/catalog/models' && method == 'GET') {
      final make = query['make']?.toLowerCase() ?? '';
      return _catalogModels[make] ?? _catalogModels['toyota'] ?? [];
    }

    // Fallback: objeto vacío o lista vacía según corresponda
    return <String, dynamic>{};
  }

  // --- SEMILLAS Y DATOS DEMO PREDETERMINADOS ---
  static const _seedConfig = {
    'schema_version': 1,
    'theme_key': 'pitlane',
    'branding': {
      'name': 'MotorDesk',
      'tagline': 'Tu taller, conectado.',
      'welcome': 'Cuidamos lo que te mueve',
      'logo': '',
      'colors': {
        'primary': '#2563EB',
        'secondary': '#0D9488',
        'background': '#F4F6FA',
        'surface': '#FFFFFF',
      },
      'theme': 'pitlane',
    },
    'features': {
      'vehicles': true,
      'maintenance': true,
      'quotes': true,
      'photos': true,
      'history': true,
    },
    'regional': {
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
    },
    'theme': <String, String>{},
    'revision': 1,
  };

  static const _seedUsers = [
    {
      'id': 1,
      'username': 'admin',
      'role': 'admin',
      'email': 'admin@motordesk.local',
      'must_change_password': false,
    },
    {
      'id': 2,
      'username': 'carlos.mecanico',
      'role': 'mechanic',
      'email': 'carlos@motordesk.local',
      'must_change_password': false,
    },
    {
      'id': 4,
      'username': 'patricio.mendez',
      'role': 'customer',
      'email': 'pmendez@correo.ec',
      'must_change_password': false,
    },
  ];

  static const _seedCustomers = [
    {
      'id': 1,
      'cedula_ruc': '1712345678',
      'first_name': 'Patricio',
      'last_name': 'Méndez',
      'name': 'Patricio Méndez',
      'email': 'pmendez@correo.ec',
      'phone': '0992345678',
      'telefono': '0992345678',
      'whatsapp': '+593992345678',
      'address': 'Av. Amazonas y Colón, Quito',
      'direccion': 'Av. Amazonas y Colón, Quito',
      'notes': 'Cliente corporativo frecuente',
      'active': true,
      'notification_channel': 'whatsapp',
      'email_notifications_enabled': true,
      'whatsapp_notifications_enabled': true,
      'telegram_notifications_enabled': true,
      'telegram_chat_id': '987654321',
      'has_portal_access': true,
      'portal_access_status': 'activo',
    },
    {
      'id': 2,
      'cedula_ruc': '0923456789',
      'first_name': 'María Elena',
      'last_name': 'Salazar',
      'name': 'María Elena Salazar',
      'email': 'mesalazar@correo.ec',
      'phone': '0987654321',
      'telefono': '0987654321',
      'whatsapp': '+593987654321',
      'address': 'Cumbayá, Sector San Juan',
      'direccion': 'Cumbayá, Sector San Juan',
      'notes': 'Solicita siempre repuestos originales',
      'active': true,
      'notification_channel': 'email',
      'email_notifications_enabled': true,
      'whatsapp_notifications_enabled': true,
      'telegram_notifications_enabled': false,
      'telegram_chat_id': null,
      'has_portal_access': false,
      'portal_access_status': 'sin_cuenta',
    },
    {
      'id': 3,
      'cedula_ruc': '1709876543',
      'first_name': 'Roberto Carlos',
      'last_name': 'Gómez',
      'name': 'Roberto Carlos Gómez',
      'email': 'rgomez@correo.ec',
      'phone': '0998765432',
      'telefono': '0998765432',
      'whatsapp': '+593998765432',
      'address': 'La Floresta, Calle Madrid',
      'direccion': 'La Floresta, Calle Madrid',
      'notes': 'Prefiere avisos matutinos',
      'active': true,
      'notification_channel': 'email',
      'email_notifications_enabled': true,
      'whatsapp_notifications_enabled': false,
      'telegram_notifications_enabled': false,
      'telegram_chat_id': null,
      'has_portal_access': true,
      'portal_access_status': 'pendiente_activacion',
    },
  ];

  static const _seedVehicles = [
    {
      'id': 1,
      'plate': 'PBX-4589',
      'brand': 'Toyota',
      'model': 'Hilux 2.8 D-4D',
      'year': 2022,
      'vin': '8AJBA3CD4NE123456',
      'color': 'Plata Metálico',
      'fuel_type': 'diesel',
      'mileage': 45200,
      'active': true,
      'owner_id': 1,
      'owner_name': 'Patricio Méndez',
      'notes': 'Uso mixto ciudad y carretera',
    },
    {
      'id': 2,
      'plate': 'GSB-7821',
      'brand': 'Hyundai',
      'model': 'Tucson 2.0',
      'year': 2021,
      'vin': 'KMHJT81CBDU654321',
      'color': 'Blanco Nieve',
      'fuel_type': 'gasolina',
      'mileage': 38500,
      'active': true,
      'owner_id': 2,
      'owner_name': 'María Elena Salazar',
      'notes': 'Todos los mantenimientos en taller',
    },
    {
      'id': 3,
      'plate': 'PCY-3210',
      'brand': 'Chevrolet',
      'model': 'D-Max 3.0 CRDI',
      'year': 2023,
      'vin': '8M1TFS85JNN654321',
      'color': 'Gris Oscuro',
      'fuel_type': 'diesel',
      'mileage': 18400,
      'active': true,
      'owner_id': 3,
      'owner_name': 'Roberto Carlos Gómez',
      'notes': 'Vehículo utilitario de carga',
    },
  ];

  static const _seedCatalogs = [
    {
      'id': 1,
      'name': 'Mantenimiento preventivo básico',
      'description':
          'Servicio programado básico de fluidos e inspección visual de seguridad.',
      'base_price': '45.00',
      'active': true,
      'revision': 1,
      'price_configured': true,
      'interval_km': 5000,
      'schedule_source': 'Recomendación fabricante',
      'tasks': [
        'Cambio de aceite y filtro de motor',
        'Inspección de frenos y pastillas',
        'Revisión de niveles de refrigerante y frenos',
        'Inspección visual de neumáticos y suspensión',
      ],
      'task_details': [
        {
          'label': 'Cambio de aceite y filtro de motor',
          'required': true,
          'estimated_minutes': 30,
        },
        {
          'label': 'Inspección de frenos y pastillas',
          'required': true,
          'estimated_minutes': 20,
        },
        {
          'label': 'Revisión de niveles de refrigerante y frenos',
          'required': true,
          'estimated_minutes': 15,
        },
        {
          'label': 'Inspección visual de neumáticos y suspensión',
          'required': false,
          'estimated_minutes': 15,
        },
      ],
    },
    {
      'id': 2,
      'name': 'Mantenimiento preventivo completo (40.000 / 80.000 km)',
      'description':
          'Servicio integral con cambio de filtros, bujías y chequeo de sistemas críticos.',
      'base_price': '115.00',
      'active': true,
      'revision': 1,
      'price_configured': true,
      'interval_km': 40000,
      'schedule_source': 'Programa de servicio mayor',
      'tasks': [
        'Cambio de aceite y filtro de motor',
        'Cambio de filtro de aire y de cabina',
        'Sustitución de filtro de combustible',
        'Revisión de pastillas y discos de freno',
        'Diagnóstico computarizado OBD-II',
        'Rotación y calibración de neumáticos',
        'Alineación y balanceo 3D',
      ],
      'task_details': [
        {
          'label': 'Cambio de aceite y filtro de motor',
          'required': true,
          'estimated_minutes': 30,
        },
        {
          'label': 'Cambio de filtro de aire y de cabina',
          'required': true,
          'estimated_minutes': 20,
        },
        {
          'label': 'Sustitución de filtro de combustible',
          'required': true,
          'estimated_minutes': 35,
        },
        {
          'label': 'Revisión de pastillas y discos de freno',
          'required': true,
          'estimated_minutes': 25,
        },
        {
          'label': 'Diagnóstico computarizado OBD-II',
          'required': true,
          'estimated_minutes': 20,
        },
        {
          'label': 'Rotación y calibración de neumáticos',
          'required': false,
          'estimated_minutes': 20,
        },
        {
          'label': 'Alineación y balanceo 3D',
          'required': false,
          'estimated_minutes': 40,
        },
      ],
    },
    {
      'id': 3,
      'name': 'Diagnóstico general computarizado',
      'description':
          'Escaneo electrónico de módulos ECU, ABS, Airbag y prueba de actuadores.',
      'base_price': '35.00',
      'active': true,
      'revision': 1,
      'price_configured': true,
      'interval_km': 10000,
      'schedule_source': 'Diagnóstico bajo demanda',
      'tasks': [
        'Escaneo computarizado OBD-II',
        'Lectura y borrado de códigos DTC',
        'Prueba de batería y alternador',
        'Inspección de sensores de motor',
      ],
      'task_details': [
        {
          'label': 'Escaneo computarizado OBD-II',
          'required': true,
          'estimated_minutes': 20,
        },
        {
          'label': 'Lectura y borrado de códigos DTC',
          'required': true,
          'estimated_minutes': 15,
        },
        {
          'label': 'Prueba de batería y alternador',
          'required': true,
          'estimated_minutes': 15,
        },
        {
          'label': 'Inspección de sensores de motor',
          'required': false,
          'estimated_minutes': 20,
        },
      ],
    },
    {
      'id': 4,
      'name': 'Mantenimiento correctivo de frenos y suspensión',
      'description':
          'Reparación de sistema de frenado y componentes de tren delantero/trasero.',
      'base_price': '75.00',
      'active': true,
      'revision': 1,
      'price_configured': true,
      'interval_km': null,
      'schedule_source': 'Reparación correctiva',
      'tasks': [
        'Cambio de pastillas de freno delanteras',
        'Rectificación o cambio de discos',
        'Inspección de terminales de dirección y rótulas',
        'Revisión de amortiguadores y bujes',
      ],
      'task_details': [
        {
          'label': 'Cambio de pastillas de freno delanteras',
          'required': true,
          'estimated_minutes': 30,
        },
        {
          'label': 'Rectificación o cambio de discos',
          'required': false,
          'estimated_minutes': 45,
        },
        {
          'label': 'Inspección de terminales de dirección y rótulas',
          'required': true,
          'estimated_minutes': 25,
        },
        {
          'label': 'Revisión de amortiguadores y bujes',
          'required': false,
          'estimated_minutes': 30,
        },
      ],
    },
  ];

  static const _seedActivities = [
    {
      'id': 1,
      'name': 'Cambio de aceite y filtro de motor',
      'system': 'motor',
      'description': 'Drenado de lubricante usado y sustitución de filtro.',
      'estimated_duration_min': 30,
      'active': true,
      'technical_notes': 'Verificar viscosidad y norma API/ACEA recomendada.',
    },
    {
      'id': 2,
      'name': 'Revisión de pastillas y discos de freno',
      'system': 'frenos',
      'description': 'Medición de espesor de material de fricción y discos.',
      'estimated_duration_min': 25,
      'active': true,
      'technical_notes': 'Reemplazar si el espesor es menor a 2.5 mm.',
    },
    {
      'id': 3,
      'name': 'Inspección de suspensión y rótulas',
      'system': 'suspension',
      'description': 'Revisión de holguras en terminales, rótulas y axiales.',
      'estimated_duration_min': 35,
      'active': true,
      'technical_notes': 'Detectar ruidos metálicos y desgaste en bujes.',
    },
    {
      'id': 4,
      'name': 'Diagnóstico computarizado OBD-II',
      'system': 'electrico',
      'description': 'Conexión a puerto de diagnosis para lectura en vivo.',
      'estimated_duration_min': 20,
      'active': true,
      'technical_notes': 'Guardar historial de códigos DTC antes de borrar.',
    },
    {
      'id': 5,
      'name': 'Revisión y purga de líquido de frenos',
      'system': 'fluidos',
      'description': 'Medición de punto de ebullición y humedad en fluido.',
      'estimated_duration_min': 25,
      'active': true,
      'technical_notes': 'Humedad mayor a 3% requiere cambio completo DOT 4.',
    },
    {
      'id': 6,
      'name': 'Inspección y carga de batería / alternador',
      'system': 'electrico',
      'description': 'Prueba de arranque y prueba de diodos de carga.',
      'estimated_duration_min': 15,
      'active': true,
      'technical_notes': 'Tensión óptima: entre 13.8V y 14.4V.',
    },
    {
      'id': 7,
      'name': 'Alineación y balanceo 3D',
      'system': 'direccion',
      'description': 'Ajuste de convergencia, divergencia y camber.',
      'estimated_duration_min': 45,
      'active': true,
      'technical_notes': 'Comprobar desgaste irregular en banda de rodadura.',
    },
    {
      'id': 8,
      'name': 'Limpieza de cuerpo de aceleración e inyectores',
      'system': 'motor',
      'description': 'Descarbonización de mariposa y prueba de caudal.',
      'estimated_duration_min': 50,
      'active': true,
      'technical_notes': 'Realizar reaprendizaje de ralentí tras la limpieza.',
    },
  ];

  static const _seedOrders = [
    {
      'id': 1,
      'vehicle_id': 1,
      'customer_id': 1,
      'title': 'Mantenimiento preventivo 45.000 km',
      'plate': 'PBX-4589',
      'vehicle_name': 'Toyota Hilux 2.8 D-4D',
      'status': 'in_progress',
      'operational_stage': 'in_progress',
      'base_approval': 'approved',
      'progress': 0.66,
      'revision': 2,
      'priority': 'normal',
      'mileage': 45200,
      'symptoms':
          'Mantenimiento periódico programado por kilometraje. Ruido leve en tren delantero.',
      'problem_description':
          'Mantenimiento periódico programado por kilometraje. Ruido leve en tren delantero.',
      'technical_diagnosis':
          'Pastillas de freno con 30% de vida útil restante. Filtro de combustible saturado.',
      'notes': 'Cliente autorizó cambio de pastillas de freno y filtro adicional.',
      'delay_reason': 'Espera de pastillas originales en bodega central',
      'mechanic_id': 2,
      'created_at': '2026-10-22T10:00:00Z',
      'items': [
        {
          'id': 101,
          'label': 'Cambio de aceite y filtro de motor',
          'status': 'completed',
          'completed': true,
          'required': true,
          'revision': 1,
          'notes': 'Completado con 5W-30 sintético',
          'responsible_ids': [2],
          'suggested_part_ids': <int>[],
        },
        {
          'id': 102,
          'label': 'Sustitución de pastillas de freno delanteras',
          'status': 'in_progress',
          'completed': false,
          'required': true,
          'revision': 1,
          'notes': 'Instalando pastillas cerámicas',
          'responsible_ids': [2],
          'suggested_part_ids': <int>[],
        },
        {
          'id': 103,
          'label': 'Inspección de suspensión y rótulas',
          'status': 'pending',
          'completed': false,
          'required': false,
          'revision': 1,
          'notes': 'Pendiente de prueba en fosa',
          'responsible_ids': [2],
          'suggested_part_ids': <int>[],
        },
      ],
      'quotes': [
        {
          'id': 1,
          'labor': '80.00',
          'parts': '55.00',
          'subtotal': '135.00',
          'tax_rate': '0.15',
          'tax_amount': '20.25',
          'total': '155.25',
          'status': 'approved',
        },
      ],
      'photos': <dynamic>[],
      'templates': [
        {'id': 1, 'name': 'Mantenimiento preventivo básico', 'revision': 1},
      ],
      'capabilities': {
        'manage': true,
        'assign': true,
        'inspect': true,
        'upload': true,
        'quote': true,
      },
    },
    {
      'id': 2,
      'vehicle_id': 2,
      'customer_id': 2,
      'title': 'Diagnóstico de sistema eléctrico y encendido',
      'plate': 'GSB-7821',
      'vehicle_name': 'Hyundai Tucson 2.0',
      'status': 'in_progress',
      'operational_stage': 'diagnosis',
      'base_approval': 'approved',
      'progress': 0.33,
      'revision': 1,
      'priority': 'urgent',
      'mileage': 38500,
      'symptoms':
          'Dificultad de encendido en frío y testigo Check Engine intermitente.',
      'problem_description':
          'Dificultad de encendido en frío y testigo Check Engine intermitente.',
      'technical_diagnosis':
          'Batería con 11.8V en reposo. Código DTC P0300 aleatorio registrado.',
      'notes': 'Revisar bujías de iridio y alternador.',
      'delay_reason': null,
      'mechanic_id': 2,
      'created_at': '2026-10-22T11:30:00Z',
      'items': [
        {
          'id': 201,
          'label': 'Diagnóstico computarizado OBD-II',
          'status': 'completed',
          'completed': true,
          'required': true,
          'revision': 1,
          'notes': 'Código P0300 detectado',
          'responsible_ids': [2],
          'suggested_part_ids': <int>[],
        },
        {
          'id': 202,
          'label': 'Prueba de batería y sistema de carga',
          'status': 'in_progress',
          'completed': false,
          'required': true,
          'revision': 1,
          'notes': 'Medición de caída de tensión',
          'responsible_ids': [2],
          'suggested_part_ids': <int>[],
        },
        {
          'id': 203,
          'label': 'Inspección de bujías y bobinas',
          'status': 'pending',
          'completed': false,
          'required': true,
          'revision': 1,
          'notes': '',
          'responsible_ids': [2],
          'suggested_part_ids': <int>[],
        },
      ],
      'quotes': <dynamic>[],
      'photos': <dynamic>[],
      'templates': [
        {'id': 3, 'name': 'Diagnóstico general computarizado', 'revision': 1},
      ],
      'capabilities': {
        'manage': true,
        'assign': true,
        'inspect': true,
        'upload': true,
        'quote': true,
      },
    },
  ];

  static const _seedBays = [
    {
      'id': 1,
      'name': 'Bahía 1 (Elevador 1)',
      'zone': 'mecanica_rapida',
      'status': 'occupied',
      'x': 120,
      'y': 150,
      'width': 220,
      'height': 140,
      'assigned_order_id': 1,
      'order_title': 'Toyota Hilux (PBX-4589)',
    },
    {
      'id': 2,
      'name': 'Bahía 2 (Elevador 2)',
      'zone': 'mecanica_rapida',
      'status': 'occupied',
      'x': 380,
      'y': 150,
      'width': 220,
      'height': 140,
      'assigned_order_id': 2,
      'order_title': 'Hyundai Tucson (GSB-7821)',
    },
    {
      'id': 3,
      'name': 'Bahía 3 (Alineación y balanceo)',
      'zone': 'diagnostico',
      'status': 'available',
      'x': 120,
      'y': 340,
      'width': 220,
      'height': 140,
      'assigned_order_id': null,
    },
    {
      'id': 4,
      'name': 'Bahía 4 (Mantenimiento general)',
      'zone': 'mantenimiento_pesado',
      'status': 'available',
      'x': 380,
      'y': 340,
      'width': 220,
      'height': 140,
      'assigned_order_id': null,
    },
    {
      'id': 5,
      'name': 'Bahía 5 (Lavado y entrega)',
      'zone': 'entrega',
      'status': 'available',
      'x': 640,
      'y': 240,
      'width': 200,
      'height': 160,
      'assigned_order_id': null,
    },
  ];

  static const _seedNotifications = [
    {
      'id': 1,
      'orden_id': 1,
      'destinatario': '+593992345678',
      'canal': 'whatsapp',
      'evento_tipo': 'reception',
      'asunto': 'Recepción de vehículo - MotorDesk',
      'body':
          'Estimado/a Patricio Méndez, confirmamos la recepción de su Toyota Hilux (PBX-4589). Orden OT-2026-0001 generada con éxito.',
      'mensaje':
          'Estimado/a Patricio Méndez, confirmamos la recepción de su Toyota Hilux (PBX-4589). Orden OT-2026-0001 generada con éxito.',
      'status': 'sent',
      'estado': 'sent',
      'created_at': '2026-10-22T10:05:00Z',
      'archivado': false,
    },
    {
      'id': 2,
      'orden_id': 1,
      'destinatario': 'pmendez@correo.ec',
      'canal': 'email',
      'evento_tipo': 'vehicle_ready',
      'asunto': 'Vehículo listo para retiro - MotorDesk',
      'body':
          'Estimado/a Patricio Méndez, su vehículo placa PBX-4589 está listo para entrega. Puede retirarlo en nuestro taller. Total: \$155.25.',
      'mensaje':
          'Estimado/a Patricio Méndez, su vehículo placa PBX-4589 está listo para entrega. Puede retirarlo en nuestro taller. Total: \$155.25.',
      'status': 'sent',
      'estado': 'sent',
      'created_at': '2026-10-22T14:30:00Z',
      'archivado': false,
    },
    {
      'id': 3,
      'orden_id': 1,
      'destinatario': 'pmendez@correo.ec',
      'canal': 'email',
      'evento_tipo': 'payment_info',
      'asunto': 'Liquidación y detalle de pago - MotorDesk',
      'body':
          'Orden OT-2026-0001: Mano de obra \$80.00, Repuestos \$55.00, IVA 15% \$20.25. Total final \$155.25.',
      'mensaje':
          'Orden OT-2026-0001: Mano de obra \$80.00, Repuestos \$55.00, IVA 15% \$20.25. Total final \$155.25.',
      'status': 'sent',
      'estado': 'sent',
      'created_at': '2026-10-22T14:32:00Z',
      'archivado': false,
    },
  ];

  static const _seedDeliverySettings = {
    'email_enabled': true,
    'whatsapp_enabled': true,
    'telegram_enabled': true,
  };

  static const _catalogMakes = [
    {'name': 'Toyota', 'slug': 'toyota', 'logo_url': ''},
    {'name': 'Hyundai', 'slug': 'hyundai', 'logo_url': ''},
    {'name': 'Chevrolet', 'slug': 'chevrolet', 'logo_url': ''},
    {'name': 'Ford', 'slug': 'ford', 'logo_url': ''},
    {'name': 'Nissan', 'slug': 'nissan', 'logo_url': ''},
    {'name': 'Kia', 'slug': 'kia', 'logo_url': ''},
    {'name': 'Volkswagen', 'slug': 'volkswagen', 'logo_url': ''},
    {'name': 'Renault', 'slug': 'renault', 'logo_url': ''},
  ];

  static const _catalogModels = {
    'toyota': [
      {'name': 'Hilux 2.8 D-4D', 'year_from': 2016, 'year_to': 2024},
      {'name': 'Fortuner 4.0 V6', 'year_from': 2017, 'year_to': 2024},
      {'name': 'Corolla 1.8 Dual VVT-i', 'year_from': 2014, 'year_to': 2023},
      {'name': 'RAV4 2.5 Híbrido', 'year_from': 2019, 'year_to': 2024},
    ],
    'hyundai': [
      {'name': 'Tucson 2.0', 'year_from': 2016, 'year_to': 2023},
      {'name': 'Santa Fe 2.4', 'year_from': 2015, 'year_to': 2022},
      {'name': 'Creta 1.6', 'year_from': 2018, 'year_to': 2024},
      {'name': 'Accent 1.4', 'year_from': 2012, 'year_to': 2021},
    ],
    'chevrolet': [
      {'name': 'D-Max 3.0 CRDI', 'year_from': 2015, 'year_to': 2024},
      {'name': 'Sail 1.5', 'year_from': 2016, 'year_to': 2022},
      {'name': 'Tracker 1.2 Turbo', 'year_from': 2020, 'year_to': 2024},
      {'name': 'Captiva 1.5 Turbo', 'year_from': 2019, 'year_to': 2023},
    ],
  };
}
