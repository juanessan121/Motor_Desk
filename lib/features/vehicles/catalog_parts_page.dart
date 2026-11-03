import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart' show jsonList;
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';
import 'catalog_record_page.dart';
import 'stock_page.dart';

class CatalogPartsPage extends StatefulWidget {
  const CatalogPartsPage({super.key, this.embedded = false});
  final bool embedded;
  @override
  State<CatalogPartsPage> createState() => _CatalogPartsPageState();
}

class _CatalogPartsPageState extends State<CatalogPartsPage> {
  final _search = TextEditingController();
  Timer? _debounce;
  Json _filters = {};
  List<Json> _parts = [];
  bool _loading = false;
  bool _semantic = false;
  String _mode = 'text';
  String? _error, _system, _category, _source, _manufacturer, _emptyReason;
  String _sort = 'name_asc';
  int? _make, _model;
  int _offset = 0, _total = 0, _available = 0, _request = 0;
  static const _limit = 20;
  ApiClient get api => context.read<WorkshopController>().api;

  @override
  void initState() {
    super.initState();
    final user = context.read<WorkshopController>();
    if (user.isAdmin || user.isMechanic) {
      _loadFilters();
      _load();
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _loadFilters() async {
    try {
      final data = await api.request('GET', '/catalog/parts/filters') as Json;
      if (mounted) setState(() => _filters = data);
    } catch (_) {
      /* El listado sigue disponible y muestra sus propios errores. */
    }
  }

  void _reset() {
    _offset = 0;
    _load();
  }

  Future<void> _load() async {
    final request = ++_request;
    setState(() {
      _loading = true;
      _error = null;
    });
    final params = {
      'q': _search.text.trim(),
      'limit': '$_limit',
      'offset': '$_offset',
      'sort': _sort,
      'semantic': '$_semantic',
      'system': ?_system,
      'category': ?_category,
      'source': ?_source,
      'manufacturer': ?_manufacturer,
      if (_make != null) 'make_id': '$_make',
      if (_model != null) 'model_id': '$_model',
    };
    try {
      final data =
          await api.request(
                'GET',
                '/catalog/parts?${Uri(queryParameters: params).query}',
              )
              as Json;
      if (!mounted || request != _request) return;
      setState(() {
        _parts = jsonList(data['items']);
        _total = data['total'] as int;
        _available = data['available'] as int;
        _mode = data['mode'] as String;
        _emptyReason = data['empty_reason'] as String?;
      });
    } catch (failure) {
      if (mounted && request == _request) {
        setState(() => _error = failure.toString());
      }
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  Future<void> _manual() async {
    final saved = await showDialog<Json>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _ManualPartDialog(api: api),
    );
    if (!mounted || saved == null) return;
    _loadFilters();
    _reset();
    await openCatalogRecord(context, 'part', saved['id'] as int);
  }

  Widget _filter(
    String label,
    String key,
    String? value,
    ValueChanged<String?> changed,
  ) => SizedBox(
    width: 220,
    child: DropdownButtonFormField<String>(
      key: ValueKey('$key:$value'),
      initialValue: value ?? '',
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: [
        const DropdownMenuItem(value: '', child: Text('Todos')),
        for (final option in (_filters[key] as List? ?? []))
          DropdownMenuItem(
            value: option as String,
            child: Text(
              key == 'sources' ? catalogSourceLabels[option] ?? option : option,
              overflow: TextOverflow.ellipsis,
            ),
          ),
      ],
      onChanged: (value) {
        changed(value == '' ? null : value);
        _reset();
      },
    ),
  );

  @override
  Widget build(BuildContext context) {
    final staff = context.watch<WorkshopController>();
    if (!staff.isAdmin && !staff.isMechanic) {
      return const EmptyState(
        title: 'Acceso restringido',
        message: 'El catálogo técnico es de consulta del personal del taller.',
      );
    }
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 360,
                child: TextField(
                  controller: _search,
                  maxLength: 120,
                  decoration: const InputDecoration(
                    labelText: 'Buscar repuesto, sinónimo o código',
                    prefixIcon: Icon(Icons.search),
                    counterText: '',
                  ),
                  onChanged: (_) {
                    _debounce?.cancel();
                    _debounce = Timer(
                      const Duration(milliseconds: 300),
                      _reset,
                    );
                  },
                  onSubmitted: (_) {
                    _debounce?.cancel();
                    _reset();
                  },
                ),
              ),
              _filter(
                'Sistema mecánico',
                'systems',
                _system,
                (value) => _system = value,
              ),
              _filter(
                'Fuente de datos',
                'sources',
                _source,
                (value) => _source = value,
              ),
              FilledButton.icon(
                onPressed: _manual,
                icon: const Icon(Icons.add),
                label: const Text('Agregar repuesto manual'),
              ),
              if (staff.isAdmin)
                OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(builder: (_) => const StockPage()),
                  ),
                  icon: const Icon(Icons.inventory_2_outlined),
                  label: const Text('Existencias físicas'),
                ),
              IconButton(
                tooltip: 'Actualizar catálogo',
                onPressed: _loading ? null : _load,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ),
        ExpansionTile(
          title: const Text('Más filtros y compatibilidad documentada'),
          tilePadding: EdgeInsets.zero,
          children: [
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                _filter(
                  'Categoría de origen',
                  'categories',
                  _category,
                  (value) => _category = value,
                ),
                _filter(
                  'Fabricante del repuesto',
                  'manufacturers',
                  _manufacturer,
                  (value) => _manufacturer = value,
                ),
                SizedBox(
                  width: 250,
                  child: CatalogReferenceSearch(
                    api: api,
                    label: 'Marca de vehículo',
                    endpoint: '/catalog/browse?entity=make',
                    onSelected: (row) {
                      setState(() {
                        _make = row['id'] as int;
                        _model = null;
                      });
                      _reset();
                    },
                    onTyped: () {
                      if (_make != null) {
                        setState(() {
                          _make = null;
                          _model = null;
                        });
                        _reset();
                      }
                    },
                  ),
                ),
                if (_make != null)
                  SizedBox(
                    width: 250,
                    child: CatalogReferenceSearch(
                      key: ValueKey(_make),
                      api: api,
                      label: 'Modelo de vehículo',
                      endpoint: '/catalog/browse?entity=model&make_id=$_make',
                      onSelected: (row) {
                        _model = row['id'] as int;
                        _reset();
                      },
                      onTyped: () {
                        if (_model != null) {
                          _model = null;
                          _reset();
                        }
                      },
                    ),
                  ),
                SizedBox(
                  width: 200,
                  child: DropdownButtonFormField<String>(
                    initialValue: _sort,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Ordenar'),
                    items: [
                      for (final item in {
                        'name_asc': 'Nombre A–Z',
                        'name_desc': 'Nombre Z–A',
                        'code_asc': 'Código A–Z',
                        'code_desc': 'Código Z–A',
                      }.entries)
                        DropdownMenuItem(
                          value: item.key,
                          child: Text(item.value),
                        ),
                    ],
                    onChanged: (value) {
                      _sort = value!;
                      _reset();
                    },
                  ),
                ),
              ],
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Ampliar con búsqueda semántica'),
              subtitle: const Text(
                'La similitud no demuestra compatibilidad. Los filtros por vehículo siguen siendo obligatorios.',
              ),
              value: _semantic,
              onChanged: (value) {
                _semantic = value;
                _reset();
              },
            ),
          ],
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Text(
            '$_total resultados · $_available repuestos accesibles · ${_mode == 'hybrid' ? 'Búsqueda híbrida' : 'Búsqueda textual'}',
          ),
        ),
        if (_semantic &&
            _search.text.trim().length >= 2 &&
            _mode == 'text' &&
            !_loading)
          const Text(
            'La ampliación semántica no está disponible; la consulta textual continúa funcionando.',
          ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
              ? EmptyState(
                  title: 'No se pudo consultar el catálogo',
                  message: _error!,
                  action: TextButton(
                    onPressed: _load,
                    child: const Text('Reintentar'),
                  ),
                )
              : _parts.isEmpty
              ? EmptyState(
                  title: _emptyReason == 'empty_catalog'
                      ? 'No hay datos de repuestos disponibles'
                      : _emptyReason == 'no_documented_fits'
                      ? 'Sin compatibilidades documentadas para este filtro'
                      : 'Sin coincidencias',
                  message: _emptyReason == 'empty_catalog'
                      ? 'La consulta respondió correctamente, pero no encontró datos maestros. Revisa la importación; no es la cola de propuestas.'
                      : 'Ajusta la búsqueda o registra lo que falta. No se deducen compatibilidades por similitud de nombres.',
                  action: TextButton(
                    onPressed: _manual,
                    child: const Text('Agregar manualmente'),
                  ),
                )
              : ListView.separated(
                  itemCount: _parts.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (context, index) {
                    final part = _parts[index];
                    return Card(
                      child: ListTile(
                        contentPadding: const EdgeInsets.all(16),
                        leading: const Icon(Icons.build_outlined),
                        title: Text(
                          (part['name_es'] ?? part['title']) as String,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        subtitle: Text(
                          '${part['sku']} · ${part['system'] ?? part['category'] ?? 'Sistema no informado'}\n'
                          '${catalogSourceLabels[part['source_key']] ?? part['source_key'] ?? 'Fuente no registrada'} · ${catalogOriginLabels[part['origin']] ?? part['origin']}\n'
                          '${(part['compatibilities_count'] as int? ?? 0) > 0 ? '${part['compatibilities_count']} referencias de compatibilidad' : 'Genérico / sin compatibilidad documentada'}',
                        ),
                        isThreeLine: true,
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => openCatalogRecord(
                          context,
                          'part',
                          part['id'] as int,
                        ),
                      ),
                    );
                  },
                ),
        ),
        AtelierPaginator(
          from: _offset,
          to: _offset + _parts.length,
          total: _total,
          onPrevious: _loading || _offset == 0
              ? null
              : () {
                  _offset -= _limit;
                  _load();
                },
          onNext: _loading || _offset + _parts.length >= _total
              ? null
              : () {
                  _offset += _limit;
                  _load();
                },
        ),
      ],
    );
    return widget.embedded
        ? content
        : Scaffold(
            appBar: AppBar(title: const Text('Catálogo de repuestos')),
            body: Padding(padding: const EdgeInsets.all(16), child: content),
          );
  }
}

class _ManualPartDialog extends StatefulWidget {
  const _ManualPartDialog({required this.api});
  final ApiClient api;
  @override
  State<_ManualPartDialog> createState() => _ManualPartDialogState();
}

class _ManualPartDialogState extends State<_ManualPartDialog> {
  final _form = GlobalKey<FormState>();
  final _fields = {
    for (final field in [
      'name_es',
      'title',
      'sku',
      'system',
      'brand',
      'synonyms',
      'note',
    ])
      field: TextEditingController(),
  };
  Timer? _debounce;
  List<Json> _suggestions = [];
  bool _saving = false;
  String? _error;
  int _request = 0;
  @override
  void dispose() {
    _debounce?.cancel();
    for (final field in _fields.values) {
      field.dispose();
    }
    super.dispose();
  }

  Future<void> _suggest() async {
    final request = ++_request;
    final text = _fields['name_es']!.text.trim();
    if (text.length < 2) {
      if (mounted) setState(() => _suggestions = []);
      return;
    }
    try {
      final data =
          await widget.api.request(
                'GET',
                '/catalog/parts?q=${Uri.encodeQueryComponent(text)}&limit=5',
              )
              as Json;
      if (mounted && request == _request) {
        setState(() => _suggestions = jsonList(data['items']));
      }
    } catch (_) {
      /* Un problema de sugerencias no elimina lo escrito. */
    }
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      String text(String field) => _fields[field]!.text.trim();
      final saved =
          await widget.api.request(
                'POST',
                '/catalog/parts',
                body: {
                  'title': text('title').isEmpty
                      ? text('name_es')
                      : text('title'),
                  'name_es': text('name_es'),
                  if (text('sku').isNotEmpty) 'sku': text('sku'),
                  if (text('system').isNotEmpty) 'system': text('system'),
                  if (text('brand').isNotEmpty) 'brand': text('brand'),
                  'note': text('note'),
                  'synonyms': text('synonyms')
                      .split(',')
                      .map((word) => word.trim())
                      .where((word) => word.isNotEmpty)
                      .take(12)
                      .toList(),
                },
              )
              as Json;
      if (mounted) Navigator.pop(context, saved);
    } catch (failure) {
      if (mounted) {
        setState(() {
          _error = failure.toString();
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      title: const Text('Agregar repuesto manual'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Form(
            key: _form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Se guarda en la base con autor y procedencia. Las propuestas de personal requieren revisión antes de verificarse.',
                ),
                for (final entry in {
                  'name_es': 'Nombre en español',
                  'title': 'Nombre original (opcional)',
                  'sku': 'Referencia / código (opcional)',
                  'system': 'Sistema mecánico (opcional)',
                  'brand': 'Fabricante del repuesto (opcional)',
                  'synonyms': 'Sinónimos separados por coma',
                  'note': 'Fuente u observación (opcional)',
                }.entries)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: TextFormField(
                      controller: _fields[entry.key],
                      enabled: !_saving,
                      maxLength: entry.key == 'note'
                          ? 250
                          : entry.key == 'sku'
                          ? 80
                          : entry.key == 'system'
                          ? 40
                          : entry.key == 'brand'
                          ? 120
                          : 200,
                      decoration: InputDecoration(
                        labelText: entry.value,
                        counterText: '',
                      ),
                      validator: (value) =>
                          entry.key == 'name_es' &&
                              (value?.trim().length ?? 0) < 2
                          ? 'Escribe al menos dos caracteres'
                          : null,
                      onChanged: entry.key != 'name_es'
                          ? null
                          : (_) {
                              _debounce?.cancel();
                              _debounce = Timer(
                                const Duration(milliseconds: 300),
                                _suggest,
                              );
                            },
                    ),
                  ),
                if (_suggestions.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  const Text(
                    'Posibles coincidencias: reutiliza una ficha si corresponde.',
                  ),
                  for (final item in _suggestions)
                    TextButton(
                      onPressed: _saving
                          ? null
                          : () => Navigator.pop(context, item),
                      child: Text(
                        '${item['name_es'] ?? item['title']} · ${item['sku']}',
                      ),
                    ),
                ],
                if (_error != null)
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: Text(_saving ? 'Guardando…' : 'Guardar repuesto'),
        ),
      ],
    ),
  );
}
