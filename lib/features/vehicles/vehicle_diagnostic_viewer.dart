import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/network/api_client.dart';
import 'vehicle_template.dart';

class VehicleDiagnosticViewer extends StatefulWidget {
  const VehicleDiagnosticViewer({
    super.key,
    required this.template,
    required this.view,
    required this.states,
    required this.onPoint,
    this.points,
    this.onPosition,
    this.height = 430,
  });
  final VehicleTemplate template;
  final VehicleView view;
  final Json states;
  final ValueChanged<VehiclePoint> onPoint;
  final List<VehiclePoint>? points;
  final ValueChanged<Offset>? onPosition;
  final double height;
  @override
  State<VehicleDiagnosticViewer> createState() =>
      _VehicleDiagnosticViewerState();
}

class _VehicleDiagnosticViewerState extends State<VehicleDiagnosticViewer> {
  final transform = TransformationController();
  @override
  void didUpdateWidget(covariant VehicleDiagnosticViewer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.view.id != widget.view.id) {
      transform.value = Matrix4.identity();
    }
  }

  @override
  void dispose() {
    transform.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Container(
    height: widget.height,
    decoration: BoxDecoration(
      color:
          Theme.of(context).extension<AtelierTokens>()?.diagnostic ??
          const Color(0xFF101B28),
      borderRadius: BorderRadius.circular(18),
    ),
    clipBehavior: Clip.antiAlias,
    child: LayoutBuilder(
      builder: (context, constraints) {
        final viewport = Size(constraints.maxWidth, constraints.maxHeight);
        final image = renderedImageRect(viewport, widget.view.intrinsic);
        return Stack(
          children: [
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapUp: widget.onPosition == null
                  ? null
                  : (details) {
                      final normalized = normalizedPosition(
                        image,
                        transform.toScene(details.localPosition),
                      );
                      if (normalized != null) widget.onPosition!(normalized);
                    },
              child: InteractiveViewer(
                transformationController: transform,
                minScale: 1,
                maxScale: 4,
                boundaryMargin: const EdgeInsets.all(30),
                child: SizedBox.fromSize(
                  size: viewport,
                  child: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      Positioned.fromRect(
                        rect: image,
                        child: ExcludeSemantics(
                          child: widget.view.asset.endsWith('.svg')
                              ? SvgPicture.asset(
                                  widget.view.asset,
                                  fit: BoxFit.contain,
                                )
                              : Image.asset(
                                  widget.view.asset,
                                  fit: BoxFit.contain,
                                ),
                        ),
                      ),
                      for (final point in widget.points ?? widget.view.points)
                        _marker(context, image, point),
                    ],
                  ),
                ),
              ),
            ),
            Positioned(
              top: 8,
              right: 8,
              child: IconButton.filledTonal(
                tooltip: 'Restablecer zoom y posición',
                onPressed: () => transform.value = Matrix4.identity(),
                icon: const Icon(Icons.center_focus_strong, size: 19),
              ),
            ),
            const Positioned(
              bottom: 10,
              left: 12,
              right: 12,
              child: IgnorePointer(
                child: Text(
                  'Ilustración genérica · No detecta averías · Zoom y desplazamiento disponibles',
                  style: TextStyle(color: Color(0xFFCBD5E1), fontSize: 10),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ],
        );
      },
    ),
  );

  Widget _marker(BuildContext context, Rect image, VehiclePoint point) {
    final center = markerCenter(image, point.x, point.y);
    final state =
        (widget.states[point.componentId] as Map?)?['condition'] as String? ??
        'no_data';
    final label =
        '${widget.template.label(point.componentId)} · ${conditionLabels[state] ?? conditionLabels['no_data']}';
    return Positioned(
      left: center.dx - 24,
      top: center.dy - 24,
      width: 48,
      height: 48,
      child: Semantics(
        label: label,
        button: true,
        child: Tooltip(
          message: label,
          child: IconButton(
            key: ValueKey('marker:${widget.view.id}:${point.id}'),
            tooltip: null,
            onPressed: () => widget.onPoint(point),
            icon: Container(
              width: 25,
              height: 25,
              decoration: BoxDecoration(
                color: conditionColor(state),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2),
                boxShadow: const [
                  BoxShadow(color: Colors.black38, blurRadius: 6),
                ],
              ),
              child: Icon(
                state == 'normal'
                    ? Icons.check
                    : state == 'issue'
                    ? Icons.priority_high
                    : state == 'follow_up'
                    ? Icons.flag_outlined
                    : Icons.question_mark,
                color: Colors.white,
                size: 15,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
