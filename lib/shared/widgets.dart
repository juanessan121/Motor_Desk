import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';

import '../core/config/app_config_model.dart';
import '../core/config/regional_format.dart';
import '../core/network/api_client.dart';
import 'atelier_controls.dart';

String money(dynamic value) => const RegionalFormat().money(value);
String shortDate(dynamic value) => const RegionalFormat().date(value);

void showMessage(BuildContext context, String message, {bool error = false}) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message),
      backgroundColor: error ? Theme.of(context).colorScheme.error : null,
    ),
  );
}

Future<void> runAction(
  BuildContext context,
  Future<void> Function() action, {
  String? success,
}) async {
  try {
    await action();
    if (context.mounted && success != null) showMessage(context, success);
  } catch (failure) {
    if (context.mounted) showMessage(context, failure.toString(), error: true);
  }
}

Future<bool> confirmAction(
  BuildContext context,
  String title,
  String description,
) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(description),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirmar'),
          ),
        ],
      ),
    ) ??
    false;

class BrandLogo extends StatelessWidget {
  const BrandLogo({super.key, required this.config, this.size = 44});
  final AppConfigModel config;
  final double size;
  @override
  Widget build(BuildContext context) {
    final fallback = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: config.color('primary'),
        borderRadius: BorderRadius.circular(13),
      ),
      child: Icon(
        Icons.car_repair_rounded,
        color: Colors.white,
        size: size * .6,
      ),
    );
    if (config.logo.isEmpty) return fallback;
    Widget image;
    try {
      image = config.logo.startsWith('data:')
          ? Image.memory(
              base64Decode(config.logo.split(',').last),
              width: size,
              height: size,
              fit: BoxFit.contain,
              errorBuilder: (_, _, _) => fallback,
            )
          : Image.network(
              config.logo,
              width: size,
              height: size,
              fit: BoxFit.contain,
              errorBuilder: (_, _, _) => fallback,
            );
    } on FormatException {
      return fallback;
    }
    return ClipRRect(borderRadius: BorderRadius.circular(12), child: image);
  }
}

class PageHeading extends StatelessWidget {
  const PageHeading({
    super.key,
    required this.title,
    required this.subtitle,
    this.action,
  });
  final String title;
  final String subtitle;
  final Widget? action;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final heading = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              letterSpacing: -.8,
            ),
          ),
          const SizedBox(height: 7),
          Text(
            subtitle,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.5,
            ),
          ),
        ],
      );
      if (constraints.maxWidth < 620) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            heading,
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        );
      }
      return Row(
        children: [
          Expanded(child: heading),
          if (action != null) ...[const SizedBox(width: 18), action!],
        ],
      );
    },
  );
}

/// Etiqueta de estado operativo.
///
/// Antes tenía los colores escritos a mano, de modo que «En taller» salía
/// azul con cualquier tema. Ahora sale de los tokens del tema activo, igual
/// que el resto de la aplicación.
class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key});
  final String status;
  @override
  Widget build(BuildContext context) =>
      AtelierStateBadge.operational(status, context, dense: true);
}

class EmptyState extends StatelessWidget {
  const EmptyState({
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
          Icon(
            icon,
            size: 46,
            color: Theme.of(context).colorScheme.primary.withValues(alpha: .55),
          ),
          const SizedBox(height: 18),
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.6,
            ),
          ),
          if (action != null) ...[const SizedBox(height: 22), action!],
        ],
      ),
    ),
  );
}

class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.title,
    required this.child,
    this.trailing,
    this.subtitle,
    this.padding = const EdgeInsets.all(24),
  });
  final String title;
  final Widget child;
  final Widget? trailing;
  /// Texto breve que explica para qué sirve la sección.
  final String? subtitle;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: padding,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        subtitle!,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color:
                                  Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ],
                ),
              ),
              ?trailing,
            ],
          ),
          const SizedBox(height: 20),
          child,
        ],
      ),
    ),
  );
}

class RecordColumn {
  const RecordColumn(this.label, this.value, {this.cell});
  final String label;
  final String Function(Json) value;
  final Widget Function(Json)? cell;
}

class RecordTable extends StatefulWidget {
  const RecordTable({
    super.key,
    required this.records,
    required this.columns,
    required this.emptyTitle,
    this.actions,
  });
  final List<Json> records;
  final List<RecordColumn> columns;
  final String emptyTitle;
  final Widget Function(Json)? actions;
  @override
  State<RecordTable> createState() => _RecordTableState();
}

class _RecordTableState extends State<RecordTable> {
  String query = '';
  int page = 0;
  int sortColumn = 0;
  bool ascending = true;
  @override
  Widget build(BuildContext context) {
    final records = widget.records
        .where(
          (row) => widget.columns.any(
            (column) => column.value(row).toLowerCase().contains(query),
          ),
        )
        .toList();
    records.sort((a, b) {
      final column = widget.columns[sortColumn];
      final result = column
          .value(a)
          .toLowerCase()
          .compareTo(column.value(b).toLowerCase());
      return ascending ? result : -result;
    });
    final currentPage = min(page, max(0, (records.length - 1) ~/ 8));
    final visible = records.skip(currentPage * 8).take(8);
    return Card(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Expanded(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 390),
                    child: TextField(
                      decoration: const InputDecoration(
                        hintText: 'Buscar en esta lista…',
                        prefixIcon: Icon(Icons.search_rounded),
                        isDense: true,
                      ),
                      onChanged: (value) => setState(() {
                        query = value.toLowerCase().trim();
                        page = 0;
                      }),
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Text(
                  '${records.length} registros',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const Divider(),
          if (records.isEmpty)
            EmptyState(
              title: widget.emptyTitle,
              message: query.isEmpty
                  ? 'Los registros que agregues aparecerán aquí.'
                  : 'Prueba con otro criterio de búsqueda.',
            )
          else
            LayoutBuilder(
              builder: (context, constraints) => SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: ConstrainedBox(
                  constraints: BoxConstraints(minWidth: constraints.maxWidth),
                  child: DataTable(
                    sortColumnIndex: sortColumn,
                    sortAscending: ascending,
                    columns: [
                      for (
                        var index = 0;
                        index < widget.columns.length;
                        index++
                      )
                        DataColumn(
                          label: Text(
                            widget.columns[index].label.toUpperCase(),
                          ),
                          onSort: (column, direction) => setState(() {
                            sortColumn = column;
                            ascending = direction;
                          }),
                        ),
                      if (widget.actions != null)
                        const DataColumn(label: Text('ACCIONES')),
                    ],
                    rows: [
                      for (final row in visible)
                        DataRow(
                          cells: [
                            for (final column in widget.columns)
                              DataCell(
                                column.cell?.call(row) ??
                                    Text(column.value(row)),
                              ),
                            if (widget.actions != null)
                              DataCell(widget.actions!(row)),
                          ],
                        ),
                    ],
                  ),
                ),
              ),
            ),
          const Divider(),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    records.isEmpty
                        ? 'Sin resultados'
                        : '${currentPage * 8 + 1}–${min((currentPage + 1) * 8, records.length)} de ${records.length}',
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
                IconButton(
                  tooltip: 'Página anterior',
                  onPressed: currentPage > 0
                      ? () => setState(() => page = currentPage - 1)
                      : null,
                  icon: const Icon(Icons.chevron_left),
                ),
                IconButton(
                  tooltip: 'Página siguiente',
                  onPressed: (currentPage + 1) * 8 < records.length
                      ? () => setState(() => page = currentPage + 1)
                      : null,
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
