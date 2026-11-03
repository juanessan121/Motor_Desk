import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart' show jsonList;
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';

const catalogSourceLabels = {
  'part_terms': 'lifeofcapo/car-api',
  'parts': 'ModelPartFinder',
  'vehicles': 'gor3a/vehicle-makes-models',
  'manual': 'Registro manual de MotorDesk',
};
const catalogOriginLabels = {
  'imported': 'Importado',
  'manual': 'Manual',
  'verified': 'Verificado',
  'needs_review': 'Pendiente de revisión',
  'unknown': 'Procedencia sin registrar',
};

Future<void> openCatalogRecord(BuildContext context, String entity, int id) =>
    Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => CatalogRecordPage(entity: entity, recordId: id),
      ),
    );

class CatalogRecordPage extends StatefulWidget {
  const CatalogRecordPage({
    super.key,
    required this.entity,
    required this.recordId,
  });
  final String entity;
  final int recordId;
  @override
  State<CatalogRecordPage> createState() => _CatalogRecordPageState();
}

class _CatalogRecordPageState extends State<CatalogRecordPage> {
  Json? _data;
  String? _error;
  int _offset = 0;
  bool _loading = false;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result =
          await context.read<WorkshopController>().api.request(
                'GET',
                '/catalog/records/${widget.entity}/${widget.recordId}?limit=50&offset=$_offset',
              )
              as Json;
      if (mounted) setState(() => _data = result);
    } catch (failure) {
      if (mounted) setState(() => _error = failure.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final record = _data?['record'] as Json? ?? {};
    final source = _data?['source'] as Json?;
    final details = jsonList(_data?['details']);
    final title =
        (record['name_es'] ??
                record['name'] ??
                record['label'] ??
                record['title'] ??
                'Ficha de catálogo')
            .toString();
    const labels = {
      'title': 'Nombre original',
      'sku': 'Referencia de catálogo / SKU',
      'mpn': 'Número de parte documentado',
      'country': 'País registrado',
      'brand': 'Fabricante del repuesto',
      'category': 'Categoría original',
      'system': 'Sistema mecánico',
      'year_start': 'Año inicial documentado',
      'year_end': 'Año final documentado',
      'body_type': 'Carrocería',
      'fuel_type': 'Combustible',
      'cylinders': 'Cilindros',
      'displacement_cc': 'Cilindrada (cc)',
      'power_hp': 'Potencia (HP)',
      'torque_nm': 'Par (Nm)',
      'transmission': 'Transmisión',
      'drivetrain': 'Tracción',
      'length_mm': 'Longitud (mm)',
      'width_mm': 'Anchura (mm)',
      'height_mm': 'Altura (mm)',
      'wheelbase_mm': 'Distancia entre ejes (mm)',
      'curb_weight_kg': 'Masa (kg)',
      'zero_to_100_s': '0–100 km/h (s)',
      'top_speed_kmh': 'Velocidad máxima (km/h)',
      'fuel_economy_l100': 'Consumo (l/100 km)',
    };
    return Scaffold(
      appBar: AppBar(title: const Text('Ficha del catálogo')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? EmptyState(
              title: 'No se pudo consultar la ficha',
              message: _error!,
              action: TextButton(
                onPressed: _load,
                child: const Text('Reintentar'),
              ),
            )
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 960),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                      Text(
                        '${catalogOriginLabels[record['origin']] ?? 'Procedencia sin registrar'} · ${catalogSourceLabels[record['source_key']] ?? record['source_key'] ?? 'Fuente no registrada'}',
                      ),
                      const SizedBox(height: 12),
                      if (jsonList(_data?['parents']).isNotEmpty)
                        Wrap(
                          children: [
                            for (final parent in jsonList(_data?['parents']))
                              TextButton(
                                onPressed: () => openCatalogRecord(
                                  context,
                                  parent['entity'] as String,
                                  parent['id'] as int,
                                ),
                                child: Text(parent['name'] as String),
                              ),
                          ],
                        ),
                      SectionCard(
                        title: 'Información disponible',
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            for (final entry in labels.entries)
                              if (record[entry.key] != null &&
                                  record[entry.key].toString().isNotEmpty)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 8),
                                  child: SelectableText(
                                    '${entry.value}: ${record[entry.key]}',
                                  ),
                                ),
                            if (record['synonyms'] is List &&
                                (record['synonyms'] as List).isNotEmpty)
                              SelectableText(
                                'Sinónimos: ${(record['synonyms'] as List).join(', ')}',
                              ),
                            if (record['review_required'] == true)
                              const Text(
                                'La denominación en español necesita revisión.',
                              ),
                            if (widget.entity == 'part')
                              const Text(
                                'Catálogo, no inventario: no se informan existencias, precios ni disponibilidad local. La fuente no aporta imagen ni descripción de esta ficha.',
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                      if (widget.entity == 'part' || widget.entity == 'engine')
                        SectionCard(
                          title: widget.entity == 'part'
                              ? 'Compatibilidad declarada por la fuente'
                              : 'Especificaciones originales de la fuente',
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              if (details.isEmpty)
                                Text(
                                  widget.entity == 'part'
                                      ? 'Componente genérico o sin relaciones de compatibilidad documentadas. Una similitud de nombre no verifica compatibilidad.'
                                      : 'Sin especificaciones adicionales registradas.',
                                ),
                              for (final item in details)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 10),
                                  child: SelectableText(
                                    widget.entity == 'engine'
                                        ? '${item['key']}: ${item['value']}'
                                        : '${item['make']} · ${item['model']}\n${item['year_from'] ?? 'Sin año inicial'} — ${item['year_to'] ?? 'Sin año final'} · Fuente: ${item['source_key']}',
                                  ),
                                ),
                              if ((_data?['details_total'] as int? ?? 0) > 50)
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.end,
                                  children: [
                                    Text(
                                      '${_offset + 1}–${_offset + details.length} de ${_data!['details_total']}',
                                    ),
                                    IconButton(
                                      tooltip: 'Página anterior',
                                      onPressed: _offset == 0
                                          ? null
                                          : () {
                                              _offset -= 50;
                                              _load();
                                            },
                                      icon: const Icon(Icons.chevron_left),
                                    ),
                                    IconButton(
                                      tooltip: 'Página siguiente',
                                      onPressed:
                                          _offset + details.length >=
                                              (_data!['details_total'] as int)
                                          ? null
                                          : () {
                                              _offset += 50;
                                              _load();
                                            },
                                      icon: const Icon(Icons.chevron_right),
                                    ),
                                  ],
                                ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 18),
                      SectionCard(
                        title: 'Procedencia y condiciones',
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              source?['title']?.toString() ??
                                  (record['source_key'] == 'manual'
                                      ? 'Registro introducido manualmente en MotorDesk.'
                                      : 'No hay metadatos adicionales de la fuente.'),
                            ),
                            if (source != null) ...[
                              SelectableText(
                                'Licencia declarada: ${source['license']}',
                              ),
                              SelectableText(source['url'] as String),
                              SelectableText(source['license_url'] as String),
                              SelectableText(source['attribution'] as String),
                              TextButton.icon(
                                onPressed: () => Clipboard.setData(
                                  ClipboardData(
                                    text:
                                        '${source['url']}\n${source['attribution']}',
                                  ),
                                ),
                                icon: const Icon(Icons.copy),
                                label: const Text('Copiar atribución'),
                              ),
                            ],
                            Text(_data?['notice']?.toString() ?? ''),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
    );
  }
}

/// Autocompletado remoto, usado solo para relaciones de catálogo conocidas.
class CatalogReferenceSearch extends StatefulWidget {
  const CatalogReferenceSearch({
    super.key,
    required this.label,
    required this.api,
    required this.endpoint,
    required this.onSelected,
    this.onTyped,
  });
  final String label;
  final ApiClient api;
  final String endpoint;
  final ValueChanged<Json> onSelected;
  final VoidCallback? onTyped;
  @override
  State<CatalogReferenceSearch> createState() => _CatalogReferenceSearchState();
}

class _CatalogReferenceSearchState extends State<CatalogReferenceSearch> {
  String? _error;
  int _request = 0;
  @override
  Widget build(BuildContext context) => Autocomplete<Json>(
    displayStringForOption: (item) =>
        (item['name'] ?? item['name_es'] ?? item['label'] ?? item['title'])
            as String,
    optionsBuilder: (text) async {
      final request = ++_request;
      if (text.text.trim().length < 2) return const Iterable<Json>.empty();
      try {
        final data =
            await widget.api.request(
                  'GET',
                  '${widget.endpoint}&limit=30&q=${Uri.encodeQueryComponent(text.text.trim())}',
                )
                as Json;
        if (mounted && request == _request && _error != null) {
          setState(() => _error = null);
        }
        return jsonList(data['items']);
      } catch (failure) {
        if (mounted && request == _request) {
          setState(() => _error = failure.toString());
        }
        return const Iterable<Json>.empty();
      }
    },
    onSelected: widget.onSelected,
    fieldViewBuilder: (context, controller, focus, submitted) => TextFormField(
      controller: controller,
      focusNode: focus,
      decoration: InputDecoration(
        labelText: widget.label,
        helperText: 'Escribe al menos dos letras',
        errorText: _error,
      ),
      onChanged: (_) => widget.onTyped?.call(),
      onFieldSubmitted: (_) => submitted(),
    ),
  );
}
