import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart' show jsonList;
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';

const _entities = {
  'make': 'Marca',
  'model': 'Modelo',
  'generation': 'Generación',
  'engine': 'Motor',
  'part': 'Repuesto',
};

/// Cola administrativa; no publica la marca ni elimina fichas del catálogo.
class CatalogReviewPage extends StatefulWidget {
  const CatalogReviewPage({super.key});

  @override
  State<CatalogReviewPage> createState() => _CatalogReviewPageState();
}

class _CatalogReviewPageState extends State<CatalogReviewPage> {
  List<Json> _rows = [];
  String _state = 'needs_review';
  String _entity = '';
  String? _error;
  bool _loading = false;
  int _offset = 0;
  int _total = 0;
  int _request = 0;
  static const _limit = 20;

  @override
  void initState() {
    super.initState();
    if (context.read<WorkshopController>().isAdmin) _load();
  }

  Future<void> _load() async {
    final request = ++_request;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result =
          await context.read<WorkshopController>().api.request(
                'GET',
                '/catalog/review-queue?state=$_state&limit=$_limit&offset=$_offset'
                    '${_entity.isEmpty ? '' : '&entity_type=$_entity'}',
              )
              as Json;
      if (!mounted || request != _request) return;
      setState(() {
        _rows = jsonList(result['items']);
        _total = result['total'] as int;
      });
    } catch (failure) {
      if (mounted && request == _request) {
        setState(() => _error = failure.toString());
      }
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  Future<void> _review(Json row, bool verify) async {
    final result = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _ReviewDialog(
        api: context.read<WorkshopController>().api,
        row: row,
        verify: verify,
      ),
    );
    if (!mounted || result == null) return;
    // La fila puede desaparecer de la última página después de verificarse.
    if (result && verify && _rows.length == 1 && _offset >= _limit) {
      _offset -= _limit;
    }
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final allowed = context.watch<WorkshopController>().isAdmin;
    return Scaffold(
      appBar: AppBar(title: const Text('Revisión del catálogo')),
      body: !allowed
          ? const EmptyState(
              title: 'Acceso restringido',
              message: 'Solo los administradores pueden revisar propuestas.',
            )
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'Propuestas manuales del personal de tu taller. Verificar '
                    'actualiza su procedencia; dejar pendiente conserva la ficha '
                    'y el motivo. No certifica un vehículo ni publica el diseño.',
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      for (final entry in {
                        'needs_review': 'Pendientes',
                        'verified': 'Verificados',
                      }.entries)
                        ChoiceChip(
                          label: Text(entry.value),
                          selected: _state == entry.key,
                          onSelected: (_) {
                            setState(() {
                              _state = entry.key;
                              _offset = 0;
                            });
                            _load();
                          },
                        ),
                      SizedBox(
                        width: 200,
                        child: DropdownButtonFormField<String>(
                          initialValue: '',
                          isExpanded: true,
                          decoration: const InputDecoration(
                            labelText: 'Tipo de registro',
                          ),
                          items: [
                            const DropdownMenuItem(
                              value: '',
                              child: Text('Todos'),
                            ),
                            for (final entry in _entities.entries)
                              DropdownMenuItem(
                                value: entry.key,
                                child: Text(entry.value),
                              ),
                          ],
                          onChanged: (value) {
                            setState(() {
                              _entity = value ?? '';
                              _offset = 0;
                            });
                            _load();
                          },
                        ),
                      ),
                      IconButton(
                        tooltip: 'Actualizar cola',
                        onPressed: _loading ? null : _load,
                        icon: const Icon(Icons.refresh),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  if (_loading)
                    const AtelierLoading('Consultando propuestas…')
                  else if (_error != null)
                    EmptyState(
                      title: 'No se pudo consultar la cola',
                      message: _error!,
                      action: TextButton(
                        onPressed: _load,
                        child: const Text('Reintentar'),
                      ),
                    )
                  else if (_rows.isEmpty)
                    const AtelierEmpty(
                      title: 'Sin registros en esta vista',
                      message: 'Esta cola solo contiene propuestas manuales para revisar. Los datos importados se consultan en Catálogo automotriz, no aquí.',
                    )
                  else
                    for (final row in _rows) _record(row),
                  if (!_loading && _error == null)
                    AtelierPaginator(
                      from: _offset,
                      to: _offset + _rows.length,
                      total: _total,
                      onPrevious: _offset == 0
                          ? null
                          : () {
                              _offset -= _limit;
                              _load();
                            },
                      onNext: _offset + _rows.length >= _total
                          ? null
                          : () {
                              _offset += _limit;
                              _load();
                            },
                    ),
                ],
              ),
            ),
    );
  }

  Widget _record(Json row) {
    final record = Map<String, dynamic>.from(row['record'] as Map? ?? {});
    final title =
        record['name'] ??
        record['label'] ??
        record['title'] ??
        'Ficha no disponible';
    final fields = {
      'year_start': 'Desde',
      'year_end': 'Hasta',
      'body_type': 'Carrocería',
      'sku': 'Código',
      'brand': 'Marca del repuesto',
      'category': 'Categoría',
      'fuel_type': 'Combustible',
      'displacement_cc': 'Cilindrada (cc)',
      'power_hp': 'Potencia (hp)',
      'torque_nm': 'Par (Nm)',
      'cylinders': 'Cilindros',
      'transmission': 'Transmisión',
      'drivetrain': 'Tracción',
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: SectionCard(
        title: '${_entities[row['entity_type']]} · $title',
        subtitle:
            'Propuesto por ${row['created_by_name'] ?? 'autor no disponible'} · '
            '${shortDate(row['created_at'])} · Revisión ${row['revision']}',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (jsonList(row['parents']).isNotEmpty)
              Text(
                jsonList(
                  row['parents'],
                ).map((parent) => parent['name']).join(' → '),
              ),
            for (final entry in fields.entries)
              if (record[entry.key] != null)
                Text('${entry.value}: ${record[entry.key]}'),
            for (final term in jsonList(row['terms'])) ...[
              Text('Nombre en español: ${term['name_es']}'),
              Text('Sinónimos: ${(term['synonyms'] as List).join(', ')}'),
            ],
            if ((row['proposal_note'] as String? ?? '').isNotEmpty)
              Text('Nota de origen: ${row['proposal_note']}'),
            if ((row['review_note'] as String? ?? '').isNotEmpty)
              Text('Última revisión: ${row['review_note']}'),
            const SizedBox(height: 12),
            if (_state == 'needs_review')
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  AtelierAction(
                    label: 'Verificar registro',
                    icon: Icons.verified_outlined,
                    compact: true,
                    onPressed: record.isEmpty ? null : () => _review(row, true),
                  ),
                  AtelierAction(
                    label: 'Dejar pendiente',
                    family: AtelierButton.secondary,
                    compact: true,
                    onPressed: () => _review(row, false),
                  ),
                ],
              )
            else
              Text('Verificado el ${shortDate(row['reviewed_at'])}'),
          ],
        ),
      ),
    );
  }
}

class _ReviewDialog extends StatefulWidget {
  const _ReviewDialog({
    required this.api,
    required this.row,
    required this.verify,
  });
  final ApiClient api;
  final Json row;
  final bool verify;
  @override
  State<_ReviewDialog> createState() => _ReviewDialogState();
}

class _ReviewDialogState extends State<_ReviewDialog> {
  final _note = TextEditingController();
  bool _busy = false;
  bool _stale = false;
  String? _error;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || _stale) return;
    if (!widget.verify && _note.text.trim().isEmpty) {
      setState(() => _error = 'Indica qué falta comprobar.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.request(
        'POST',
        '/catalog/review-queue/${widget.row['entity_type']}/${widget.row['entity_id']}',
        body: {
          'expected_revision': widget.row['revision'],
          'decision': widget.verify ? 'verify' : 'keep_pending',
          'note': _note.text.trim(),
        },
      );
      if (mounted) {
        Navigator.pop(context, true);
      }
    } catch (failure) {
      if (mounted) {
        setState(() {
          _error = failure.toString();
          _stale = failure is ApiException && failure.statusCode == 409;
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_busy,
    child: AlertDialog(
      title: Text(
        widget.verify ? 'Verificar propuesta' : 'Conservar pendiente',
      ),
      content: SizedBox(
        width: 460,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                widget.verify
                    ? 'Confirma que has contrastado los datos de esta ficha.'
                    : 'La ficha se conserva. Explica qué debe comprobarse.',
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _note,
                readOnly: _busy,
                maxLength: 1000,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Nota de revisión',
                ),
              ),
              if (_error != null)
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        if (_stale)
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Actualizar cola'),
          )
        else
          AtelierAction(
            label: widget.verify ? 'Confirmar verificación' : 'Guardar motivo',
            loading: _busy,
            compact: true,
            onPressed: _submit,
          ),
      ],
    ),
  );
}
