import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/theme/app_theme.dart';
import 'features/shell/app_shell.dart';
import 'l10n/app_localizations.dart';
import 'services/sources_service.dart';
import 'state/app_state.dart';
import 'state/sources_controller.dart';

class WeatherGptApp extends StatelessWidget {
  const WeatherGptApp({super.key, this.state, this.sourcesService});

  /// Injectable for tests; defaults to a fresh [AppState].
  final AppState? state;

  /// Injectable for tests; backs the shared [SourcesController] that feeds the
  /// sources drawer and the per-tab source strips.
  final SourcesService? sourcesService;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => state ?? AppState()),
        // One registry fetch shared by the drawer and both tab strips.
        ChangeNotifierProvider(
          create: (_) => SourcesController(service: sourcesService),
        ),
      ],
      child: Consumer<AppState>(
        builder: (context, appState, _) => MaterialApp(
          title: 'WeatherGPT',
          onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
          locale: appState.locale,
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          theme: AppTheme.light(),
          home: const AppShell(),
        ),
      ),
    );
  }
}