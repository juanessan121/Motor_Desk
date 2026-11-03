import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'autonomous_engine.dart';

typedef Json = Map<String, dynamic>;

class ApiException implements Exception {
  const ApiException(this.message, [this.statusCode = 0]);
  final String message;
  final int statusCode;
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({http.Client? client, String? baseUrl, this.autonomousMode = false})
    : _client = client ?? http.Client(),
      baseUrl = baseUrl ?? defaultBaseUrl;

  static String get defaultBaseUrl {
    const configured = String.fromEnvironment('API_BASE_URL');
    if (configured.isNotEmpty) return configured.replaceAll(RegExp(r'/$'), '');
    if (kIsWeb) {
      if (kDebugMode &&
          (Uri.base.host == 'localhost' || Uri.base.host == '127.0.0.1')) {
        return 'http://localhost:8000/api/v1';
      }
      return '${Uri.base.origin}/api/v1';
    }
    return kReleaseMode
        ? 'https://localhost/api/v1'
        : 'http://10.0.2.2:8000/api/v1';
  }

  final http.Client _client;
  final String baseUrl;
  String? token;
  String? deviceKey;
  http.Client? _eventClient;
  bool autonomousMode;

  /// Verifica de forma rápida y no bloqueante si el backend FastAPI/Docker
  /// responde en la dirección configurada.
  Future<bool> probeBackend({Duration timeout = const Duration(milliseconds: 900)}) async {
    try {
      final res = await _client
          .get(Uri.parse('$baseUrl/public/config'))
          .timeout(timeout);
      return res.statusCode < 500;
    } catch (_) {
      return false;
    }
  }

  Map<String, String> get headers => {
    'Accept': 'application/json',
    if (token != null) 'Authorization': 'Bearer $token',
    'X-Device-Id': ?deviceKey,
    if (Uri.parse(baseUrl).host.endsWith('.ngrok-free.dev'))
      'ngrok-skip-browser-warning': '1',
  };

  Future<dynamic> request(String method, String path, {Json? body}) async {
    if (autonomousMode) {
      return AutonomousWorkshopEngine.instance.dispatch(
        method,
        path,
        body: body,
      );
    }
    try {
      final request = http.Request(method, Uri.parse('$baseUrl$path'));
      request.headers.addAll({...headers, 'Content-Type': 'application/json'});
      if (body != null) request.body = jsonEncode(body);
      final response = await http.Response.fromStream(
        await _client.send(request).timeout(const Duration(seconds: 25)),
      ).timeout(const Duration(seconds: 25));
      _check(response.statusCode, response.body);
      return response.body.isEmpty ? null : jsonDecode(response.body);
    } on TimeoutException {
      throw const ApiException('La API tardó demasiado. Intente nuevamente.');
    } on http.ClientException {
      throw const ApiException(
        'No se pudo conectar con la API. Revise la URL, la red y CORS.',
      );
    } on FormatException {
      throw const ApiException(
        'La API devolvió una respuesta no válida. Revise API_BASE_URL.',
      );
    }
  }

  Future<Uint8List> download(String path) async {
    if (autonomousMode) {
      return Uint8List.fromList(utf8.encode('{}'));
    }
    final response = await _client
        .get(Uri.parse('$baseUrl$path'), headers: headers)
        .timeout(const Duration(seconds: 25));
    if (response.statusCode >= 400) _check(response.statusCode, response.body);
    return response.bodyBytes;
  }

  Future<Json> uploadPhoto(
    int orderId,
    Uint8List bytes,
    String filename, {
    int? taskId,
    int? inspectionId,
    int? findingId,
    int? expectedRevision,
  }) async {
    if (autonomousMode) {
      return {
        'id': DateTime.now().millisecondsSinceEpoch,
        'filename': filename,
        'url': '',
        'order_id': orderId,
        'created_at': DateTime.now().toUtc().toIso8601String(),
      };
    }
    final request =
        http.MultipartRequest(
            'POST',
            Uri.parse('$baseUrl/orders/$orderId/photos'),
          )
          ..headers.addAll(headers)
          ..files.add(
            http.MultipartFile.fromBytes('file', bytes, filename: filename),
          );
    if (taskId != null) request.fields['task_id'] = '$taskId';
    if (inspectionId != null) request.fields['inspection_id'] = '$inspectionId';
    if (findingId != null) request.fields['finding_id'] = '$findingId';
    if (expectedRevision != null) {
      request.fields['expected_revision'] = '$expectedRevision';
    }
    final response = await http.Response.fromStream(
      await _client.send(request),
    ).timeout(const Duration(seconds: 40));
    _check(response.statusCode, response.body);
    return jsonDecode(response.body) as Json;
  }

  Stream<Json> events() async* {
    if (autonomousMode) {
      yield* AutonomousWorkshopEngine.instance.eventsStream;
      return;
    }
    closeEvents();
    final client = http.Client();
    _eventClient = client;
    try {
      final request = http.Request('GET', Uri.parse('$baseUrl/events'))
        ..headers.addAll({...headers, 'Accept': 'text/event-stream'});
      final response = await client
          .send(request)
          .timeout(const Duration(seconds: 30));
      if (response.statusCode != 200) {
        throw ApiException(
          'Canal de eventos no disponible',
          response.statusCode,
        );
      }
      await for (final line
          in response.stream
              .transform(utf8.decoder)
              .transform(const LineSplitter())) {
        if (line.startsWith('data: ')) {
          yield jsonDecode(line.substring(6)) as Json;
        }
      }
    } finally {
      client.close();
      if (identical(_eventClient, client)) _eventClient = null;
    }
  }

  void _check(int code, String body) {
    if (code < 400) return;
    String message = 'Error del servidor ($code)';
    try {
      final detail = (jsonDecode(body) as Json)['detail'];
      if (detail is String) message = detail;
      if (detail is List) {
        message = detail
            .map(
              (item) =>
                  '${(item['loc'] as List).skip(1).join('.')}: ${item['msg']}',
            )
            .join('\n');
      }
    } on FormatException {
      message = 'Respuesta inesperada del servidor ($code)';
    }
    throw ApiException(message, code);
  }

  void closeEvents() {
    _eventClient?.close();
    _eventClient = null;
  }

  void dispose() {
    closeEvents();
    _client.close();
  }
}
