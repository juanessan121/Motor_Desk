import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/config/theme_controller.dart';
import 'core/network/api_client.dart';
import 'core/state/make_logo_cache.dart';
import 'core/state/workshop_controller.dart';
import 'features/auth/login_page.dart';
import 'features/dashboard/admin_shell.dart';
import 'features/customer/customer_home.dart';

class MotorDeskApp extends StatefulWidget {
  const MotorDeskApp({super.key, this.api, this.initialize = true});
  final ApiClient? api;
  final bool initialize;
  @override
  State<MotorDeskApp> createState() => _MotorDeskAppState();
}

class _MotorDeskAppState extends State<MotorDeskApp>
    with WidgetsBindingObserver {
  late final ThemeController theme;
  late final WorkshopController workshop;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final api = widget.api ?? ApiClient();
    theme = ThemeController(api);
    workshop = WorkshopController(api, theme);
    if (widget.initialize) workshop.initialize();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) workshop.resume();
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      workshop.pauseEvents();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    workshop.dispose();
    theme.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: theme),
      ChangeNotifierProvider.value(value: workshop),
      // Los logotipos de marca se piden una vez para todas las tarjetas. Sin
      // provider, cada tarjeta tendría su propia copia y cada una pediría el
      // catálogo entero al servidor.
      ChangeNotifierProvider(create: (_) => MakeLogoCache(workshop.api)),
    ],
    child: Consumer2<ThemeController, WorkshopController>(
      builder: (context, theme, workshop, _) => MaterialApp(
        title: theme.config.name,
        debugShowCheckedModeBanner: false,
        theme: theme.theme,
        locale: const Locale('es'),
        supportedLocales: const [Locale('es'), Locale('en')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: !workshop.signedIn || workshop.needsPassword
            ? LoginPage(
                key: ValueKey(
                  workshop.needsPassword
                      ? 'auth.password-change'
                      : 'auth.login',
                ),
                changePassword: workshop.needsPassword,
              )
            : workshop.isCustomer
            ? const CustomerHome()
            : const AdminShell(),
      ),
    ),
  );
}
