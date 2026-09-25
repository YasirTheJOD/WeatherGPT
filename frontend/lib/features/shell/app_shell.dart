import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../alerts/alerts_screen.dart';
import '../chat/chat_screen.dart';
import '../map/map_screen.dart';
import '../weather/weather_screen.dart';
import 'language_selector.dart';
import 'sources_drawer.dart';

/// App shell: Material 3 bottom navigation with the three core tabs.
/// An IndexedStack preserves each tab's state when switching.
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.appTitle),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 8),
            child: LanguageSelector(),
          ),
        ],
      ),
      drawer: const SourcesDrawer(),
      body: IndexedStack(
        index: _index,
        children: const [
          ChatScreen(),
          WeatherScreen(),
          AlertsScreen(),
          MapScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.forum_outlined),
            selectedIcon: const Icon(Icons.forum),
            label: l10n.navChat,
          ),
          NavigationDestination(
            icon: const Icon(Icons.cloud_outlined),
            selectedIcon: const Icon(Icons.cloud),
            label: l10n.navWeather,
          ),
          NavigationDestination(
            icon: const Icon(Icons.warning_amber_outlined),
            selectedIcon: const Icon(Icons.warning_amber),
            label: l10n.navAlerts,
          ),
          NavigationDestination(
            icon: const Icon(Icons.map_outlined),
            selectedIcon: const Icon(Icons.map),
            label: l10n.navMap,
          ),
        ],
      ),
    );
  }
}