import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart';
import '../../core/models/operation_key.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/editor_dialog.dart';
import '../../shared/widgets.dart';
import 'catalog_record_page.dart';

class StockPage extends StatefulWidget {
  const StockPage({super.key});
  @override
  State<StockPage> createState() => _StockPageState();
}

class _StockPageState extends State<StockPage> {
  List<Json> _rows = [];
  int _offset = 0;
  bool _loading = false, _more = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    if (context.read<WorkshopController>().isAdmin) _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = jsonList(
        await context.read<WorkshopController>().api.request(
          'GET',
          '/stock?limit=51&offset=$_offset',
        ),
      );
      if (mounted) {
        setState(() {
          _rows = result.take(50).toList();
          _more = result.length > 50;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => _error = failure.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _receipt() async {
    final state = context.read<WorkshopController>();
    Json? part;
    var key = operationKey();
    String? previous;
    await showEditor(
      context,
      title: 'Registrar entrada física',
      description:
          'Introduce únicamente cantidades recibidas y verificadas. El catálogo no implica que el taller tenga existencias.',
      fields: [
        const EditorField(
          'quantity',
          'Cantidad recibida',
          keyboard: TextInputType.number,
        ),
        const EditorField(
          'unit',
          'Unidad (sin conversión automática)',
          initial: 'unidad',
        ),
        const EditorField('reason', 'Documento / motivo de entrada', lines: 2),
      ],
      extra: CatalogReferenceSearch(
        api: state.api,
        endpoint: '/catalog/parts?',
        label: 'Buscar y seleccionar repuesto (obligatorio)',
        onSelected: (row) => part = row,
        onTyped: () => part = null,
      ),
      onSubmit: (values) async {
        if (part == null) {
          throw const ApiException('Selecciona un repuesto real del catálogo.');
        }
        final body = <String, dynamic>{...values, 'part_id': part!['id']};
        if (previous != null && previous != body.toString()) {
          key = operationKey();
        }
        previous = body.toString();
        await state.api.request(
          'POST',
          '/stock/receipts',
          body: {...body, 'request_key': key},
        );
        await _load();
      },
    );
  }

  Future<void> _movements(Json row) async {
    final future = context.read<WorkshopController>().api.request(
      'GET',
      '/stock/${row['id']}/movements?limit=100',
    );
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Movimientos · ${row['sku']}'),
        content: SizedBox(
          width: 600,
          child: FutureBuilder(
            future: future,
            builder: (context, result) {
              if (result.hasError) return Text('${result.error}');
              if (!result.hasData) {
                return const SizedBox(
                  height: 100,
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              return SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'Últimos 100 movimientos. Las salidas están vinculadas a una solicitud y no se descuentan desde el catálogo.',
                    ),
                    for (final movement in jsonList(result.data))
                      ListTile(
                        title: Text(
                          '${movement['delta']} ${row['unit']} · ${movement['reason']}',
                        ),
                        subtitle: Text(
                          '${shortDate(movement['created_at'])}${movement['part_request_id'] == null ? '' : ' · Solicitud #${movement['part_request_id']}'}',
                        ),
                      ),
                  ],
                ),
              );
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Existencias físicas del taller')),
    body: !context.watch<WorkshopController>().isAdmin
        ? const EmptyState(
            title: 'Acceso restringido',
            message:
                'Las entradas y entregas físicas corresponden a administración.',
          )
        : Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Wrap(
                  spacing: 12,
                  children: [
                    FilledButton.icon(
                      onPressed: _receipt,
                      icon: const Icon(Icons.add),
                      label: const Text('Registrar entrada real'),
                    ),
                    IconButton(
                      tooltip: 'Actualizar existencias',
                      onPressed: _loading ? null : _load,
                      icon: const Icon(Icons.refresh),
                    ),
                  ],
                ),
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    'Los saldos se forman con entradas y entregas autorizadas. No son disponibilidad del catálogo ni precios de venta.',
                  ),
                ),
                if (_loading) const LinearProgressIndicator(),
                if (_error != null)
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                Expanded(
                  child: _rows.isEmpty && !_loading
                      ? const EmptyState(
                          title: 'Sin existencias registradas',
                          message:
                              'No se crean saldos ficticios. Registra una entrada cuando recibas el material.',
                        )
                      : ListView.builder(
                          itemCount: _rows.length,
                          itemBuilder: (context, index) {
                            final row = _rows[index];
                            return Card(
                              child: ListTile(
                                title: Text('${row['sku']} · ${row['name']}'),
                                subtitle: Text(
                                  '${row['quantity']} ${row['unit']}',
                                ),
                                onTap: () => _movements(row),
                                trailing: IconButton(
                                  tooltip: 'Ver ficha de catálogo',
                                  onPressed: () => openCatalogRecord(
                                    context,
                                    'part',
                                    row['part_id'] as int,
                                  ),
                                  icon: const Icon(Icons.info_outline),
                                ),
                              ),
                            );
                          },
                        ),
                ),
                AtelierPaginator(
                  from: _offset,
                  to: _offset + _rows.length,
                  total: _offset + _rows.length + (_more ? 1 : 0),
                  onPrevious: _loading || _offset == 0
                      ? null
                      : () {
                          _offset -= 50;
                          _load();
                        },
                  onNext: _loading || !_more
                      ? null
                      : () {
                          _offset += 50;
                          _load();
                        },
                ),
              ],
            ),
          ),
  );
}
