import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/theme_controller.dart';
import '../models/entities.dart';
import '../network/api_client.dart';
import '../network/autonomous_engine.dart';

class WorkshopController extends ChangeNotifier {
  WorkshopController(this.api, this.theme) {
    _lastFeatures = Map.of(theme.config.features);
    theme.addListener(_configurationChanged);
  }
  final ApiClient api;
  final ThemeController theme;
  Json? user;
  List<Customer> customers = [];
  List<Vehicle> vehicles = [];
  List<MaintenanceCatalog> catalogs = [];
  List<WorkOrder> orders = [];
  List<Json> notifications = [];
  Json summary = {};
  bool loading = false;
  bool eventConnected = false;
  int dataRevision = 0;
  String? error;
  StreamSubscription<Json>? _events;
  Timer? _reconnect;
  Timer? _debounce;
  Future<void>? _refreshFuture;
  bool _refreshAgain = false;
  bool _refreshConfiguration = false;
  bool _configInvalidated = false;
  bool _eventsPaused = false;
  int _epoch = 0;
  int _retrySeconds = 2;
  bool _disposed = false;
  int _accessRevision = 0;
  int _loadSerial = 0;
  late Map<String, bool> _lastFeatures;
  DateTime? lastLoadedAt;
  static const customerPageSize = 20;
  static const _customerPaths = {'orders': '/orders', 'vehicles': '/vehicles', 'notifications': '/notifications'};
  final Map<String, int> _customerTargets = {};
  final Map<String, bool> _hasMore = {};
  final Set<String> _loadingMore = {};
  final Map<String, String> _moreErrors = {};

  int get sessionEpoch => _epoch;
  bool customerHasMore(String resource) => _hasMore[resource] ?? false;
  bool customerLoadingMore(String resource) => _loadingMore.contains(resource);
  String? customerPageError(String resource) => _moreErrors[resource];

  void _configurationChanged() {
    final next = theme.config.features;
    final changed = !mapEquals(_lastFeatures, next);
    _lastFeatures = Map.of(next);
    if (!isCustomer || !changed || _disposed) return;
    _accessRevision++;
    if (next['vehicles'] != true) vehicles = [];
    if (next['maintenance'] != true) {
      orders = [];
    } else {
      orders = orders.map((order) => WorkOrder({
        ...order.json,
        if (next['photos'] != true) 'photos': <dynamic>[],
        if (next['quotes'] != true) 'quotes': <dynamic>[],
      })).toList();
    }
    // Ningún texto ya cargado debe sobrevivir a una revocación granular.
    notifications = [];
    _hasMore.clear();
    _moreErrors.clear();
    dataRevision++;
    if (_refreshFuture != null) _refreshAgain = true;
    notifyListeners();
  }

  bool get signedIn => user != null;
  bool get isCustomer => user?['role'] == 'customer';
  bool get isAdmin => user?['role'] == 'admin';
  bool get isMechanic => user?['role'] == 'mechanic';
  bool get needsPassword => user?['must_change_password'] == true;
  // Solo para demostraciones compiladas expresamente; nunca se activa por
  // pérdida de conexión ni por preferencias antiguas del navegador.
  static const browserDemoEnabled = bool.fromEnvironment('ENABLE_BROWSER_DEMO');
  bool get isAutonomous => api.autonomousMode;

  Future<void> setAutonomousMode(bool value) async {
    if (value && !browserDemoEnabled) return;
    if (signedIn) await logout();
    api.autonomousMode = value;
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool('motordesk_autonomous_mode', value);
    notifyListeners();
    if (signedIn) {
      await refresh(configuration: true);
    } else {
      try {
        await theme.refresh(public: true);
      } catch (_) {}
    }
  }

  Future<void> resetAutonomousData() async {
    await AutonomousWorkshopEngine.instance.resetToSeeds();
    if (signedIn) {
      await refresh(configuration: true);
    }
  }

  Future<void> initialize() async {
    final preferences = await SharedPreferences.getInstance();
    var key = preferences.getString('installation_id');
    if (key == null) {
      final random = Random.secure();
      final bytes = List<int>.generate(16, (_) => random.nextInt(256));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      final hex = bytes
          .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
          .join();
      key =
          '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
      await preferences.setString('installation_id', key);
    }
    api.deviceKey = key;

    api.autonomousMode = browserDemoEnabled &&
        (preferences.getBool('motordesk_autonomous_mode') ?? false);
    await theme.initialize();
  }

  Future<void> login(String username, String password) async {
    final result =
        await api.request(
              'POST',
              '/auth/login',
              body: {'username': username, 'password': password},
            )
            as Json;
    api.token = result['access_token'] as String;
    user = result['user'] as Json;
    error = null;
    _epoch++;
    notifyListeners();
    if (!needsPassword) await _startSession();
  }

  Future<void> changePassword(String current, String next) async {
    final result =
        await api.request(
              'POST',
              '/auth/password',
              body: {'current_password': current, 'new_password': next},
            )
            as Json;
    api.token = result['access_token'] as String;
    user = result['user'] as Json;
    notifyListeners();
    await _startSession();
  }

  Future<void> _startSession() async {
    try {
      await theme.refresh();
      await refresh();
      _eventsPaused = false;
      _connectEvents();
    } catch (failure) {
      error = failure.toString();
      notifyListeners();
    }
  }

  Future<void> refresh({bool configuration = false}) {
    _refreshConfiguration |= configuration;
    if (_refreshFuture != null) {
      _refreshAgain = true;
      return _refreshFuture!;
    }
    final epoch = _epoch;
    late final Future<void> future;
    future =
        Future<void>(() async {
          do {
            final updateConfig = _refreshConfiguration;
            _refreshConfiguration = false;
            _refreshAgain = false;
            await _load(configuration: updateConfig);
          } while (_refreshAgain && signedIn && epoch == _epoch && !_disposed);
        }).whenComplete(() {
          if (identical(_refreshFuture, future)) _refreshFuture = null;
        });
    _refreshFuture = future;
    return future;
  }

  Future<List<Json>> _fetchPaged(String path) async {
    final records = <Json>[];
    while (true) {
      final batch = jsonList(
        await api.request(
          'GET',
          '$path${path.contains('?') ? '&' : '?'}limit=500&offset=${records.length}',
        ),
      );
      records.addAll(batch);
      if (batch.length < 500) return records;
    }
  }

  Future<({List<Json> rows, bool more})> _customerWindow(String path, int target) async {
    final rows = <Json>[];
    while (rows.length < target + 1) {
      final size = min(500, target + 1 - rows.length);
      final batch = jsonList(await api.request('GET', '$path?limit=$size&offset=${rows.length}'));
      rows.addAll(batch);
      if (batch.length < size) break;
    }
    return (rows: rows.take(target).toList(), more: rows.length > target);
  }

  Future<void> loadMoreCustomer(String resource) async {
    if (!isCustomer || loading || !customerHasMore(resource) || _loadingMore.contains(resource)) return;
    final path = _customerPaths[resource];
    if (path == null) return;
    final epoch = _epoch, access = _accessRevision, serial = _loadSerial;
    final current = switch (resource) {
      'orders' => orders.map((row) => row.json).toList(),
      'vehicles' => vehicles.map((row) => row.json).toList(),
      _ => notifications,
    };
    _loadingMore.add(resource);
    _moreErrors.remove(resource);
    notifyListeners();
    try {
      final batch = jsonList(await api.request('GET',
        '$path?limit=${customerPageSize + 1}&offset=${current.length}'));
      if (_disposed || epoch != _epoch || access != _accessRevision || serial != _loadSerial) return;
      final merged = {for (final row in current) row['id']: row};
      for (final row in batch.take(customerPageSize)) { merged[row['id']] = row; }
      final rows = merged.values.toList();
      switch (resource) {
        case 'orders': orders = rows.map(WorkOrder.new).toList();
        case 'vehicles': vehicles = rows.map(Vehicle.new).toList();
        default: notifications = rows;
      }
      _customerTargets[resource] = rows.length;
      _hasMore[resource] = batch.length > customerPageSize;
    } catch (failure) {
      if (!_disposed && epoch == _epoch && access == _accessRevision) {
        _moreErrors[resource] = failure.toString();
        if (failure is ApiException && failure.statusCode == 401) _clearSession();
      }
    } finally {
      if (!_disposed && epoch == _epoch) {
        _loadingMore.remove(resource);
        notifyListeners();
      }
    }
  }

  Future<void> _load({required bool configuration}) async {
    if (!signedIn || needsPassword) return;
    final epoch = _epoch;
    final serial = ++_loadSerial;
    loading = true;
    notifyListeners();
    try {
      if (configuration) await theme.refresh();
      if (epoch != _epoch || _disposed) return;
      final flags = theme.config;
      final access = _accessRevision;
      if (isCustomer) {
        final results = await Future.wait([
          if (flags.enabled('vehicles'))
            _customerWindow('/vehicles', _customerTargets['vehicles'] ?? customerPageSize)
          else Future.value((rows: <Json>[], more: false)),
          if (flags.enabled('maintenance'))
            _customerWindow('/orders', _customerTargets['orders'] ?? customerPageSize)
          else Future.value((rows: <Json>[], more: false)),
          _customerWindow('/notifications', _customerTargets['notifications'] ?? customerPageSize),
        ]);
        if (_disposed || epoch != _epoch || access != _accessRevision || serial != _loadSerial) return;
        vehicles = results[0].rows.map(Vehicle.new).toList();
        orders = results[1].rows.map(WorkOrder.new).toList();
        notifications = results[2].rows;
        for (final (index, resource) in ['vehicles', 'orders', 'notifications'].indexed) {
          _hasMore[resource] = results[index].more;
        }
        _moreErrors.clear();
        lastLoadedAt = DateTime.now().toUtc();
        dataRevision++;
        error = null;
        return;
      }
      final result = await Future.wait([
        if (isAdmin) _fetchPaged('/customers') else Future.value(<dynamic>[]),
        if (!isCustomer || flags.enabled('vehicles'))
          _fetchPaged(isAdmin ? '/vehicles?include_inactive=true' : '/vehicles')
        else
          Future.value(<dynamic>[]),
        if (isAdmin)
          api.request('GET', '/catalogs')
        else
          Future.value(<dynamic>[]),
        if (!isCustomer || flags.enabled('maintenance'))
          _fetchPaged('/orders')
        else
          Future.value(<dynamic>[]),
        api.request('GET', '/notifications?limit=500'),
        if (!isCustomer)
          api.request('GET', '/dashboard')
        else
          Future.value(<String, dynamic>{}),
      ]);
      if (epoch != _epoch) return;
      customers = jsonList(result[0]).map(Customer.new).toList();
      vehicles = jsonList(result[1]).map(Vehicle.new).toList();
      catalogs = jsonList(result[2]).map(MaintenanceCatalog.new).toList();
      orders = jsonList(result[3]).map(WorkOrder.new).toList();
      notifications = jsonList(result[4]);
      summary = result[5] as Json;
      dataRevision++;
      lastLoadedAt = DateTime.now().toUtc();
      error = null;
    } catch (failure) {
      if (epoch != _epoch) return;
      error = failure.toString();
      if (failure is ApiException && failure.statusCode == 401) _clearSession();
      rethrow;
    } finally {
      if (epoch == _epoch && !_disposed) {
        loading = false;
        notifyListeners();
      }
    }
  }

  Future<void> mutate(String method, String path, {Json? body}) async {
    await api.request(method, path, body: body);
    await refresh();
  }

  void _connectEvents() {
    if (!signedIn || needsPassword || _disposed || _eventsPaused) return;
    _events?.cancel();
    _events = api.events().listen(
      (event) {
        eventConnected = true;
        _retrySeconds = 2;
        notifyListeners();
        if (event['type'] == 'session') {
          _verifySession();
        } else {
          _configInvalidated |=
              event['type'] == 'config' || event['type'] == 'connected';
          _debounce?.cancel();
          _debounce = Timer(const Duration(milliseconds: 350), () {
            final updateConfig = _configInvalidated;
            _configInvalidated = false;
            refresh(configuration: updateConfig).catchError((Object _) {});
          });
        }
      },
      onError: (Object failure) {
        if (failure is ApiException && failure.statusCode == 401) {
          _clearSession();
        } else {
          _scheduleReconnect();
        }
      },
      onDone: _scheduleReconnect,
      cancelOnError: true,
    );
  }

  Future<void> _verifySession() async {
    try {
      user = await api.request('GET', '/auth/me') as Json;
      notifyListeners();
    } catch (_) {
      _clearSession();
    }
  }

  void _scheduleReconnect() {
    if (!signedIn || _disposed || _eventsPaused) return;
    eventConnected = false;
    notifyListeners();
    _reconnect?.cancel();
    _reconnect = Timer(Duration(seconds: _retrySeconds), _connectEvents);
    _retrySeconds = min(_retrySeconds * 2, 60);
  }

  void pauseEvents() {
    _eventsPaused = true;
    _reconnect?.cancel();
    _events?.cancel();
    api.closeEvents();
    eventConnected = false;
  }

  Future<void> resume() async {
    if (!signedIn || needsPassword) return;
    _eventsPaused = false;
    try {
      await refresh(configuration: true);
      _connectEvents();
    } catch (_) {}
  }

  Future<void> logout() async {
    try {
      if (!needsPassword) await api.request('POST', '/auth/logout');
    } finally {
      _clearSession();
      await theme.initialize();
    }
  }

  void _clearSession() {
    _epoch++;
    pauseEvents();
    _debounce?.cancel();
    api.token = null;
    user = null;
    customers = [];
    vehicles = [];
    catalogs = [];
    orders = [];
    notifications = [];
    summary = {};
    _accessRevision++;
    _customerTargets.clear();
    _hasMore.clear();
    _loadingMore.clear();
    _moreErrors.clear();
    lastLoadedAt = null;
    dataRevision++;
    loading = false;
    _refreshFuture = null;
    _refreshAgain = false;
    _refreshConfiguration = false;
    _configInvalidated = false;
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    theme.removeListener(_configurationChanged);
    _disposed = true;
    _epoch++;
    pauseEvents();
    _debounce?.cancel();
    api.dispose();
    super.dispose();
  }
}
