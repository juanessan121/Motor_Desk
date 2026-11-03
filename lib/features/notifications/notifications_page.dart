import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/network/api_client.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/widgets.dart';
import '../registry/registry_forms.dart' show validateEmail;

class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key});
  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  late Future<dynamic> deliverySettings;

  @override
  void initState() {
    super.initState();
    deliverySettings = context.read<WorkshopController>().isAdmin
        ? context.read<WorkshopController>().api.request(
            'GET',
            '/notification-settings',
          )
        : Future.value(<String, dynamic>{});
  }

  Future<void> _viewMessage(Json row) => showDialog<void>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text(row['subject'] as String? ?? 'Mensaje'),
      content: SingleChildScrollView(
        child: SelectableText(
          row['body'] as String? ?? 'Contenido no disponible',
        ),
      ),
      actions: [
        TextButton(
          onPressed: row['body'] == null
              ? null
              : () async {
                  await Clipboard.setData(
                    ClipboardData(text: row['body'] as String),
                  );
                  if (dialogContext.mounted) {
                    showMessage(
                      dialogContext,
                      'Mensaje copiado. Su estado de envío no cambia.',
                    );
                  }
                },
          child: const Text('Copiar mensaje'),
        ),
        TextButton(
          onPressed: () => Navigator.pop(dialogContext),
          child: const Text('Cerrar'),
        ),
      ],
    ),
  );

  void _reloadSettings() => setState(() {
    deliverySettings = context.read<WorkshopController>().api.request(
      'GET',
      '/notification-settings',
    );
  });

  Future<void> _editRecipient(Json row) async {
    final customerId = row['customer_id'];
    if (customerId == null) return;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => _RecipientPreferencesDialog(
        customerId: customerId as int,
        initialData: row,
        onSaved: () {
          context.read<WorkshopController>().refresh();
          _reloadSettings();
        },
      ),
    );
  }

  Future<void> _openRecipientsDirectory() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => _RecipientsDirectoryDialog(
        onEditRecipient: (customer) => _editRecipient(customer),
      ),
    );
  }

  Future<void> _cleanupNotifications() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Limpiar bandeja de notificaciones'),
        content: const Text(
          'Se descartarán las notificaciones ya enviadas o fallidas de la bandeja activa.\n\n'
          'Esta acción NO elimina la información ni los datos de contacto de ningún cliente.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancelar'),
          ),
          FilledButton.icon(
            icon: const Icon(Icons.cleaning_services_outlined),
            label: const Text('Limpiar bandeja'),
            onPressed: () => Navigator.of(ctx).pop(true),
          ),
        ],
      ),
    );
    if (confirm != true || !mounted) return;

    final state = context.read<WorkshopController>();
    await runAction(context, () async {
      final res =
          await state.api.request('POST', '/notifications/cleanup') as Json;
      await state.refresh();
      if (mounted) {
        showMessage(context, res['message'] as String? ?? 'Bandeja limpiada');
        _reloadSettings();
      }
    }, success: 'Notificaciones antiguas limpiadas.');
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const PageHeading(
            title: 'Centro de notificaciones',
            subtitle:
                'Gestión independiente de contactos, preferencias de canal e historial de entregas.',
          ),
          if (state.isAdmin) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  icon: const Icon(Icons.contacts_outlined, size: 18),
                  label: const Text('Editar correo o Telegram'),
                  onPressed: _openRecipientsDirectory,
                ),
                OutlinedButton.icon(
                  icon: const Icon(Icons.cleaning_services_outlined, size: 18),
                  label: const Text('Limpiar bandeja'),
                  onPressed: _cleanupNotifications,
                ),
              ],
            ),
          ],
          const SizedBox(height: 24),
          if (state.isAdmin) ...[
            FutureBuilder(
              future: deliverySettings,
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return SectionCard(
                    title: 'No se pudieron verificar los canales',
                    child: TextButton(
                      onPressed: _reloadSettings,
                      child: const Text('Reintentar consulta'),
                    ),
                  );
                }
                if (!snapshot.hasData) return const LinearProgressIndicator();
                final config = snapshot.data as Json? ?? {};
                return SectionCard(
                  title: 'Canales del servidor y proveedores',
                  subtitle:
                      'Sin proveedor, destinatario o conexión, el envío se pausa de forma segura. Puede editar contactos y preferencias sin alterar el historial.',
                  child: Wrap(
                    spacing: 24,
                    runSpacing: 12,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      _ChannelStatus(
                        'Email / SMTP',
                        config['email_configured'] == true,
                      ),
                      _ChannelStatus(
                        'Telegram Bot',
                        config['telegram_configured'] == true,
                      ),
                      _ChannelStatus(
                        'WhatsApp Business API',
                        config['whatsapp_configured'] == true,
                      ),
                      Text(
                        'En pausa: ${config['paused_count'] ?? state.notifications.where((row) => row['effective_status'] == 'paused').length}',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      TextButton.icon(
                        icon: const Icon(Icons.play_circle_outline),
                        label: const Text('Reanudar canales configurados'),
                        onPressed:
                            config['email_configured'] != true &&
                                config['telegram_configured'] != true
                            ? null
                            : () => runAction(context, () async {
                                final result =
                                    await state.api.request(
                                          'POST',
                                          '/notification-settings/resume',
                                        )
                                        as Json;
                                await state.refresh();
                                if (context.mounted) {
                                  showMessage(
                                    context,
                                    '${result['resumed']} envíos reanudados. Los que aún necesitan configuración continúan en pausa.',
                                  );
                                }
                                if (mounted) _reloadSettings();
                              }),
                      ),
                      IconButton(
                        tooltip: 'Actualizar estado de canales',
                        onPressed: _reloadSettings,
                        icon: const Icon(Icons.refresh),
                      ),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(height: 22),
            RecordTable(
              records: state.notifications,
              emptyTitle: 'No hay envíos registrados en la bandeja activa',
              columns: [
                RecordColumn(
                  'Evento',
                  (row) => switch (row['kind']) {
                    'credentials' => 'Credenciales de acceso',
                    'vehicle_ready' => 'Vehículo listo',
                    'quote_requested' => 'Aprobación de repuesto',
                    'order_created' || 'reception' => 'Recepción de vehículo',
                    'payment_info' => 'Liquidación y pago',
                    _ => '${row['kind']}',
                  },
                ),
                RecordColumn(
                  'Destinatario',
                  (row) =>
                      row['recipient_name'] as String? ?? '#${row['user_id']}',
                ),
                RecordColumn('Medio de entrega', (row) {
                  final ch = row['channel'] ?? row['notification_channel'];
                  if (ch == 'telegram') {
                    return row['telegram_chat_id'] != null
                        ? 'Telegram: ${row['telegram_chat_id']}'
                        : 'Telegram (falta chat_id)';
                  }
                  if (ch == 'whatsapp') {
                    return row['whatsapp'] != null &&
                            (row['whatsapp'] as String).isNotEmpty
                        ? 'WhatsApp: ${row['whatsapp']}'
                        : 'WhatsApp (sin número)';
                  }
                  return row['email'] as String? ?? 'Sin correo';
                }),
                RecordColumn('Canal', (row) => '${row['channel']}'),
                RecordColumn(
                  'Estado',
                  (row) => '${row['effective_status'] ?? row['status']}',
                  cell: (row) => StatusChip(
                    (row['effective_status'] ?? row['status']) as String,
                  ),
                ),
                RecordColumn('Intentos', (row) => '${row['attempts']}'),
                RecordColumn('Fecha', (row) => shortDate(row['created_at'])),
                RecordColumn(
                  'Detalle / Error',
                  (row) => row['last_error'] as String? ?? '—',
                ),
              ],
              actions: (row) => Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    tooltip: 'Revisar mensaje',
                    onPressed: () => _viewMessage(row),
                    icon: const Icon(Icons.message_outlined),
                  ),
                  IconButton(
                    tooltip: 'Editar contacto y canal',
                    onPressed: row['customer_id'] == null
                        ? null
                        : () => _editRecipient(row),
                    icon: const Icon(Icons.edit_outlined),
                  ),
                  IconButton(
                    tooltip: 'Descartar de la bandeja',
                    onPressed: () => runAction(
                      context,
                      () => state.mutate(
                        'POST',
                        '/notifications/${row['id']}/archive',
                      ),
                      success: 'Notificación descartada de la bandeja.',
                    ),
                    icon: const Icon(Icons.archive_outlined),
                  ),
                  IconButton(
                    tooltip: 'Reintentar envío',
                    onPressed: row['can_retry'] != true
                        ? null
                        : () => runAction(
                            context,
                            () => state.mutate(
                              'POST',
                              '/notifications/${row['id']}/retry',
                            ),
                            success: 'Envío reprogramado.',
                          ),
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'La bandeja separa tres conceptos: datos de contacto del cliente, preferencias de canal y el historial de envíos. Descartar una notificación no altera el registro del cliente ni de sus vehículos.',
              style: TextStyle(
                fontSize: 11,
                color: context.atelier.secondaryText,
              ),
            ),
          ] else if (state.notifications.isEmpty)
            const Card(
              child: EmptyState(
                title: 'Todo al día',
                message: 'Aquí aparecerán tus mensajes.',
              ),
            )
          else
            for (final notification in state.notifications)
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Card(
                  child: ListTile(
                    contentPadding: const EdgeInsets.all(18),
                    leading: const Icon(Icons.notifications_outlined),
                    title: Text(
                      notification['title'] as String,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Text(
                        '${notification['body']}\n${shortDate(notification['created_at'])}',
                        style: const TextStyle(height: 1.7),
                      ),
                    ),
                  ),
                ),
              ),
        ],
      ),
    );
  }
}

class _ChannelStatus extends StatelessWidget {
  const _ChannelStatus(this.label, this.configured);
  final String label;
  final bool configured;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(
        configured ? Icons.check_circle_outline : Icons.warning_amber_rounded,
        color: configured ? context.atelier.success : context.atelier.warning,
        size: 20,
      ),
      const SizedBox(width: 8),
      Flexible(
        child: Text(
          '$label · ${configured ? 'Configurado' : 'No configurado'}',
          style: const TextStyle(fontSize: 13),
        ),
      ),
    ],
  );
}

class _RecipientPreferencesDialog extends StatefulWidget {
  const _RecipientPreferencesDialog({
    required this.customerId,
    required this.initialData,
    required this.onSaved,
  });

  final int customerId;
  final Json initialData;
  final VoidCallback onSaved;

  @override
  State<_RecipientPreferencesDialog> createState() =>
      _RecipientPreferencesDialogState();
}

class _RecipientPreferencesDialogState
    extends State<_RecipientPreferencesDialog> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _emailCtrl;
  late TextEditingController _whatsappCtrl;
  late TextEditingController _telegramCtrl;

  late String _channel;
  late bool _masterEnabled;
  late bool _emailEnabled;
  late bool _telegramEnabled;
  late bool _whatsappEnabled;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final d = widget.initialData;
    _emailCtrl = TextEditingController(text: d['email'] as String? ?? '');
    _whatsappCtrl = TextEditingController(text: d['whatsapp'] as String? ?? '');
    _telegramCtrl = TextEditingController(
      text: d['telegram_chat_id'] as String? ?? '',
    );

    _channel =
        (d['notification_channel'] ?? d['channel']) as String? ?? 'email';
    if (!['email', 'telegram', 'whatsapp'].contains(_channel)) {
      _channel = 'email';
    }
    _masterEnabled = d['notifications_enabled'] as bool? ?? true;
    _emailEnabled = d['email_notifications_enabled'] as bool? ?? true;
    _telegramEnabled = d['telegram_notifications_enabled'] as bool? ?? true;
    _whatsappEnabled = d['whatsapp_notifications_enabled'] as bool? ?? true;
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _whatsappCtrl.dispose();
    _telegramCtrl.dispose();
    super.dispose();
  }

  Future<void> _removeChannel(String channelName) async {
    setState(() {
      if (channelName == 'telegram') {
        _telegramCtrl.clear();
        _telegramEnabled = false;
      } else if (channelName == 'whatsapp') {
        _whatsappCtrl.clear();
        _whatsappEnabled = false;
      }
      if (_channel == channelName) _channel = 'email';
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final state = context.read<WorkshopController>();
      final payload = {
        'email': _emailCtrl.text.trim().toLowerCase(),
        'whatsapp': _whatsappCtrl.text.trim(),
        'telegram_chat_id': _telegramCtrl.text.trim().isEmpty
            ? null
            : _telegramCtrl.text.trim(),
        'notification_channel': _channel,
        'notifications_enabled': _masterEnabled,
        'email_notifications_enabled': _emailEnabled,
        'telegram_notifications_enabled': _telegramEnabled,
        'whatsapp_notifications_enabled': _whatsappEnabled,
      };

      await state.api.request(
        'PATCH',
        '/notifications/recipients/${widget.customerId}',
        body: payload,
      );

      if (mounted) {
        showMessage(context, 'Medios y preferencias guardados exitosamente');
        widget.onSaved();
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) showMessage(context, e.toString(), error: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final clientName =
        widget.initialData['recipient_name'] ??
        widget.initialData['name'] ??
        'Cliente #${widget.customerId}';

    return AlertDialog(
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'Contacto para notificaciones',
            style: TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            clientName,
            style: TextStyle(
              fontWeight: FontWeight.normal,
              fontSize: 12,
              color: context.atelier.secondaryText,
            ),
          ),
        ],
      ),
      content: SizedBox(
        width: 520,
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Sección 1: Medios de contacto
                const Text(
                  'Edita los datos y pulsa Guardar',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                ),
                const SizedBox(height: 10),
                TextFormField(
                  controller: _emailCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Correo del cliente',
                    hintText: 'ejemplo@correo.com',
                    prefixIcon: Icon(Icons.email_outlined),
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                  keyboardType: TextInputType.emailAddress,
                  validator: (v) => validateEmail(v ?? ''),
                ),
                const SizedBox(height: 10),
                TextFormField(
                  controller: _telegramCtrl,
                  decoration: InputDecoration(
                    labelText: 'Telegram Chat ID',
                    helperText:
                        'ID numérico del chat, no @usuario. El cliente debe iniciar tu bot.',
                    helperMaxLines: 3,
                    hintText: 'Ej: 123456789',
                    prefixIcon: const Icon(Icons.send_outlined),
                    border: const OutlineInputBorder(),
                    isDense: true,
                    suffixIcon: _telegramCtrl.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 18),
                            tooltip: 'Desvincular Telegram',
                            onPressed: () => _removeChannel('telegram'),
                          )
                        : null,
                  ),
                  validator: (v) {
                    if (v == null || v.trim().isEmpty) {
                      return _channel == 'telegram' && _masterEnabled
                          ? 'Añade el ID del chat para usar Telegram'
                          : null;
                    }
                    return RegExp(r'^-?\d{1,30}$').hasMatch(v.trim())
                        ? null
                        : 'Debe ser un identificador numérico de Telegram';
                  },
                ),
                const Divider(height: 24),

                // Sección 2: Preferencias de notificación
                const Text(
                  'Cómo prefiere recibir los avisos',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  isExpanded: true,
                  key: ValueKey(_channel),
                  initialValue: _channel,
                  decoration: const InputDecoration(
                    labelText: 'Canal de entrega preferido',
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'email',
                      child: Text('Correo electrónico'),
                    ),
                    DropdownMenuItem(
                      value: 'whatsapp',
                      child: Text('WhatsApp'),
                    ),
                    DropdownMenuItem(
                      value: 'telegram',
                      child: Text('Telegram'),
                    ),
                  ],
                  onChanged: (v) => setState(() => _channel = v ?? 'email'),
                ),
                const SizedBox(height: 8),
                SwitchListTile(
                  title: const Text('Permitir notificaciones'),
                  subtitle: const Text(
                    'Permite enviar alertas de órdenes al cliente',
                    style: TextStyle(fontSize: 11),
                  ),
                  value: _masterEnabled,
                  onChanged: (v) => setState(() => _masterEnabled = v),
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                ),
                ExpansionTile(
                  title: const Text('WhatsApp y opciones de envío'),
                  children: [
                    TextFormField(
                      controller: _whatsappCtrl,
                      decoration: InputDecoration(
                        labelText: 'Número de WhatsApp',
                        hintText: '+593991234567',
                        prefixIcon: const Icon(Icons.phone_android_outlined),
                        border: const OutlineInputBorder(),
                        isDense: true,
                        suffixIcon: _whatsappCtrl.text.isNotEmpty
                            ? IconButton(
                                icon: const Icon(Icons.clear, size: 18),
                                tooltip: 'Desvincular WhatsApp',
                                onPressed: () => _removeChannel('whatsapp'),
                              )
                            : null,
                      ),
                      keyboardType: TextInputType.phone,
                    ),
                    const SizedBox(height: 10),
                    SwitchListTile(
                      title: const Text('Alertas por Correo electrónico'),
                      value: _emailEnabled,
                      onChanged: (v) => setState(() => _emailEnabled = v),
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                    ),
                    SwitchListTile(
                      title: const Text('Alertas por WhatsApp'),
                      value: _whatsappEnabled,
                      onChanged: (v) => setState(() => _whatsappEnabled = v),
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                    ),
                    SwitchListTile(
                      title: const Text('Alertas por Telegram'),
                      value: _telegramEnabled,
                      onChanged: (v) => setState(() => _telegramEnabled = v),
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: Text(_saving ? 'Guardando…' : 'Guardar'),
        ),
      ],
    );
  }
}

class _RecipientsDirectoryDialog extends StatefulWidget {
  const _RecipientsDirectoryDialog({required this.onEditRecipient});
  final void Function(Json) onEditRecipient;

  @override
  State<_RecipientsDirectoryDialog> createState() =>
      _RecipientsDirectoryDialogState();
}

class _RecipientsDirectoryDialogState
    extends State<_RecipientsDirectoryDialog> {
  late Future<List<dynamic>> _recipientsFuture;
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _loadRecipients();
  }

  void _loadRecipients() {
    _recipientsFuture = context
        .read<WorkshopController>()
        .api
        .request('GET', '/notifications/recipients')
        .then((res) => res as List<dynamic>);
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800, maxHeight: 650),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Directorio de contactos para notificaciones',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                'Configure canales, números y medios de entrega de cada cliente directamente desde este panel.',
                style: TextStyle(
                  fontSize: 12,
                  color: context.atelier.secondaryText,
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search),
                  hintText: 'Buscar por nombre, correo o teléfono...',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                onChanged: (v) =>
                    setState(() => _filter = v.trim().toLowerCase()),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: FutureBuilder<List<dynamic>>(
                  future: _recipientsFuture,
                  builder: (context, snapshot) {
                    if (snapshot.hasError) {
                      return Center(
                        child: Text(
                          'Error al cargar contactos: ${snapshot.error}',
                        ),
                      );
                    }
                    if (!snapshot.hasData) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    final list = snapshot.data!.map((e) => e as Json).where((
                      c,
                    ) {
                      if (_filter.isEmpty) return true;
                      final name = (c['name'] as String? ?? '').toLowerCase();
                      final email = (c['email'] as String? ?? '').toLowerCase();
                      final phone = (c['phone'] as String? ?? '').toLowerCase();
                      final wa = (c['whatsapp'] as String? ?? '').toLowerCase();
                      return name.contains(_filter) ||
                          email.contains(_filter) ||
                          phone.contains(_filter) ||
                          wa.contains(_filter);
                    }).toList();

                    if (list.isEmpty) {
                      return const Center(
                        child: Text('No se encontraron clientes coincidentes.'),
                      );
                    }

                    return ListView.separated(
                      itemCount: list.length,
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (context, index) {
                        final c = list[index];
                        final hasEmail =
                            (c['email'] as String? ?? '').isNotEmpty;
                        final hasWa =
                            (c['whatsapp'] as String? ?? '').isNotEmpty;
                        final hasTg =
                            (c['telegram_chat_id'] as String? ?? '').isNotEmpty;
                        final pref =
                            c['notification_channel'] as String? ?? 'email';

                        return ListTile(
                          title: Text(
                            c['name'] as String? ?? 'Cliente #${c['id']}',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            'Correo: ${c['email'] ?? '—'} · WhatsApp: ${c['whatsapp'] ?? '—'} · Telegram: ${c['telegram_chat_id'] ?? '—'}\n'
                            'Canal preferido: $pref · Notificaciones: ${c['notifications_enabled'] == true ? 'Activas' : 'Desactivadas'}',
                            style: const TextStyle(fontSize: 12),
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              _MiniChannelChip(
                                label: 'Email',
                                active:
                                    hasEmail &&
                                    c['email_notifications_enabled'] == true,
                              ),
                              const SizedBox(width: 4),
                              _MiniChannelChip(
                                label: 'WhatsApp',
                                active:
                                    hasWa &&
                                    c['whatsapp_notifications_enabled'] == true,
                              ),
                              const SizedBox(width: 4),
                              _MiniChannelChip(
                                label: 'Telegram',
                                active:
                                    hasTg &&
                                    c['telegram_notifications_enabled'] == true,
                              ),
                              const SizedBox(width: 8),
                              IconButton(
                                icon: const Icon(Icons.edit_outlined),
                                tooltip: 'Editar medios y preferencias',
                                onPressed: () {
                                  Navigator.of(context).pop();
                                  widget.onEditRecipient(c);
                                },
                              ),
                            ],
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MiniChannelChip extends StatelessWidget {
  const _MiniChannelChip({required this.label, required this.active});
  final String label;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: active
            ? context.atelier.success.withOpacity(0.12)
            : Colors.grey.withOpacity(0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: active ? context.atelier.success : Colors.grey,
          width: 0.8,
        ),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: active ? context.atelier.success : Colors.grey,
        ),
      ),
    );
  }
}
