import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config_model.dart';
import '../../core/config/theme_controller.dart';
import '../../core/models/entities.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';

class BrandingPage extends StatefulWidget {
  const BrandingPage({super.key});
  @override
  State<BrandingPage> createState() => _BrandingPageState();
}

class _BrandingPageState extends State<BrandingPage> {
  late AppConfigModel draft;
  late final Map<String, TextEditingController> fields;
  final form = GlobalKey<FormState>();
  List<Json> devices = [];
  Map<String, bool> overrides = {};
  String scope = 'global';
  bool saving = false;
  bool loadingFlags = false;
  String? flagError;
  List<Json> themeCatalog = [];
  String themeDefault = 'pitlane';

  @override
  void initState() {
    super.initState();
    draft = context.read<ThemeController>().config;
    fields = {
      'name': TextEditingController(text: draft.name),
      'tagline': TextEditingController(text: draft.tagline),
      'welcome': TextEditingController(text: draft.welcome),
      'tax_rate': TextEditingController(
        text:
            ((double.tryParse('${draft.regional['tax_rate'] ?? '0.15'}') ??
                        0.15) *
                    100)
                .toStringAsFixed(2),
      ),
      'logo': TextEditingController(
        text: draft.logo.startsWith('data:') ? '' : draft.logo,
      ),
      for (final entry in draft.colors.entries)
        entry.key: TextEditingController(text: entry.value),
    };
    _loadDevices();
    _loadThemes();
  }

  /// El catálogo de temas lo publica el servidor: la interfaz no lleva paletas
  /// propias que puedan desincronizarse de las que el taller publica.
  Future<void> _loadThemes() async {
    try {
      final result = await context.read<WorkshopController>().api.request(
        'GET',
        '/config/themes',
      );
      if (!mounted) return;
      setState(() {
        themeCatalog = jsonList(result['themes']);
        themeDefault = result['default'] as String? ?? 'pitlane';
      });
    } catch (failure) {
      if (mounted) setState(() => flagError = failure.toString());
    }
  }

  /// Al cambiar de tema hay que volver a pedir la configuración efectiva: la
  /// paleta del tema la resuelve el servidor, no el cliente.
  Future<void> _reloadThemes() async {
    try {
      await context.read<ThemeController>().refresh();
    } catch (_) {
      // Un fallo al recargar la paleta no debe bloquear el borrador: el tema
      // se guardará y se aplicará al recargar.
    }
  }

  Future<void> _loadDevices() async {
    try {
      final result = await context.read<WorkshopController>().api.request(
        'GET',
        '/devices',
      );
      if (mounted) setState(() => devices = jsonList(result));
    } catch (failure) {
      if (mounted) setState(() => flagError = failure.toString());
    }
  }

  @override
  void dispose() {
    for (final controller in fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> uploadLogo() async {
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['png', 'jpg', 'jpeg', 'webp'],
    );
    if (file == null) return;
    final length = await file.length();
    if (length == null || length > 256 * 1024) {
      throw const ApiException('El logo debe pesar hasta 256 KB.');
    }
    final bytes = await file.readAsBytes();
    if (!mounted) return;
    final mime = switch (file.extension?.toLowerCase()) {
      'png' => 'png',
      'webp' => 'webp',
      _ => 'jpeg',
    };
    setState(() {
      draft = draft.copyWith(
        logo: 'data:image/$mime;base64,${base64Encode(bytes)}',
      );
      fields['logo']!.clear();
    });
  }

  Future<void> saveBranding() async {
    if (!form.currentState!.validate()) return;
    setState(() => saving = true);
    final theme = context.read<ThemeController>();
    await runAction(
      context,
      () async {
        await theme.save(draft);
        if (mounted) setState(() => draft = theme.config);
      },
      success: 'Diseño publicado. Las sesiones conectadas recibirán el cambio.',
    );
    if (mounted) setState(() => saving = false);
  }

  Future<void> changeScope(String selected) async {
    setState(() {
      scope = selected;
      loadingFlags = true;
      flagError = null;
    });
    try {
      Map<String, bool> result = {};
      if (selected.startsWith('user:')) {
        final data =
            await context.read<WorkshopController>().api.request(
                  'GET',
                  '/config/users/${selected.split(':').last}',
                )
                as Json;
        result = Map<String, bool>.from(data['features'] as Map);
      } else if (selected.startsWith('device:')) {
        result = Map<String, bool>.from(
          devices.firstWhere(
                (row) => 'device:${row['id']}' == selected,
              )['features']
              as Map,
        );
      }
      if (mounted && scope == selected) {
        setState(
          () => overrides = {
            for (final key in featureLabels.keys) key: result[key] ?? true,
          },
        );
      }
    } catch (failure) {
      if (mounted) setState(() => flagError = failure.toString());
    } finally {
      if (mounted && scope == selected) setState(() => loadingFlags = false);
    }
  }

  Future<void> saveFlags() async {
    if (scope == 'global') return saveBranding();
    setState(() => saving = true);
    await runAction(
      context,
      () async {
        final pieces = scope.split(':');
        final endpoint = pieces.first == 'user'
            ? '/config/users/${pieces.last}'
            : '/config/devices/${pieces.last}';
        await context.read<WorkshopController>().api.request(
          'PUT',
          endpoint,
          body: {'features': overrides},
        );
        await _loadDevices();
      },
      success:
          'Permisos publicados. El bloqueo global siempre tiene prioridad.',
    );
    if (mounted) setState(() => saving = false);
  }

  void resetDraft() {
    final current = context.read<ThemeController>().config;
    setState(() {
      draft = current;
      fields['name']!.text = current.name;
      fields['tagline']!.text = current.tagline;
      fields['welcome']!.text = current.welcome;
      fields['logo']!.text = current.logo.startsWith('data:')
          ? ''
          : current.logo;
      for (final entry in current.colors.entries) {
        fields[entry.key]!.text = entry.value;
      }
    });
  }

  Widget brandForm() => Form(
    key: form,
    child: Column(
      children: [
        SectionCard(
          title: 'Identidad de tu taller',
          child: Column(
            children: [
              TextFormField(
                controller: fields['name'],
                maxLength: 80,
                decoration: const InputDecoration(
                  labelText: 'Nombre comercial',
                  counterText: '',
                ),
                validator: (value) => value?.trim().isEmpty ?? true
                    ? 'El nombre es obligatorio'
                    : null,
                onChanged: (value) =>
                    setState(() => draft = draft.copyWith(name: value)),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: fields['tagline'],
                maxLength: 150,
                decoration: const InputDecoration(
                  labelText: 'Eslogan',
                  counterText: '',
                ),
                onChanged: (value) =>
                    setState(() => draft = draft.copyWith(tagline: value)),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: fields['welcome'],
                maxLength: 150,
                decoration: const InputDecoration(
                  labelText: 'Mensaje de bienvenida',
                  counterText: '',
                ),
                onChanged: (value) =>
                    setState(() => draft = draft.copyWith(welcome: value)),
              ),
              const SizedBox(height: 20),
              TextFormField(
                controller: fields['tax_rate'],
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Impuesto para nuevas órdenes (%)',
                  helperText:
                      'Verifique la tasa aplicable. Las órdenes existentes conservan su tasa.',
                ),
                validator: (value) {
                  final rate = double.tryParse(
                    (value ?? '').replaceAll(',', '.'),
                  );
                  return rate == null ||
                          !rate.isFinite ||
                          rate < 0 ||
                          rate > 100
                      ? 'Ingrese un porcentaje entre 0 y 100'
                      : null;
                },
                onChanged: (value) {
                  final rate = double.tryParse(value.replaceAll(',', '.'));
                  if (rate != null && rate.isFinite) {
                    setState(
                      () => draft = draft.copyWith(
                        regional: {
                          ...draft.regional,
                          'tax_rate': (rate / 100).toStringAsFixed(4),
                        },
                      ),
                    );
                  }
                },
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  BrandLogo(config: draft, size: 52),
                  const SizedBox(width: 16),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => runAction(context, uploadLogo),
                      icon: const Icon(Icons.file_upload_outlined, size: 18),
                      label: const Text('Subir logo'),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Quitar logo',
                    onPressed: () => setState(() {
                      draft = draft.copyWith(logo: '');
                      fields['logo']!.clear();
                    }),
                    icon: const Icon(Icons.close, size: 18),
                  ),
                ],
              ),
              const SizedBox(height: 15),
              TextFormField(
                controller: fields['logo'],
                decoration: InputDecoration(
                  labelText: 'O utiliza una URL HTTPS',
                  helperText: draft.logo.startsWith('data:')
                      ? 'Logo Base64 cargado · PNG/JPEG/WebP · hasta 256 KB'
                      : 'La URL debe permitir cargar imágenes desde tu dominio (CORS).',
                ),
                onChanged: (value) =>
                    setState(() => draft = draft.copyWith(logo: value.trim())),
              ),
            ],
          ),
        ),
        const SizedBox(height: 22),
        _ThemeSelector(
          catalog: themeCatalog,
          selected: draft.themeKey,
          onSelect: (key) {
            setState(() => draft = draft.copyWith(themeKey: key));
            _reloadThemes();
          },
        ),
        const SizedBox(height: 22),
        SectionCard(
          title: 'Paleta de colores',
          subtitle:
              'Tu identidad manda sobre la del tema. Publicar no es automático: '
              'cambia el borrador y pulsa Publicar.',
          child: LayoutBuilder(
            builder: (context, constraints) => Wrap(
              spacing: 16,
              runSpacing: 18,
              children: [
                for (final entry in {
                  'primary': 'Primario',
                  'secondary': 'Secundario',
                  'background': 'Fondo',
                  'surface': 'Superficie',
                }.entries)
                  SizedBox(
                    width: constraints.maxWidth < 420
                        ? constraints.maxWidth
                        : (constraints.maxWidth - 16) / 2,
                    child: TextFormField(
                      controller: fields[entry.key],
                      decoration: InputDecoration(
                        labelText: entry.value,
                        suffixIcon: Padding(
                          padding: const EdgeInsets.all(9),
                          child: InkWell(
                            borderRadius: BorderRadius.circular(8),
                            onTap: () async {
                              final color = await selectColor(
                                context,
                                draft.color(entry.key),
                              );
                              if (color != null && mounted) {
                                final hex =
                                    '#${color.toARGB32().toRadixString(16).substring(2).toUpperCase()}';
                                setState(() {
                                  fields[entry.key]!.text = hex;
                                  draft = draft.copyWith(
                                    colors: {...draft.colors, entry.key: hex},
                                  );
                                });
                              }
                            },
                            child: Container(
                              width: 28,
                              height: 28,
                              decoration: BoxDecoration(
                                color: draft.color(entry.key),
                                border: Border.all(
                                  color: Theme.of(
                                    context,
                                  ).colorScheme.outlineVariant,
                                ),
                                borderRadius: BorderRadius.circular(8),
                              ),
                            ),
                          ),
                        ),
                      ),
                      validator: (value) =>
                          RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(value ?? '')
                          ? null
                          : 'Formato: #2563EB',
                      onChanged: (value) {
                        if (RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(value)) {
                          setState(
                            () => draft = draft.copyWith(
                              colors: {...draft.colors, entry.key: value},
                            ),
                          );
                        }
                      },
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final options = {
      'global': 'Toda la aplicación · global',
      for (final customer in state.customers)
        'user:${customer.userId}': 'Cuenta · ${customer.name}',
      for (final device in devices)
        'device:${device['id']}':
            'Dispositivo · ${state.customers.where((row) => row.userId == device['user_id']).firstOrNull?.name ?? device['user_id']} · ${(device['device_key'] as String).substring(0, 8)}',
    };
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PageHeading(
            title: 'Tu marca. Tu experiencia.',
            subtitle:
                'Diseña una vez. Publica en Web y Android, sin recompilar.',
            action: FilledButton.icon(
              onPressed: saving ? null : saveBranding,
              icon: const Icon(Icons.publish_outlined, size: 20),
              label: Text(saving ? 'Publicando…' : 'Publicar diseño'),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'Revisión del borrador: ${draft.revision}',
                style: TextStyle(
                  fontSize: 11,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              TextButton(
                onPressed: saving ? null : resetDraft,
                child: const Text('Recargar borrador'),
              ),
            ],
          ),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (context, constraints) {
              if (constraints.maxWidth < 930) {
                return Column(
                  children: [
                    brandForm(),
                    const SizedBox(height: 22),
                    _PhonePreview(config: draft),
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: brandForm()),
                  const SizedBox(width: 28),
                  SizedBox(width: 330, child: _PhonePreview(config: draft)),
                ],
              );
            },
          ),
          const SizedBox(height: 24),
          SectionCard(
            title: 'Módulos y permisos dinámicos',
            trailing: const Icon(Icons.tune_rounded, size: 22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Un módulo debe estar habilitado globalmente, en la cuenta y en el dispositivo. Ocultarlo también bloquea sus endpoints para el cliente.',
                  style: TextStyle(fontSize: 13, height: 1.6),
                ),
                const SizedBox(height: 20),
                DropdownButtonFormField<String>(
                  key: ValueKey('${options.length}:$scope'),
                  initialValue: options.containsKey(scope) ? scope : 'global',
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Aplicar permisos a',
                  ),
                  items: [
                    for (final entry in options.entries)
                      DropdownMenuItem(
                        value: entry.key,
                        child: Text(
                          entry.value,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: saving || loadingFlags
                      ? null
                      : (value) => changeScope(value!),
                ),
                if (loadingFlags)
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: LinearProgressIndicator(),
                  ),
                if (flagError != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(
                      flagError!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
                const SizedBox(height: 14),
                for (final entry in featureLabels.entries)
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                      entry.value,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    subtitle: scope != 'global' && !draft.enabled(entry.key)
                        ? const Text(
                            'Actualmente bloqueado a nivel global',
                            style: TextStyle(fontSize: 11),
                          )
                        : null,
                    value: scope == 'global'
                        ? draft.enabled(entry.key)
                        : overrides[entry.key] ?? true,
                    onChanged: loadingFlags || saving || flagError != null
                        ? null
                        : (value) => setState(() {
                            if (scope == 'global') {
                              draft = draft.copyWith(
                                features: {...draft.features, entry.key: value},
                              );
                            } else {
                              overrides = {...overrides, entry.key: value};
                            }
                          }),
                  ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: saving || loadingFlags || flagError != null
                      ? null
                      : saveFlags,
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: Text(
                    scope == 'global'
                        ? 'Publicar diseño y módulos globales'
                        : 'Guardar permisos del destino',
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PhonePreview extends StatelessWidget {
  const _PhonePreview({required this.config});
  final AppConfigModel config;
  @override
  Widget build(BuildContext context) => SectionCard(
    title: 'Vista previa · Android',
    child: Center(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 285),
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: const Color(0xFF14213D),
          borderRadius: BorderRadius.circular(34),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(27),
          child: Theme(
            data: ThemeController.buildTheme(config),
            child: Builder(
              builder: (context) => Container(
                color: config.color('background'),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(20),
                      color: config.color('primary'),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Center(
                            child: Icon(
                              Icons.horizontal_rule_rounded,
                              color: Colors.white54,
                              size: 28,
                            ),
                          ),
                          const SizedBox(height: 16),
                          BrandLogo(config: config, size: 37),
                          const SizedBox(height: 16),
                          Text(
                            config.name,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onPrimary,
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 12),
                          Text(
                            config.welcome,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onPrimary,
                              fontSize: 22,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            config.tagline,
                            style: const TextStyle(fontSize: 12, height: 1.5),
                          ),
                          const SizedBox(height: 18),
                          for (final entry in featureLabels.entries.where(
                            (entry) => config.enabled(entry.key),
                          ))
                            Padding(
                              padding: const EdgeInsets.only(bottom: 9),
                              child: Card(
                                child: Padding(
                                  padding: const EdgeInsets.all(13),
                                  child: Row(
                                    children: [
                                      Icon(
                                        Icons.check_circle_outline,
                                        size: 18,
                                        color: config.color('secondary'),
                                      ),
                                      const SizedBox(width: 10),
                                      Expanded(
                                        child: Text(
                                          entry.value,
                                          style: const TextStyle(fontSize: 11),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.all(18),
                      child: Center(
                        child: Text(
                          'Vista ilustrativa · Sin datos de clientes',
                          style: TextStyle(fontSize: 9),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

Future<Color?> selectColor(BuildContext context, Color initial) {
  var value = HSVColor.fromColor(initial);
  return showDialog<Color>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setState) => AlertDialog(
        title: const Text('Seleccionar color'),
        content: SizedBox(
          width: 350,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                height: 64,
                decoration: BoxDecoration(
                  color: value.toColor(),
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              const SizedBox(height: 20),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  for (final color in [
                    0xFF2563EB,
                    0xFF0D9488,
                    0xFF7C3AED,
                    0xFFDB2777,
                    0xFFDC2626,
                    0xFFF59E0B,
                    0xFF0E182A,
                    0xFFF4F6FA,
                    0xFFFFFFFF,
                  ])
                    InkWell(
                      onTap: () => setState(
                        () => value = HSVColor.fromColor(Color(color)),
                      ),
                      child: Container(
                        width: 27,
                        height: 27,
                        decoration: BoxDecoration(
                          color: Color(color),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.black12),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 18),
              const Align(alignment: Alignment.centerLeft, child: Text('Tono')),
              Slider(
                value: value.hue,
                min: 0,
                max: 360,
                onChanged: (hue) => setState(() => value = value.withHue(hue)),
              ),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text('Saturación'),
              ),
              Slider(
                value: value.saturation,
                onChanged: (saturation) =>
                    setState(() => value = value.withSaturation(saturation)),
              ),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text('Luminosidad'),
              ),
              Slider(
                value: value.value,
                onChanged: (brightness) =>
                    setState(() => value = value.withValue(brightness)),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, value.toColor()),
            child: const Text('Aplicar'),
          ),
        ],
      ),
    ),
  );
}

/// Selector de tema del sistema visual.
///
/// Cada tarjeta muestra la paleta tal cual la publicará el taller y los colores
/// semánticos de estado. Elegir un tema solo cambia el borrador: no se publica
/// nada hasta pulsar «Publicar diseño».
class _ThemeSelector extends StatelessWidget {
  const _ThemeSelector({
    required this.catalog,
    required this.selected,
    required this.onSelect,
  });

  final List<Json> catalog;
  final String selected;
  final ValueChanged<String> onSelect;

  static const _structure = ['navigation', 'background', 'surface', 'text'];
  static const _states = [
    ('success', 'Normal'),
    ('warning', 'Seguimiento'),
    ('danger', 'Incidencia'),
    ('unknown', 'Sin datos'),
  ];

  @override
  Widget build(BuildContext context) => SectionCard(
    title: 'Tema visual',
    subtitle:
        'El tema define la estructura y los estados. Tus cuatro colores de '
        'marca siguen mandando sobre los del tema.',
    child: themeCatalog(),
  );

  Widget themeCatalog() {
    if (catalog.isEmpty) {
      return const Text('Cargando catálogo de temas…');
    }
    return Builder(
      builder: (context) => Wrap(
        spacing: 14,
        runSpacing: 14,
        children: [for (final theme in catalog) _themeCard(context, theme)],
      ),
    );
  }

  Widget _themeCard(BuildContext context, Json theme) {
    final key = theme['key'] as String;
    final active = key == selected;
    return Semantics(
      selected: active,
      button: true,
      label: '${theme['label']}. ${theme['description']}',
      child: InkWell(
        onTap: () => onSelect(key),
        borderRadius: BorderRadius.circular(14),
        child: Container(
          width: 236,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: active
                  ? Theme.of(context).colorScheme.primary
                  : Theme.of(context).colorScheme.outlineVariant,
              width: active ? 2 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  for (final field in _structure)
                    Expanded(
                      child: Container(
                        height: 30,
                        margin: const EdgeInsets.only(right: 3),
                        decoration: BoxDecoration(
                          color: field == 'navigation'
                              ? _hex(theme['navigation'])
                              : field == 'background'
                              ? _hex(theme['background'])
                              : field == 'surface'
                              ? _hex(theme['surface'])
                              : _hex(theme['accent']),
                          borderRadius: BorderRadius.circular(5),
                        ),
                      ),
                    ),
                  const SizedBox(width: 6),
                  Icon(
                    active ? Icons.check_circle : Icons.circle_outlined,
                    size: 18,
                    color: active
                        ? Theme.of(context).colorScheme.primary
                        : Theme.of(context).colorScheme.outlineVariant,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                theme['label'] as String,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 2),
              Text(
                theme['description'] as String? ?? '',
                style: const TextStyle(fontSize: 11, height: 1.25),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  for (final state in _states) ...[
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: _hex(theme[state.$1]),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 3),
                    Text(state.$2, style: const TextStyle(fontSize: 9)),
                    const SizedBox(width: 6),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _hex(Object? value) {
    if (value is String && RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(value)) {
      return Color(int.parse('FF${value.substring(1)}', radix: 16));
    }
    return const Color(0xFF9AA4AE);
  }
}
