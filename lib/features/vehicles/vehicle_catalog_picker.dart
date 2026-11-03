import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/models/entities.dart' show jsonList;
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';

/// Cascada de selección con catálogo: Marca → Modelo → Generación → Motor.
///
/// Cada paso es opcional: no se obliga a recorrer cinco pantallas para
/// registrar un vehículo del que solo se conoce marca y modelo. Cuando la
/// búsqueda no encuentra nada, el propio campo ofrece registrar lo que falta.
/// No es un adorno: el catálogo de fuentes es global y se comprobó que no
/// incluye Chevrolet Sail, Optra ni Lanos, habituales en Ecuador.
class VehicleCatalogPicker extends StatefulWidget {
  const VehicleCatalogPicker({
    super.key,
    required this.api,
    required this.brandController,
    required this.modelController,
    required this.onChanged,
    this.showYear = true,
    this.initialReference,
  });

  final ApiClient api;
  final TextEditingController brandController;
  final TextEditingController modelController;
  final ValueChanged<Json?> onChanged;
  final bool showYear;
  final Json? initialReference;

  @override
  State<VehicleCatalogPicker> createState() => _VehicleCatalogPickerState();
}

class _VehicleCatalogPickerState extends State<VehicleCatalogPicker> {
  final Map<String, Json?> _selected = {
    'make': null,
    'model': null,
    'generation': null,
    'engine': null,
  };
  final Map<String, List<Json>> _items = {};
  final Set<String> _busy = {};
  final Map<String, int> _requests = {};
  bool _applying = false;
  String? _error;
  int? _year;

  static const _levelOrder = ['make', 'model', 'generation', 'engine'];

  @override
  void initState() {
    super.initState();
    final ref = widget.initialReference;
    if (ref != null) {
      for (final level in _levelOrder) {
        if (ref['${level}_id'] != null) {
          _selected[level] = {
            'id': ref['${level}_id'],
            'name':
                ref['${level}_name'] ?? (ref['engine'] as Map?)?['label'] ?? '',
          };
        }
      }
    }
    widget.brandController.addListener(_textChanged);
    widget.modelController.addListener(_textChanged);
    _search('make', '');
  }

  @override
  void dispose() {
    widget.brandController.removeListener(_textChanged);
    widget.modelController.removeListener(_textChanged);
    super.dispose();
  }

  void _textChanged() {
    if (_applying) return;
    if (_selected['make'] != null &&
        widget.brandController.text.trim() != _label('make')) {
      _clearFrom('make');
    } else if (_selected['model'] != null &&
        widget.modelController.text.trim() != _label('model')) {
      _clearFrom('model');
    }
  }

  void _clearFrom(String level) {
    final start = _levelOrder.indexOf(level);
    setState(() {
      for (var index = start; index < _levelOrder.length; index++) {
        _selected[_levelOrder[index]] = null;
        _items[_levelOrder[index]] = [];
        _requests.update(
          _levelOrder[index],
          (value) => value + 1,
          ifAbsent: () => 1,
        );
        _busy.remove(_levelOrder[index]);
      }
    });
    widget.onChanged(_selection);
    final parentIndex = start - 1;
    if (parentIndex < 0 || _selected[_levelOrder[parentIndex]] != null) {
      _search(level, '');
    }
  }

  Future<void> _search(String level, String q) async {
    final request = (_requests[level] ?? 0) + 1;
    _requests[level] = request;
    setState(() {
      _busy.add(level);
      _error = null;
    });
    try {
      final data = await widget.api.request('GET', _endpoint(level, q));
      if (mounted && _requests[level] == request) {
        setState(() => _items[level] = jsonList(data));
      }
    } catch (error) {
      if (mounted && _requests[level] == request) {
        setState(() => _error = '$error');
      }
    } finally {
      if (mounted && _requests[level] == request) {
        setState(() => _busy.remove(level));
      }
    }
  }

  String _endpoint(String level, String q) {
    final query = q.isEmpty ? '' : '&q=${Uri.encodeQueryComponent(q)}';
    switch (level) {
      case 'make':
        return '/catalog/makes?logo=true&limit=100$query';
      case 'model':
        return '/catalog/models?make_id=${_selected['make']!['id']}&limit=200$query';
      case 'generation':
        return '/catalog/generations?model_id=${_selected['model']!['id']}';
      case 'engine':
        return '/catalog/engines?generation_id=${_selected['generation']!['id']}&limit=1000';
      default:
        return '';
    }
  }

  Future<void> _choose(String level, Json item) async {
    final start = _levelOrder.indexOf(level);
    _applying = true;
    setState(() {
      for (var index = start; index < _levelOrder.length; index++) {
        _selected[_levelOrder[index]] = null;
        _items[_levelOrder[index]] = [];
        _requests.update(
          _levelOrder[index],
          (value) => value + 1,
          ifAbsent: () => 1,
        );
        _busy.remove(_levelOrder[index]);
      }
      _selected[level] = item;
      if (level == 'make') {
        widget.brandController.text = item['name'] as String;
        widget.modelController.clear();
      }
      if (level == 'model') {
        widget.modelController.text = item['name'] as String;
      }
    });
    _applying = false;
    widget.onChanged(_selection);
    final next = start + 1;
    if (next < _levelOrder.length) {
      await _search(_levelOrder[next], '');
    }
  }

  Json? get _selection {
    if (_selected['make'] == null) return null;
    return {..._selected, 'year': _year, 'source': 'catalog'};
  }

  Future<void> _register(String level) async {
    final label = switch (level) {
      'make' => 'marca',
      'model' => 'modelo',
      'generation' => 'generación',
      _ => 'motorización',
    };
    final index = _levelOrder.indexOf(level);
    final parent = index == 0 ? null : _levelOrder[index - 1];
    final body = switch (level) {
      'make' => <String, dynamic>{},
      'model' => {'make_id': _selected['make']!['id']},
      'generation' => {'model_id': _selected['model']!['id']},
      _ => {'generation_id': _selected['generation']!['id']},
    };
    final created = await showDialog<Json>(
      context: context,
      builder: (context) => _ManualEntryDialog(
        level: level,
        body: body,
        label: label,
        parentLabel: parent == null ? '' : _label(parent),
      ),
    );
    if (created == null || !mounted) return;
    await _choose(level, created);
  }

  String _label(String level) {
    final item = _selected[level];
    return item == null ? '' : (item['name'] ?? item['label']) as String;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Catálogo de referencia',
                style: theme.textTheme.labelLarge,
              ),
            ),
            if (_busy.isNotEmpty)
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          'Datos de referencia del catálogo. No son una verificación de este '
          'vehículo en concreto.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 12),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              _error!,
              style: TextStyle(color: theme.colorScheme.error, fontSize: 12),
            ),
          ),
        _level(context, 'make', 'Marca', Icons.directions_car_outlined),
        if (_selected['make'] != null) ...[
          _level(
            context,
            'model',
            'Modelo',
            Icons.directions_car_filled_outlined,
          ),
          if (widget.showYear) _yearField(theme),
          if (_selected['model'] != null)
            _list(
              context,
              'generation',
              'Generación',
              Icons.build_circle_outlined,
            ),
          if (_selected['generation'] != null)
            _list(context, 'engine', 'Motorización', Icons.settings_outlined),
        ],
      ],
    );
  }

  Widget _level(
    BuildContext context,
    String level,
    String title,
    IconData icon,
  ) {
    final selected = _selected[level];
    return _block(context, icon, title, [
      if (selected != null)
        InputChip(
          avatar: Icon(icon, size: 16),
          label: Text(_label(level), overflow: TextOverflow.ellipsis),
          onDeleted: () => _clearFrom(level),
          deleteIcon: const Icon(Icons.close, size: 16),
        )
      else ...[
        _CatalogSearchBox(
          hint: 'Buscar $title'.toLowerCase(),
          onSearch: (q) => _search(level, q),
        ),
        ..._results(context, level),
        if (!_busy.contains(level) && (_items[level]?.isEmpty ?? true))
          TextButton.icon(
            onPressed: () => _register(level),
            icon: const Icon(Icons.add, size: 18),
            label: Text('No encuentro $title'.toLowerCase()),
          ),
      ],
    ]);
  }

  Widget _list(
    BuildContext context,
    String level,
    String title,
    IconData icon,
  ) => _block(context, icon, title, [
    if (_selected[level] != null)
      InputChip(label: Text(_label(level)), onDeleted: () => _clearFrom(level))
    else ...[
      for (final item in (_items[level] ?? []))
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          title: Text(
            _describe(level, item),
            style: const TextStyle(fontSize: 13),
          ),
          onTap: () => _choose(level, item),
        ),
      if (!_busy.contains(level) && (_items[level]?.isEmpty ?? true))
        TextButton.icon(
          onPressed: () => _register(level),
          icon: const Icon(Icons.add, size: 18),
          label: Text('No encuentro $title'.toLowerCase()),
        ),
    ],
  ]);

  List<Widget> _results(BuildContext context, String level) => [
    for (final item in (_items[level] ?? []).take(40))
      ListTile(
        dense: true,
        contentPadding: EdgeInsets.zero,
        leading: level == 'make' && item['logo_url'] != null
            ? CircleAvatar(
                radius: 14,
                backgroundImage: NetworkImage(item['logo_url'] as String),
              )
            : null,
        title: Text(
          _describe(level, item),
          style: const TextStyle(fontSize: 13),
        ),
        onTap: () => _choose(level, item),
      ),
  ];

  Widget _yearField(ThemeData theme) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(
      children: [
        Padding(
          padding: const EdgeInsets.only(right: 8),
          child: Icon(Icons.calendar_today_outlined, size: 18),
        ),
        Expanded(
          child: DropdownButtonFormField<int?>(
            initialValue: _year,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Año', isDense: true),
            items: [
              const DropdownMenuItem(
                value: null,
                child: Text('Sin especificar'),
              ),
              for (var year = DateTime.now().year; year >= 1950; year--)
                DropdownMenuItem(value: year, child: Text('$year')),
            ],
            onChanged: (value) {
              setState(() => _year = value);
              widget.onChanged(_selection);
            },
          ),
        ),
      ],
    ),
  );

  Widget _block(
    BuildContext context,
    IconData icon,
    String title,
    List<Widget> children,
  ) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 12, right: 8),
          child: Icon(icon, size: 18),
        ),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 12, bottom: 4),
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ),
              ...children,
            ],
          ),
        ),
      ],
    ),
  );

  String _describe(String level, Json item) {
    if (level == 'engine') return _engineLabel(item);
    final parts = <String>[item['name'] as String];
    if (item['year_start'] != null) {
      parts.add(
        '${item['year_start']}'
        '${item['year_end'] == null ? '' : '-${item['year_end']}'}',
      );
    }
    return parts.join(' · ');
  }

  String _engineLabel(Json engine) {
    final parts = <String>[
      if (engine['label'] != null) engine['label'] as String,
      if (engine['displacement_cc'] != null)
        '${(engine['displacement_cc'] as num).round()} cc',
      if (engine['power_hp'] != null)
        '${(engine['power_hp'] as num).round()} hp',
      if (engine['fuel_type'] != null) engine['fuel_type'] as String,
    ];
    return parts.isEmpty ? 'Sin especificar' : parts.join(' · ');
  }
}

class _CatalogSearchBox extends StatefulWidget {
  const _CatalogSearchBox({required this.hint, required this.onSearch});

  final String hint;
  final ValueChanged<String> onSearch;

  @override
  State<_CatalogSearchBox> createState() => _CatalogSearchBoxState();
}

class _CatalogSearchBoxState extends State<_CatalogSearchBox> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => TextField(
    controller: _controller,
    decoration: InputDecoration(
      hintText: widget.hint,
      isDense: true,
      suffixIcon: IconButton(
        icon: const Icon(Icons.search, size: 18),
        tooltip: 'Buscar en el catálogo',
        onPressed: () => widget.onSearch(_controller.text.trim()),
      ),
    ),
    onSubmitted: (value) => widget.onSearch(value.trim()),
  );
}

/// Diálogo de registro manual. Persiste en la base con autor y procedencia.
class _ManualEntryDialog extends StatefulWidget {
  const _ManualEntryDialog({
    required this.level,
    required this.body,
    required this.label,
    required this.parentLabel,
  });

  final String level;
  final Map<String, dynamic> body;
  final String label;
  final String parentLabel;

  @override
  State<_ManualEntryDialog> createState() => _ManualEntryDialogState();
}

class _ManualEntryDialogState extends State<_ManualEntryDialog> {
  final _name = TextEditingController();
  final _note = TextEditingController();
  bool _busy = false;
  String? _error;

  /// El campo que cada nivel espera recibir.
  String get _nameField => widget.level == 'engine' ? 'label' : 'name';

  @override
  void dispose() {
    _name.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty) {
      setState(() => _error = 'Escribe el nombre');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final created =
          await context.read<WorkshopController>().api.request(
                'POST',
                '/catalog/${widget.level == 'engine' ? 'engines' : '${widget.level}s'}',
                body: {
                  ...widget.body,
                  _nameField: _name.text.trim(),
                  'note': _note.text.trim(),
                },
              )
              as Json;
      if (mounted) Navigator.pop(context, created);
    } catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = '$error';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('Registrar ${widget.label}'),
    content: SizedBox(
      width: 420,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            widget.parentLabel.isEmpty
                ? 'Se guarda en el catálogo del taller con tu nombre como autor.'
                : 'Se añadirá a «${widget.parentLabel}» y quedará marcado como '
                      'registro manual, con tu nombre como autor.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _name,
            autofocus: true,
            textCapitalization: TextCapitalization.words,
            decoration: InputDecoration(
              labelText: widget.level == 'engine' ? 'Denominación' : 'Nombre',
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _note,
            decoration: const InputDecoration(
              labelText: 'Nota (opcional)',
              hintText: 'Fuente, observación…',
            ),
            maxLines: 2,
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: _busy ? null : () => Navigator.pop(context),
        child: const Text('Cancelar'),
      ),
      FilledButton(
        onPressed: _busy ? null : _submit,
        child: _busy
            ? const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Text('Registrar'),
      ),
    ],
  );
}
