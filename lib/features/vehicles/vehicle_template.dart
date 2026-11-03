import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';

class VehiclePoint {
  const VehiclePoint({
    required this.id,
    required this.componentId,
    required this.x,
    required this.y,
  });
  final String id;
  final String componentId;
  final double x;
  final double y;
}

class VehicleView {
  VehicleView(this.json);
  final Json json;
  String get id => json['id'] as String;
  String get label => json['label'] as String;
  String get asset => json['asset'] as String;
  Size get intrinsic => Size(number(json['width']), number(json['height']));
  bool get passport => json['passport'] == true;
  List<VehiclePoint> get points => [
    for (final row in jsonList(json['hotspots']))
      VehiclePoint(
        id: '$id:${row['componentId']}',
        componentId: row['componentId'] as String,
        x: number(row['xNormalized']),
        y: number(row['yNormalized']),
      ),
  ];
}

class VehicleTemplate {
  VehicleTemplate(this.json);
  final Json json;
  String get id => json['id'] as String;
  List<Json> get components => jsonList(json['components']);
  List<VehicleView> get views =>
      jsonList(json['views']).map(VehicleView.new).toList();
  String label(String id) =>
      components.where((row) => row['id'] == id).firstOrNull?['label']
          as String? ??
      id;
  static Future<List<VehicleTemplate>>? _cache;
  static Future<List<VehicleTemplate>> load() => _cache ??= _read();
  static Future<List<VehicleTemplate>> _read() async {
    final data =
        jsonDecode(
              await rootBundle.loadString(
                'backend/app/resources/vehicle_templates.json',
              ),
            )
            as Json;
    return jsonList(data['templates']).map(VehicleTemplate.new).toList();
  }
}

Rect renderedImageRect(Size viewport, Size intrinsic) {
  final fitted = applyBoxFit(BoxFit.contain, intrinsic, viewport);
  return Alignment.center.inscribe(fitted.destination, Offset.zero & viewport);
}

Offset markerCenter(Rect image, double x, double y) =>
    Offset(image.left + x * image.width, image.top + y * image.height);

Offset? normalizedPosition(Rect image, Offset scene) {
  if (!image.contains(scene) || image.width == 0 || image.height == 0) {
    return null;
  }
  return Offset(
    ((scene.dx - image.left) / image.width).clamp(0, 1),
    ((scene.dy - image.top) / image.height).clamp(0, 1),
  );
}
