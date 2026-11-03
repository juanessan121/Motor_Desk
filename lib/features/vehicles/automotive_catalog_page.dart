import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart' show jsonList;
import '../../core/network/api_client.dart';
import '../../core/state/make_logo_cache.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';
import 'catalog_parts_page.dart';
import 'catalog_record_page.dart';
import 'catalog_review_page.dart';

/// Consulta de maestros, separada de las propuestas manuales por revisar.
class AutomotiveCatalogPage extends StatefulWidget {
  const AutomotiveCatalogPage({super.key, this.standalone = false});
  final bool standalone;
  @override
  State<AutomotiveCatalogPage> createState() => _AutomotiveCatalogPageState();
}

class _AutomotiveCatalogPageState extends State<AutomotiveCatalogPage> {
  Json? _overview;
  String? _error;
  @override
  void initState() {
    super.initState();
    final user = context.read<WorkshopController>();
    if (user.isAdmin || user.isMechanic) _load();
  }

  Future<void> _load() async {
    try {
      final data =
          await context.read<WorkshopController>().api.request(
                'GET',
                '/catalog/overview',
              )
              as Json;
      if (mounted) {
        setState(() {
          _overview = data;
          _error = null;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => _error = failure.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final counts = _overview?['counts'] as Json? ?? {};
    final body = !state.isAdmin && !state.isMechanic
        ? const EmptyState(
            title: 'Acceso restringido',
            message: 'Consulta técnica del personal del taller.',
          )
        : DefaultTabController(
            length: 2,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                PageHeading(
                  title: 'Catálogo automotriz',
                  subtitle:
                      'Datos maestros importados y manuales. No es la cola de revisión ni un inventario.',
                  action: state.isAdmin
                      ? OutlinedButton.icon(
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => const CatalogReviewPage(),
                            ),
                          ),
                          icon: const Icon(Icons.fact_check_outlined),
                          label: const Text('Revisar propuestas'),
                        )
                      : null,
                ),
                if (_error != null)
                  Wrap(
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text('No se pudieron verificar los totales: $_error'),
                      TextButton(
                        onPressed: _load,
                        child: const Text('Reintentar'),
                      ),
                    ],
                  ),
                if (_overview != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 6,
                      children: [
                        for (final entry in {
                          'make': 'Marcas',
                          'model': 'Modelos',
                          'generation': 'Generaciones',
                          'engine': 'Motores',
                          'part': 'Repuestos',
                        }.entries)
                          AtelierBadge(
                            '${entry.value}: ${counts[entry.key] ?? '—'}',
                            dense: true,
                          ),
                      ],
                    ),
                  ),
                const TabBar(
                  tabs: [
                    Tab(
                      icon: Icon(Icons.directions_car_outlined),
                      text: 'Marcas y vehículos',
                    ),
                    Tab(icon: Icon(Icons.build_outlined), text: 'Repuestos'),
                  ],
                ),
                const Expanded(
                  child: TabBarView(
                    children: [
                      _VehicleCatalogBrowser(),
                      CatalogPartsPage(embedded: true),
                    ],
                  ),
                ),
              ],
            ),
          );
    return widget.standalone
        ? Scaffold(
            appBar: AppBar(title: const Text('Consulta del catálogo')),
            body: Padding(padding: const EdgeInsets.all(16), child: body),
          )
        : body;
  }
}

class _VehicleCatalogBrowser extends StatefulWidget {
  const _VehicleCatalogBrowser();
  @override
  State<_VehicleCatalogBrowser> createState() => _VehicleCatalogBrowserState();
}

class _VehicleCatalogBrowserState extends State<_VehicleCatalogBrowser> {
  static const _levels = ['make', 'model', 'generation', 'engine'];
  static const _labels = {
    'make': 'Marcas',
    'model': 'Modelos',
    'generation': 'Generaciones',
    'engine': 'Motores / versiones',
  };
  final _search = TextEditingController();
  final _year = TextEditingController();
  final List<Json> _parents = [];
  Timer? _debounce;
  String _entity = 'make';
  String? _error;
  bool _loading = false;
  List<Json> _items = [];
  int _offset = 0, _total = 0, _request = 0;
  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    _year.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    final request = ++_request;
    setState(() {
      _loading = true;
      _error = null;
    });
    final year = int.tryParse(_year.text.trim());
    try {
      if (_entity != 'make' &&
          _year.text.isNotEmpty &&
          (year == null || year < 1900 || year > 2200)) {
        throw const ApiException('Usa un año de 1900 a 2200.');
      }
      final params = {
        'entity': _entity,
        'q': _search.text.trim(),
        'limit': '20',
        'offset': '$_offset',
        for (final parent in _parents)
          '${parent['entity']}_id': '${parent['id']}',
        if (year != null && _entity != 'make') 'year': '$year',
      };
      final data =
          await context.read<WorkshopController>().api.request(
                'GET',
                '/catalog/browse?${Uri(queryParameters: params).query}',
              )
              as Json;
      if (mounted && request == _request) {
        setState(() {
          _items = jsonList(data['items']);
          _total = data['total'] as int;
        });
      }
    } catch (failure) {
      if (mounted && request == _request) {
        setState(() => _error = failure.toString());
      }
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  void _reset() {
    _offset = 0;
    _load();
  }

  void _enter(Json item) {
    if (_entity == 'engine') {
      openCatalogRecord(context, _entity, item['id'] as int);
      return;
    }
    setState(() {
      _parents.add({...item, 'entity': _entity});
      _entity = _levels[_levels.indexOf(_entity) + 1];
      _search.clear();
    });
    _reset();
  }

  void _back(int length) {
    setState(() {
      _parents.removeRange(length, _parents.length);
      _entity = _levels[length];
      _search.clear();
    });
    _reset();
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const SizedBox(height: 10),
      Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          TextButton(onPressed: () => _back(0), child: const Text('Marcas')),
          for (var index = 0; index < _parents.length; index++)
            TextButton.icon(
              onPressed: () => _back(index + 1),
              icon: const Icon(Icons.chevron_right, size: 16),
              label: Text(_parents[index]['name'] as String),
            ),
        ],
      ),
      Wrap(
        spacing: 12,
        runSpacing: 10,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          SizedBox(
            width: 330,
            child: TextField(
              controller: _search,
              maxLength: 120,
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                labelText: 'Buscar en ${_labels[_entity]!.toLowerCase()}',
                counterText: '',
              ),
              onChanged: (_) {
                _debounce?.cancel();
                _debounce = Timer(const Duration(milliseconds: 300), _reset);
              },
              onSubmitted: (_) {
                _debounce?.cancel();
                _reset();
              },
            ),
          ),
          if (_entity != 'make')
            SizedBox(
              width: 160,
              child: TextField(
                controller: _year,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Año (opcional)'),
                onChanged: (_) {
                  _debounce?.cancel();
                  _debounce = Timer(const Duration(milliseconds: 400), _reset);
                },
              ),
            ),
          Text('${_labels[_entity]}: $_total'),
          IconButton(
            tooltip: 'Actualizar resultados',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      const Padding(
        padding: EdgeInsets.symmetric(vertical: 10),
        child: Text(
          'Referencia global: generaciones y versiones no identifican por sí solas la motorización del vehículo real.',
        ),
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
            : _items.isEmpty
            ? const EmptyState(
                title: 'Sin coincidencias en esta referencia',
                message:
                    'Prueba otra búsqueda o retrocede en la jerarquía. Las opciones ausentes pueden registrarse desde Ingresar vehículo.',
              )
            : ListView.separated(
                itemCount: _items.length,
                separatorBuilder: (_, _) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  final item = _items[index];
                  return Card(
                    child: ListTile(
                      contentPadding: const EdgeInsets.all(14),
                      leading: _entity == 'make'
                          ? MakeLogo(
                              make: item['name'] as String?,
                              logoUrl: item['logo_url'] as String?,
                              loadCatalog: false,
                            )
                          : const Icon(Icons.directions_car_outlined),
                      title: Text((item['name'] ?? item['label']) as String),
                      subtitle: Text(
                        '${item['year_start'] ?? ''}${item['year_end'] == null ? '' : ' – ${item['year_end']}'} '
                        '${item['power_hp'] == null ? '' : ' · ${item['power_hp']} HP'}\n${catalogOriginLabels[item['origin']] ?? item['origin']} · ${catalogSourceLabels[item['source_key']] ?? item['source_key'] ?? 'Fuente no registrada'}',
                      ),
                      onTap: () => _enter(item),
                      trailing: IconButton(
                        tooltip: 'Ver ficha técnica',
                        onPressed: () => openCatalogRecord(
                          context,
                          _entity,
                          item['id'] as int,
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
        to: _offset + _items.length,
        total: _total,
        onPrevious: _loading || _offset == 0
            ? null
            : () {
                _offset -= 20;
                _load();
              },
        onNext: _loading || _offset + _items.length >= _total
            ? null
            : () {
                _offset += 20;
                _load();
              },
      ),
    ],
  );
}
