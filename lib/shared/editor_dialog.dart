import 'package:flutter/material.dart';

class EditorField {
  const EditorField(
    this.key,
    this.label, {
    this.initial = '',
    this.required = true,
    this.lines = 1,
    this.options,
    this.validate,
    this.keyboard,
    this.obscure = false,
  });
  final String key;
  final String label;
  final String initial;
  final bool required;
  final int lines;
  final Map<String, String>? options;
  final String? Function(String)? validate;
  final TextInputType? keyboard;
  final bool obscure;
}

Future<void> showEditor(
  BuildContext context, {
  required String title,
  required String description,
  required List<EditorField> fields,
  required Future<void> Function(Map<String, String>) onSubmit,
  String submitLabel = 'Guardar',
  Widget? extra,
  Map<String, TextEditingController>? sharedControllers,
}) async {
  final navigator = Navigator.of(context, rootNavigator: true);
  final route = DialogRoute<void>(
    context: context,
    barrierDismissible: false,
    themes: InheritedTheme.capture(from: context, to: navigator.context),
    builder: (_) => EditorDialog(
      title: title,
      description: description,
      fields: fields,
      onSubmit: onSubmit,
      submitLabel: submitLabel,
      extra: extra,
      sharedControllers: sharedControllers,
    ),
  );
  await navigator.push(route);
  // El Future de pop termina antes que la animación de salida. El llamador
  // solo puede disponer sus controladores compartidos al desmontar la ruta.
  await route.completed;
}

class EditorDialog extends StatefulWidget {
  const EditorDialog({
    super.key,
    required this.title,
    required this.description,
    required this.fields,
    required this.onSubmit,
    required this.submitLabel,
    this.extra,
    this.sharedControllers,
  });
  final String title;
  final String description;
  final List<EditorField> fields;
  final Future<void> Function(Map<String, String>) onSubmit;
  final String submitLabel;

  /// Contenido a ancho completo debajo de los campos, por ejemplo un selector
  /// de catálogo que rellene alguno de ellos.
  final Widget? extra;

  /// Controladores reutilizados desde fuera para poder escribir en ellos.
  final Map<String, TextEditingController>? sharedControllers;
  @override
  State<EditorDialog> createState() => _EditorDialogState();
}

class _EditorDialogState extends State<EditorDialog> {
  final form = GlobalKey<FormState>();
  late final Map<String, TextEditingController> controllers;
  late final Map<String, String> dropdowns;
  bool saving = false;
  String? error;
  @override
  void initState() {
    super.initState();
    controllers = {
      for (final field in widget.fields.where((field) => field.options == null))
        field.key:
            widget.sharedControllers?[field.key] ??
            TextEditingController(text: field.initial),
    };
    dropdowns = {
      for (final field in widget.fields.where((field) => field.options != null))
        field.key: field.options!.containsKey(field.initial)
            ? field.initial
            : field.options!.keys.firstOrNull ?? '',
    };
  }

  @override
  void dispose() {
    for (final controller
        in controllers.entries
            .where(
              (entry) => widget.sharedControllers?[entry.key] != entry.value,
            )
            .map((entry) => entry.value)) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> submit() async {
    if (saving) return;
    if (!form.currentState!.validate()) return;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.onSubmit({
        ...dropdowns,
        for (final entry in controllers.entries)
          entry.key: entry.value.text.trim(),
      });
      if (mounted) Navigator.pop(context);
    } catch (failure) {
      if (mounted) {
        setState(() {
          error = failure.toString();
          saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !saving,
    child: Dialog(
      insetPadding: const EdgeInsets.all(18),
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: 680,
          maxHeight: MediaQuery.sizeOf(context).height * .9,
        ),
        child: Padding(
          padding: const EdgeInsets.all(26),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.title,
                style: const TextStyle(
                  fontSize: 23,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                widget.description,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 24),
              Flexible(
                child: SingleChildScrollView(
                  child: Form(
                    key: form,
                    child: LayoutBuilder(
                      builder: (context, constraints) => Wrap(
                        spacing: 16,
                        runSpacing: 18,
                        children: [
                          for (final field in widget.fields)
                            SizedBox(
                              width:
                                  constraints.maxWidth < 480 || field.lines > 1
                                  ? constraints.maxWidth
                                  : (constraints.maxWidth - 16) / 2,
                              child: field.options == null
                                  ? TextFormField(
                                      controller: controllers[field.key],
                                      decoration: InputDecoration(
                                        labelText: field.label,
                                      ),
                                      maxLines: field.lines,
                                      enabled: !saving,
                                      obscureText: field.obscure,
                                      keyboardType: field.keyboard,
                                      validator: (value) {
                                        if (field.required &&
                                            (value?.trim().isEmpty ?? true)) {
                                          return 'Este campo es obligatorio';
                                        }
                                        return field.validate?.call(
                                          value?.trim() ?? '',
                                        );
                                      },
                                    )
                                  : DropdownButtonFormField<String>(
                                      initialValue:
                                          dropdowns[field.key]!.isEmpty
                                          ? null
                                          : dropdowns[field.key],
                                      isExpanded: true,
                                      decoration: InputDecoration(
                                        labelText: field.label,
                                      ),
                                      items: [
                                        for (final entry
                                            in field.options!.entries)
                                          DropdownMenuItem(
                                            value: entry.key,
                                            child: Text(
                                              entry.value,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                      ],
                                      onChanged: saving
                                          ? null
                                          : (value) => setState(
                                              () => dropdowns[field.key] =
                                                  value ?? '',
                                            ),
                                      validator: (value) =>
                                          field.required &&
                                              (value?.isEmpty ?? true)
                                          ? 'Seleccione una opción'
                                          : null,
                                    ),
                            ),
                          if (widget.extra != null)
                            SizedBox(
                              width: constraints.maxWidth,
                              child: widget.extra!,
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Text(
                    error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              const SizedBox(height: 24),
              Wrap(
                alignment: WrapAlignment.end,
                spacing: 12,
                runSpacing: 8,
                children: [
                  TextButton(
                    onPressed: saving ? null : () => Navigator.pop(context),
                    child: const Text('Cancelar'),
                  ),
                  FilledButton(
                    onPressed: saving ? null : submit,
                    child: saving
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(widget.submitLabel),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
