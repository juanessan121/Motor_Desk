import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config_model.dart';
import '../../core/config/atelier_tokens.dart';
import '../../core/config/theme_controller.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, this.changePassword = false});
  final bool changePassword;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final form = GlobalKey<FormState>();
  final username = TextEditingController();
  final password = TextEditingController();
  final newPassword = TextEditingController();
  final confirmation = TextEditingController();
  final usernameFocus = FocusNode(debugLabel: 'auth.username');
  final passwordFocus = FocusNode(debugLabel: 'auth.current-password');
  final newPasswordFocus = FocusNode(debugLabel: 'auth.new-password');
  final confirmationFocus = FocusNode(debugLabel: 'auth.confirm-password');
  bool busy = false;
  bool visible = false;
  bool newVisible = false;
  bool confirmationVisible = false;
  bool submitted = false;
  String? error;

  @override
  void dispose() {
    username.dispose();
    password.dispose();
    newPassword.dispose();
    confirmation.dispose();
    usernameFocus.dispose();
    passwordFocus.dispose();
    newPasswordFocus.dispose();
    confirmationFocus.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy) return;
    setState(() => submitted = true);
    if (!form.currentState!.validate()) return;
    final current = password.text;
    final next = newPassword.text;
    FocusManager.instance.primaryFocus?.unfocus();
    TextInput.finishAutofillContext(shouldSave: false);
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final state = context.read<WorkshopController>();
      if (widget.changePassword) {
        await state.changePassword(current, next);
      } else {
        await state.login(username.text.trim(), current);
      }
    } catch (failure) {
      if (mounted) setState(() => error = failure.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void _quickLogin(String user, String pass) {
    username.text = user;
    password.text = pass;
    final state = context.read<WorkshopController>();
    if (!state.isAutonomous) {
      state.setAutonomousMode(true);
    }
    submit();
  }

  Widget visibilityButton({
    required bool showing,
    required String label,
    required FocusNode focus,
    required VoidCallback toggle,
  }) => IconButton(
    tooltip: '${showing ? 'Ocultar' : 'Mostrar'} $label',
    onPressed: busy
        ? null
        : () {
            setState(toggle);
            focus.requestFocus();
          },
    icon: Icon(
      showing ? Icons.visibility_off_outlined : Icons.visibility_outlined,
    ),
  );

  /// Panel de izquierda: qué es esto y qué hace.
  ///
  /// No lleva cifras. El concepto las muestra («2 clientes activos»), pero en
  /// el momento del inicio de sesión no hay sesión: cualquier número ahí sería
  /// inventado. Se cuentan las tres cosas que el taller sí puede esperar, que
  /// es información verdadera y no un adorno.
  Widget heroPanel(AppConfigModel config) {
    final palette = context.atelier;
    return Container(
      key: const ValueKey('auth.hero-panel'),
      padding: const EdgeInsets.symmetric(horizontal: 56, vertical: 44),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [palette.navigation, palette.diagnostic],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              BrandLogo(config: config, size: 44),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      config.name,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      'WORKSHOP MANAGER',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: .45),
                        fontSize: 9,
                        letterSpacing: 1.8,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: .08),
              borderRadius: BorderRadius.circular(30),
            ),
            child: Text(
              'GESTIÓN INTELIGENTE DEL TALLER',
              style: TextStyle(
                color: palette.accent,
                fontSize: 11,
                letterSpacing: 1.6,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 26),
          Text(
            config.welcome,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 44,
              height: 1.15,
              letterSpacing: -1.5,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            config.tagline.isEmpty
                ? 'Cada vehículo. Cada detalle.\nTodo conectado en un solo lugar.'
                : config.tagline,
            style: TextStyle(
              color: Colors.white.withValues(alpha: .68),
              fontSize: 18,
              height: 1.7,
            ),
          ),
          const SizedBox(height: 40),
          const _HeroPoint(
            icon: Icons.directions_car_filled_outlined,
            title: 'Gestión completa',
            detail: 'Clientes, vehículos, mantenimientos y órdenes de trabajo.',
          ),
          const SizedBox(height: 18),
          const _HeroPoint(
            icon: Icons.insights_outlined,
            title: 'Seguimiento en tiempo real',
            detail: 'El estado de cada servicio, sin preguntar a nadie.',
          ),
          const SizedBox(height: 18),
          const _HeroPoint(
            icon: Icons.verified_user_outlined,
            title: 'Historial siempre disponible',
            detail: 'Todo el historial del vehículo y sus mantenimientos.',
          ),
          const Spacer(),
          // Sin pie de página: en pantallas estrechas no se ve este panel y el
          // aviso vive en el formulario.
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = context.watch<ThemeController>();
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => Row(
            children: [
              if (constraints.maxWidth >= 1000 && constraints.maxHeight >= 720)
                Expanded(child: heroPanel(theme.config)),
              Expanded(
                key: const ValueKey('auth.form-panel'),
                child: Center(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(30),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 400),
                      child: AutofillGroup(
                        key: ValueKey(
                          widget.changePassword
                              ? 'autofill.change-password'
                              : 'autofill.login',
                        ),
                        onDisposeAction: AutofillContextAction.cancel,
                        child: Form(
                          key: form,
                          autovalidateMode: submitted
                              ? AutovalidateMode.onUserInteraction
                              : AutovalidateMode.disabled,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              BrandLogo(config: theme.config, size: 52),
                              const SizedBox(height: 12),
                              Text(
                                theme.config.name,
                                style: const TextStyle(
                                  fontSize: 21,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              const Text(
                                'WORKSHOP MANAGER',
                                style: TextStyle(
                                  fontSize: 9,
                                  letterSpacing: 1.8,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 30),
                              Text(
                                widget.changePassword
                                    ? 'Protege tu cuenta'
                                    : '¡Bienvenido de nuevo!',
                                style: const TextStyle(
                                  fontSize: 29,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -.8,
                                ),
                              ),
                              const SizedBox(height: 10),
                              Text(
                                widget.changePassword
                                    ? 'Escribe la contraseña temporal con la que ingresaste y crea una nueva de al menos 12 caracteres.'
                                    : 'Ingresa para acceder a tu espacio en ${theme.config.name}.',
                                style: TextStyle(
                                  color: Theme.of(
                                    context,
                                  ).colorScheme.onSurfaceVariant,
                                  height: 1.6,
                                ),
                              ),
                              const SizedBox(height: 30),
                              if (!widget.changePassword) ...[
                                TextFormField(
                                  key: const ValueKey('auth.username'),
                                  controller: username,
                                  focusNode: usernameFocus,
                                  readOnly: busy,
                                  decoration: const InputDecoration(
                                    labelText: 'Usuario o correo',
                                    prefixIcon: Icon(Icons.person_outline),
                                  ),
                                  autofillHints: const [AutofillHints.username],
                                  textInputAction: TextInputAction.next,
                                  onFieldSubmitted: (_) =>
                                      passwordFocus.requestFocus(),
                                  validator: (value) =>
                                      value?.trim().isEmpty ?? true
                                      ? 'Ingresa tu usuario'
                                      : null,
                                ),
                                const SizedBox(height: 18),
                              ],
                              TextFormField(
                                key: ValueKey(
                                  widget.changePassword
                                      ? 'auth.current-password'
                                      : 'auth.password',
                                ),
                                controller: password,
                                focusNode: passwordFocus,
                                readOnly: busy,
                                obscureText: !visible,
                                keyboardType: TextInputType.visiblePassword,
                                textInputAction: widget.changePassword
                                    ? TextInputAction.next
                                    : TextInputAction.done,
                                autocorrect: false,
                                enableSuggestions: false,
                                smartDashesType: SmartDashesType.disabled,
                                smartQuotesType: SmartQuotesType.disabled,
                                autofillHints: const [AutofillHints.password],
                                decoration: InputDecoration(
                                  labelText: widget.changePassword
                                      ? 'Contraseña temporal / actual'
                                      : 'Contraseña',
                                  prefixIcon: const Icon(Icons.lock_outline),
                                  helperText: widget.changePassword
                                      ? 'Es la contraseña que usaste para entrar, no la nueva.'
                                      : null,
                                  helperMaxLines: 2,
                                  suffixIcon: visibilityButton(
                                    showing: visible,
                                    label: 'contraseña actual',
                                    focus: passwordFocus,
                                    toggle: () => visible = !visible,
                                  ),
                                ),
                                validator: (value) => value?.isEmpty ?? true
                                    ? 'Ingresa tu contraseña'
                                    : null,
                                onFieldSubmitted: (_) {
                                  if (widget.changePassword) {
                                    newPasswordFocus.requestFocus();
                                  } else {
                                    submit();
                                  }
                                },
                              ),
                              if (widget.changePassword) ...[
                                const SizedBox(height: 18),
                                TextFormField(
                                  key: const ValueKey('auth.new-password'),
                                  controller: newPassword,
                                  focusNode: newPasswordFocus,
                                  readOnly: busy,
                                  obscureText: !newVisible,
                                  keyboardType: TextInputType.visiblePassword,
                                  textInputAction: TextInputAction.next,
                                  autocorrect: false,
                                  enableSuggestions: false,
                                  smartDashesType: SmartDashesType.disabled,
                                  smartQuotesType: SmartQuotesType.disabled,
                                  autofillHints: const [
                                    AutofillHints.newPassword,
                                  ],
                                  maxLength: 200,
                                  decoration: InputDecoration(
                                    labelText: 'Nueva contraseña',
                                    helperText:
                                        'Mínimo 12 caracteres y diferente de la temporal.',
                                    helperMaxLines: 2,
                                    suffixIcon: visibilityButton(
                                      showing: newVisible,
                                      label: 'nueva contraseña',
                                      focus: newPasswordFocus,
                                      toggle: () => newVisible = !newVisible,
                                    ),
                                  ),
                                  validator: (value) {
                                    if ((value?.length ?? 0) < 12) {
                                      return 'Usa al menos 12 caracteres';
                                    }
                                    if (value == password.text) {
                                      return 'Debe ser diferente de la contraseña temporal';
                                    }
                                    return null;
                                  },
                                  onFieldSubmitted: (_) =>
                                      confirmationFocus.requestFocus(),
                                ),
                                const SizedBox(height: 18),
                                TextFormField(
                                  key: const ValueKey('auth.confirm-password'),
                                  controller: confirmation,
                                  focusNode: confirmationFocus,
                                  readOnly: busy,
                                  obscureText: !confirmationVisible,
                                  keyboardType: TextInputType.visiblePassword,
                                  textInputAction: TextInputAction.done,
                                  autocorrect: false,
                                  enableSuggestions: false,
                                  smartDashesType: SmartDashesType.disabled,
                                  smartQuotesType: SmartQuotesType.disabled,
                                  autofillHints: const [
                                    AutofillHints.newPassword,
                                  ],
                                  decoration: InputDecoration(
                                    labelText: 'Repetir nueva contraseña',
                                    suffixIcon: visibilityButton(
                                      showing: confirmationVisible,
                                      label: 'confirmación de contraseña',
                                      focus: confirmationFocus,
                                      toggle: () => confirmationVisible =
                                          !confirmationVisible,
                                    ),
                                  ),
                                  validator: (value) =>
                                      value == null || value.isEmpty
                                      ? 'Repite la nueva contraseña'
                                      : value != newPassword.text
                                      ? 'Las contraseñas no coinciden'
                                      : null,
                                  onFieldSubmitted: (_) => submit(),
                                ),
                              ],
                              if (error != null)
                                Padding(
                                  padding: const EdgeInsets.only(top: 18),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        error!,
                                        style: TextStyle(
                                          color: Theme.of(
                                            context,
                                          ).colorScheme.error,
                                        ),
                                      ),
                                      if (WorkshopController.browserDemoEnabled && !context.watch<WorkshopController>().isAutonomous &&
                                          (error!.contains('No se pudo conectar') ||
                                              error!.contains('tardó demasiado') ||
                                              error!.contains('API'))) ...[
                                        const SizedBox(height: 8),
                                        FilledButton.tonalIcon(
                                          icon: const Icon(Icons.bolt_rounded, size: 16),
                                          label: const Text('Entrar en Demostración en navegador'),
                                          onPressed: () {
                                            context.read<WorkshopController>().setAutonomousMode(true);
                                            submit();
                                          },
                                        ),
                                      ],
                                    ],
                                  ),
                                ),
                              const SizedBox(height: 26),
                              SizedBox(
                                width: double.infinity,
                                child: AtelierAction(
                                  label: widget.changePassword
                                      ? 'Guardar y continuar'
                                      : 'Entrar a mi espacio',
                                  icon: Icons.arrow_forward_rounded,
                                  loading: busy,
                                  expand: true,
                                  onPressed: submit,
                                ),
                              ),
                              const SizedBox(height: 26),
                              if (widget.changePassword)
                                Center(
                                  child: TextButton(
                                    onPressed: busy
                                        ? null
                                        : () => runAction(
                                            context,
                                            context
                                                .read<WorkshopController>()
                                                .logout,
                                          ),
                                    child: const Text(
                                      'Volver al inicio de sesión',
                                    ),
                                  ),
                                ),
                              if (!widget.changePassword && WorkshopController.browserDemoEnabled) ...[
                                Container(
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: context.watch<WorkshopController>().isAutonomous
                                        ? context.atelier.success.withValues(alpha: .09)
                                        : Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: .4),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                      color: context.watch<WorkshopController>().isAutonomous
                                          ? context.atelier.success.withValues(alpha: .3)
                                          : Theme.of(context).colorScheme.outlineVariant,
                                    ),
                                  ),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Icon(
                                            context.watch<WorkshopController>().isAutonomous
                                                ? Icons.bolt_rounded
                                                : Icons.cloud_outlined,
                                            size: 18,
                                            color: context.watch<WorkshopController>().isAutonomous
                                                ? context.atelier.success
                                                : Theme.of(context).colorScheme.primary,
                                          ),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Text(
                                              context.watch<WorkshopController>().isAutonomous
                                                  ? 'Demostración en navegador'
                                                  : 'Modo Conectado (API FastAPI)',
                                              style: TextStyle(
                                                fontSize: 12,
                                                fontWeight: FontWeight.w700,
                                                color: context.watch<WorkshopController>().isAutonomous
                                                    ? context.atelier.success
                                                    : null,
                                              ),
                                            ),
                                          ),
                                          Switch(
                                            value: context.watch<WorkshopController>().isAutonomous,
                                            activeThumbColor: context.atelier.success,
                                            onChanged: busy
                                                ? null
                                                : (val) {
                                                    context.read<WorkshopController>().setAutonomousMode(val);
                                                  },
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        context.watch<WorkshopController>().isAutonomous
                                            ? 'Solo demostración. No utilizar para datos reales del taller.'
                                            : 'Conectando al servidor HTTP remoto.',
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: context.atelier.secondaryText,
                                          height: 1.4,
                                        ),
                                      ),
                                      const SizedBox(height: 10),
                                      const Text(
                                        'Accesos rápidos de prueba:',
                                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                                      ),
                                      const SizedBox(height: 6),
                                      Wrap(
                                        spacing: 6,
                                        runSpacing: 6,
                                        children: [
                                          ActionChip(
                                            avatar: const Icon(Icons.admin_panel_settings_outlined, size: 14),
                                            label: const Text('Admin', style: TextStyle(fontSize: 11)),
                                            onPressed: busy ? null : () => _quickLogin('admin', 'admin123'),
                                          ),
                                          ActionChip(
                                            avatar: const Icon(Icons.build_outlined, size: 14),
                                            label: const Text('Mecánico', style: TextStyle(fontSize: 11)),
                                            onPressed: busy ? null : () => _quickLogin('carlos.mecanico', 'mecanico123'),
                                          ),
                                          ActionChip(
                                            avatar: const Icon(Icons.person_outline, size: 14),
                                            label: const Text('Cliente', style: TextStyle(fontSize: 11)),
                                            onPressed: busy ? null : () => _quickLogin('patricio.mendez', 'cliente123'),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 16),
                              ],
                              Center(
                                child: Text(
                                  'Acceso seguro · Una sola plataforma',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: context.atelier.secondaryText,
                                  ),
                                ),
                              ),
                              if (theme.loadError != null && !context.watch<WorkshopController>().isAutonomous) ...[
                                const SizedBox(height: 18),
                                Container(
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: Theme.of(context).colorScheme.errorContainer.withValues(alpha: .2),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        theme.loadError!,
                                        style: TextStyle(
                                          fontSize: 12,
                                          color: Theme.of(context).colorScheme.error,
                                        ),
                                      ),
                                      const SizedBox(height: 8),
                                      Wrap(
                                        spacing: 8,
                                        children: [
                                          if (WorkshopController.browserDemoEnabled) FilledButton.tonalIcon(
                                            icon: const Icon(Icons.bolt_rounded, size: 16),
                                            label: const Text('Activar demostración'),
                                            onPressed: () {
                                              context.read<WorkshopController>().setAutonomousMode(true);
                                            },
                                          ),
                                          TextButton(
                                            onPressed: () => theme.initialize(),
                                            child: const Text('Reintentar conexión'),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Una de las tres razones para usar el sistema, en el panel de entrada.
///
/// Texto fijo y sin cifras: en el momento de iniciar sesión no hay sesion, asi
/// que cualquier numero aqui seria inventado. Lo que el concepto muestra como
/// «2 clientes activos» es una ilustracion del diseno, no un dato.
class _HeroPoint extends StatelessWidget {
  const _HeroPoint({
    required this.icon,
    required this.title,
    required this.detail,
  });

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    final palette = context.atelier;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: .09),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: palette.accent, size: 21),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                detail,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: .55),
                  fontSize: 12,
                  height: 1.5,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}