import 'package:flutter/material.dart';

import '../core/config/atelier_tokens.dart';

/// Librería de controles del sistema visual Automotive Atelier.
///
/// Un solo lugar donde se decide cómo se ve y cómo se comporta un botón.
/// Antes cada pantalla escribía su propio `FilledButton` con su propio color y
/// sus propios estados; el resultado era que «cargando» se resolvía de cinco
/// maneras distintas y ninguna era un estado del sistema, sino un
/// `CircularProgressIndicator` puesto a mano.
///
/// Los ocho estados del sistema —normal, hover, presionado, seleccionado,
/// deshabilitado, cargando, error y foco— se resuelven aquí y se prueban aquí.
/// Cada familia tiene una intención distinta:
///
/// * [AtelierButton.primary]   la acción que continúa el trabajo.
/// * [AtelierButton.secondary] la alternativa a la anterior.
/// * [AtelierButton.technical] la que habla del vehículo o del diagnóstico.
/// * [AtelierButton.contextual] la que actúa sobre el elemento que la acompaña.
/// * [AtelierButton.critical]  la que deshace algo o cobra dinero.
enum AtelierButton { primary, secondary, technical, contextual, critical }

/// Un botón con estados reales.
///
/// La diferencia con `FilledButton` no es el aspecto: es que el estado
/// [loading] bloquea la acción y expone un rótulo accesible, [error] no
/// desaparece al primer pulsado y [selected] es un estado que el servidor
/// puede imponer (por ejemplo, una orden ya aprobada).
class AtelierAction extends StatefulWidget {
  const AtelierAction({
    super.key,
    required this.label,
    required this.onPressed,
    this.family = AtelierButton.primary,
    this.icon,
    this.trailingIcon,
    this.loading = false,
    this.selected = false,
    this.error,
    this.expand = false,
    this.compact = false,
    this.tooltip,
    this.confirmation,
  });

  final String label;
  final VoidCallback? onPressed;
  final AtelierButton family;
  final IconData? icon;
  final IconData? trailingIcon;

  /// En curso. Bloquea la acción: pulsar dos veces no envía dos veces.
  final bool loading;

  /// Estado impuesto, no urination del usuario.
  final bool selected;

  /// Mensaje del último intento fallido. Se muestra **hasta el siguiente
  /// cambio**, no un segundo y desaparece: un error que se va solo obliga a
  /// pulsar otra vez a ciegas.
  final String? error;

  final bool expand;
  final bool compact;
  final String? tooltip;

  /// Confirmación obligatoria antes de ejecutar. Vacío significa que se pide
  /// confirmación con el diálogo estándar.
  /// Texto de la confirmación previa. Nulo en una familia que no sea crítica.
  final String? confirmation;

  bool get isCritical => family == AtelierButton.critical;

  @override
  State<AtelierAction> createState() => _AtelierActionState();
}

class _AtelierActionState extends State<AtelierAction> {
  bool _hovered = false;
  bool _pressed = false;
  bool _confirming = false;

  bool get _enabled => widget.onPressed != null && !widget.loading;

  Future<void> _run() async {
    if (!_enabled) return;
    if (widget.isCritical && !_confirming) {
      final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Confirmar acción'),
          content: Text(
            widget.confirmation ??
                'Esta acción no se puede deshacer. ¿Continuar?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Sí, continuar'),
            ),
          ],
        ),
      );
      if (accepted != true) return;
      if (!mounted) return;
    }
    setState(() => _confirming = false);
    widget.onPressed?.call();
  }

  @override
  Widget build(BuildContext context) {
    final palette = context.atelier;
    final scheme = Theme.of(context).colorScheme;
    final (base, foreground, border) = _colors(palette, scheme);
    // Hover y presionado se distinguen por cuánto se oscurece el fondo. En los
    // fondos ya claros (el secundario es blanco)oscurecer es lo único que
    // funciona, y por eso no se usa una capa de opacidad encima del texto.
    final background = !_enabled
        ? base
        : _pressed
        ? _shade(base, -.12)
        : _hovered
        ? _shade(base, -.06)
        : base;

    final button = Semantics(
      button: true,
      enabled: _enabled,
      selected: widget.selected,
      label: widget.label,
      // Un botón que carga sigue siendo un botón: se anuncia como ocupado en
      // lugar de desaparecer del árbol de accesibilidad.
      hint: widget.loading ? 'Procesando' : widget.tooltip,
      child: ExcludeSemantics(
        child: MouseRegion(
          onEnter: (_) => setState(() => _hovered = true),
          onExit: (_) => setState(() => _hovered = false),
          cursor: _enabled
              ? SystemMouseCursors.click
              : SystemMouseCursors.basic,
          child: GestureDetector(
            onTapDown: _enabled ? (_) => setState(() => _pressed = true) : null,
            onTapUp: _enabled ? (_) => setState(() => _pressed = false) : null,
            onTapCancel: _enabled
                ? () => setState(() => _pressed = false)
                : null,
            onTap: _enabled ? _run : null,
            child: AnimatedOpacity(
              duration: const Duration(milliseconds: 140),
              opacity: _enabled ? 1 : .45,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 140),
                width: widget.expand ? double.infinity : null,
                padding: EdgeInsets.symmetric(
                  horizontal: widget.compact ? 14 : 22,
                  vertical: widget.compact ? 10 : 16,
                ),
                decoration: BoxDecoration(
                  color: background,
                  borderRadius: BorderRadius.circular(12),
                  border: border == null ? null : Border.all(color: border),
                ),
                child: Row(
                  mainAxisSize: widget.expand
                      ? MainAxisSize.max
                      : MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (widget.loading)
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation(foreground),
                        ),
                      )
                    else if (widget.icon != null)
                      Icon(widget.icon, size: 18, color: foreground),
                    if (widget.loading || widget.icon != null)
                      const SizedBox(width: 9),
                    Flexible(
                      child: Text(
                        widget.label,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: foreground,
                          fontWeight: FontWeight.w600,
                          fontSize: widget.compact ? 13 : 14,
                        ),
                      ),
                    ),
                    if (widget.trailingIcon != null && !widget.loading) ...[
                      const SizedBox(width: 8),
                      Icon(widget.trailingIcon, size: 18, color: foreground),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );

    final content = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: widget.expand
          ? CrossAxisAlignment.stretch
          : CrossAxisAlignment.start,
      children: [
        button,
        // El error se queda hasta el siguiente intento: una fila de texto que
        // aparece y se va sola obliga a repetir la acción a ciegas.
        if (widget.error != null) ...[
          const SizedBox(height: 5),
          Text(
            widget.error!,
            style: TextStyle(color: palette.danger, fontSize: 12, height: 1.3),
          ),
        ],
      ],
    );

    return widget.tooltip == null
        ? content
        : Tooltip(message: widget.tooltip!, child: content);
  }

  (Color, Color, Color?) _colors(AtelierTokens palette, ColorScheme scheme) =>
      switch (widget.family) {
        // En «selected» el primario pasa al acento. Si no, el botón marcado y
        // el simplemente pulsado se confundirían.
        AtelierButton.primary => (
          widget.selected ? palette.accent : scheme.primary,
          contrast(widget.selected ? palette.accent : scheme.primary),
          null,
        ),
        AtelierButton.secondary => (
          scheme.surface,
          scheme.onSurface,
          _hovered && _enabled ? scheme.outline : scheme.outlineVariant,
        ),
        AtelierButton.technical => (
          palette.diagnostic,
          palette.onNavigation,
          null,
        ),
        AtelierButton.contextual => (
          palette.accent.withValues(alpha: .12),
          palette.accent,
          null,
        ),
        AtelierButton.critical => (
          palette.danger.withValues(alpha: _hovered ? .2 : .12),
          palette.danger,
          palette.danger.withValues(alpha: .45),
        ),
      };

  Color contrast(Color color) =>
      ThemeData.estimateBrightnessForColor(color) == Brightness.dark
      ? Colors.white
      : const Color(0xFF14213D);

  /// Oscurece o aclara según el fondo. Un `Color.lerp` hacia negro
  /// ensuciaría los colores cálidos: el acento de Heritage Garage se
  /// convertiría en un marrón apagado al pasar el ratón.
  static Color _shade(Color color, double amount) {
    final hsl = HSLColor.fromColor(color);
    return hsl
        .withLightness((hsl.lightness + amount).clamp(0.0, 1.0))
        .toColor();
  }
}

/// Fila de datos con estado, usada en las cabeceras de orden y expediente.
///
/// Existe porque cada pantalla pintaba el estado con su propio color literal.
/// Ahora sale de [statusColor], de modo que «En taller» significa lo mismo en
/// todas partes.
class AtelierStateBadge extends StatelessWidget {
  const AtelierStateBadge({
    super.key,
    required this.label,
    required this.color,
    this.icon,
    this.dense = false,
  });

  /// Estado operativo.
  factory AtelierStateBadge.operational(
    String? status,
    BuildContext context, {
    bool dense = false,
  }) => AtelierStateBadge(
    label: operationalLabel(status),
    color: statusColor(status, context.atelier),
    icon: operationalIcon(status),
    dense: dense,
  );

  /// Estado técnico del componente.
  factory AtelierStateBadge.condition(
    String? state,
    BuildContext context, {
    bool dense = false,
  }) => AtelierStateBadge(
    label: conditionLabels[state] ?? 'Sin datos',
    color: conditionColor(state, context.atelier),
    icon: state == 'issue'
        ? Icons.error_outline
        : state == 'follow_up'
        ? Icons.schedule
        : state == 'normal'
        ? Icons.check_circle_outline
        : Icons.help_outline,
    dense: dense,
  );

  final String label;
  final Color color;
  final IconData? icon;
  final bool dense;

  @override
  Widget build(BuildContext context) => Semantics(
    label: label,
    child: Container(
      padding: EdgeInsets.symmetric(
        horizontal: dense ? 9 : 11,
        vertical: dense ? 5 : 7,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .12),
        borderRadius: BorderRadius.circular(9),
        border: Border.all(color: color.withValues(alpha: .3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: dense ? 13 : 15, color: color),
            const SizedBox(width: 5),
          ],
          Text(
            label,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w600,
              fontSize: dense ? 11 : 12,
            ),
          ),
        ],
      ),
    ),
  );
}

/// Etiqueta informativa que no es un estado: un aviso, una ausencia de
/// dato, una nota de alcance.
///
/// Existía confundida con [AtelierStateBadge] en el mismo widget, que recibía
/// o una clave de estado o texto libre. Al pasar a leerse por clave, el texto
/// libre se habría convertido en «Sin estado» y se habría perdido lo que
/// decía.
class AtelierBadge extends StatelessWidget {
  const AtelierBadge(
    this.label, {
    super.key,
    this.color,
    this.icon,
    this.dense = false,
  });

  final String label;
  final Color? color;
  final IconData? icon;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final tone = color ?? context.atelier.secondaryText;
    return Semantics(
      label: label,
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: dense ? 9 : 11,
          vertical: dense ? 5 : 7,
        ),
        decoration: BoxDecoration(
          color: tone.withValues(alpha: .1),
          borderRadius: BorderRadius.circular(9),
          border: Border.all(color: tone.withValues(alpha: .28)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: dense ? 13 : 15, color: tone),
              const SizedBox(width: 5),
            ],
            Flexible(
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: tone,
                  fontWeight: FontWeight.w600,
                  fontSize: dense ? 11 : 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String operationalLabel(String? status) => switch (status) {
  'in_progress' => 'En taller',
  'ready' => 'Listo para retirar',
  'delivered' => 'Entregado',
  'cancelled' => 'Cancelado',
  'approved' => 'Aprobado',
  'rejected' => 'Rechazado',
  'sent' => 'Enviado',
  'failed' => 'Fallido',
  'pending' => 'Pendiente',
  'paused' => 'En pausa',
  _ => 'Sin estado',
};

IconData? operationalIcon(String? status) => switch (status) {
  'in_progress' => Icons.build_outlined,
  'ready' => Icons.check_circle_outline,
  'delivered' => Icons.outbox_outlined,
  'cancelled' || 'rejected' || 'failed' => Icons.cancel_outlined,
  'approved' || 'sent' => Icons.task_alt,
  'pending' => Icons.schedule,
  'paused' => Icons.pause_circle_outline,
  _ => Icons.help_outline,
};

/// Campo de formulario del sistema, con error que no borra lo escrito.
///
/// El `TextFormField` normal muestra el error y el usuario reescribe todo.
/// Este conserva el texto: perder un lote de ingreso escrito a mano por un
/// error de validación es el fallo que más tiempo cuesta en un taller.
class AtelierField extends StatelessWidget {
  const AtelierField({
    super.key,
    required this.controller,
    required this.label,
    this.hint,
    this.keyboardType,
    this.maxLength,
    this.validator,
    this.error,
    this.onChanged,
    this.fieldKey,
    this.enabled = true,
    this.prefix,
    this.suffix,
    this.multiline = false,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final TextInputType? keyboardType;
  final int? maxLength;
  final String? Function(String?)? validator;
  final String? error;
  final ValueChanged<String>? onChanged;
  final Key? fieldKey;
  final bool enabled;
  final Widget? prefix;
  final Widget? suffix;
  final bool multiline;

  @override
  Widget build(BuildContext context) {
    final palette = context.atelier;
    return TextField(
      key: fieldKey,
      controller: controller,
      enabled: enabled,
      keyboardType: keyboardType,
      maxLength: maxLength,
      onChanged: onChanged,
      maxLines: multiline ? 4 : 1,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: prefix,
        suffixIcon: suffix,
        errorText: error,
        errorStyle: TextStyle(color: palette.danger, fontSize: 12),
        counterText: '',
      ),
    );
  }
}

/// Estado de carga con su mensaje. Nunca un `CircularProgressIndicator`
/// suelto: un usuario en espera necesita saber qué se está cargando.
class AtelierLoading extends StatelessWidget {
  const AtelierLoading(this.message, {super.key, this.compact = false});
  final String message;
  final bool compact;

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: message,
    child: Padding(
      padding: EdgeInsets.symmetric(vertical: compact ? 12 : 40),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 26,
              height: 26,
              child: CircularProgressIndicator(strokeWidth: 2.5),
            ),
            const SizedBox(height: 12),
            Text(
              message,
              style: TextStyle(color: context.atelier.secondaryText),
            ),
          ],
        ),
      ),
    ),
  );
}

/// Estado vacío con la acción que lo resuelve.
///
/// Un vacío sin salida obliga al usuario a adivinar qué hacer. Este siempre
/// ofrece el camino, o explica por qué no lo hay.
class AtelierEmpty extends StatelessWidget {
  const AtelierEmpty({
    super.key,
    required this.title,
    required this.message,
    this.icon = Icons.inbox_outlined,
    this.action,
  });

  final String title;
  final String message;
  final IconData icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 44),
    child: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 34, color: context.atelier.secondaryText),
          const SizedBox(height: 12),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(color: context.atelier.secondaryText, height: 1.4),
          ),
          if (action != null) ...[const SizedBox(height: 18), action!],
        ],
      ),
    ),
  );
}

/// Indicador de posición dentro de un juego de datos.
///
/// Un contador desnudo («1-20 de 340») obliga a hacer cuentas. Aquí la
/// posición se lee y además el texto es el que screen readers pronuncian.
class AtelierPaginator extends StatelessWidget {
  const AtelierPaginator({
    super.key,
    required this.from,
    required this.to,
    required this.total,
    this.onPrevious,
    this.onNext,
  });

  final int from;
  final int to;
  final int total;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    final palette = context.atelier;
    final first = total == 0 ? 0 : from + 1;
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Text(
          total == 0 ? 'Sin resultados' : '$first–$to de $total',
          style: TextStyle(fontSize: 12, color: palette.secondaryText),
        ),
        const SizedBox(width: 10),
        IconButton(
          tooltip: 'Anterior',
          onPressed: onPrevious,
          icon: const Icon(Icons.chevron_left),
          visualDensity: VisualDensity.compact,
          constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
        ),
        IconButton(
          tooltip: 'Siguiente',
          onPressed: onNext,
          icon: const Icon(Icons.chevron_right),
          visualDensity: VisualDensity.compact,
          constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
        ),
      ],
    );
  }
}

/// Medidor de completitud, para los paneles de resumen.
///
/// No se usa un `LinearProgressIndicator` a secas porque su color por defecto
/// no dice «esto va bien». Aquí el color viene de los tokens y el valor tiene
/// etiqueta.
class AtelierMeter extends StatelessWidget {
  const AtelierMeter({super.key, required this.value, this.label, this.color});

  /// Fracción entre 0 y 1.
  final double value;
  final String? label;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final palette = context.atelier;
    final clamped = value.isNaN ? 0.0 : value.clamp(0.0, 1.0);
    final tone = color ?? palette.complementary;
    return Semantics(
      label: label ?? '${(clamped * 100).round()} por ciento',
      value: '${(clamped * 100).round()}%',
      child: ExcludeSemantics(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (label != null) ...[
              Text(
                label!,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
            ],
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: clamped,
                minHeight: 7,
                backgroundColor: tone.withValues(alpha: .15),
                valueColor: AlwaysStoppedAnimation(tone),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Contenedor que aplica el mismo margen y el mismo fondo a todas las pantallas.
///
/// Existe para que ninguna vista tenga que decidir por su cuenta cuánto deja
/// de margen: cada una lo hacía distinto y el resultado era un mosaico.
class AtelierPage extends StatelessWidget {
  const AtelierPage({
    super.key,
    required this.child,
    this.maxWidth = 1180,
    this.padding = const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
  });

  final Widget child;
  final double maxWidth;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: Padding(padding: padding, child: child),
    ),
  );
}

/// Cuántas columnas caben en el ancho disponible sin que cada tarjeta quede
/// por debajo del mínimo legible de 120 px.
double responsiveColumns(double available, double columns, double gap) {
  if (available <= 0 || columns <= 0) return 1;
  final fit = ((available + gap) / (columns * 120 + gap)).floor();
  return fit.clamp(1, columns).toDouble();
}
