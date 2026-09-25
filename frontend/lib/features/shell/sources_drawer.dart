import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/widgets/source_status.dart';
import '../../l10n/app_localizations.dart';
import '../../models/source.dart';
import '../../state/sources_controller.dart';

/// Sources drawer (Phase 4 Step 8, wired to the registry in Phase 6/7).
///
/// The provenance-transparency story: it lists exactly which providers back the
/// app, mirroring the per-card [SourceCard] philosophy — data is never
/// re-labelled and official sources are flagged as such.
///
/// The list comes from `GET /api/v1/sources` (the curated integration matrix with
/// **live** availability, so e.g. IMD reads "Requires authorization" until the
/// key is granted) via the shared [SourcesController]. While that request is in
/// flight, or if it fails, the drawer renders a built-in list instead — the
/// transparency story must not depend on the network, and the demo must never
/// show an empty panel.
///
/// A failed fetch is shown as an explicit error banner (not just a footnote) with
/// a **Retry** action, because "the live registry is unreachable" is something
/// the presenter wants to notice and fix, not something to quietly paper over.
class SourcesDrawer extends StatefulWidget {
  const SourcesDrawer({super.key});

  @override
  State<SourcesDrawer> createState() => _SourcesDrawerState();
}

class _SourcesDrawerState extends State<SourcesDrawer> {
  @override
  void initState() {
    super.initState();
    // Post-frame: the controller notifies listeners while loading, which must
    // not happen during build. The controller itself de-duplicates, so opening
    // the drawer alongside the tab strips still costs one request.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<SourcesController>().load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final controller = context.watch<SourcesController>();
    final live = controller.sources;

    return Drawer(
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            DrawerHeader(
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    l10n.appTitle,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: theme.colorScheme.onPrimaryContainer,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    l10n.appTagline,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onPrimaryContainer,
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      l10n.sourcesTitle,
                      style: theme.textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
                  if (live != null) _RegistryChip(l10n: l10n, sources: live),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text(
                l10n.sourcesIntro,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.outline),
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 8),
                children: [
                  if (controller.failed)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                      child: SourceRegistryErrorBanner(
                        message: l10n.sourcesFallbackNotice,
                        retrying: controller.loading,
                        onRetry: () =>
                            context.read<SourcesController>().retry(),
                      ),
                    ),
                  for (final source in live != null
                      ? _fromRegistry(l10n, live)
                      : _builtIn(l10n))
                    _SourceTile(source: source),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// The live registry, mapped into the drawer's view model. Descriptions stay
  /// localized (keyed by source id) where we have a translation, falling back
  /// to the backend's own role text.
  static List<_DrawerSource> _fromRegistry(
    AppLocalizations l10n,
    List<SourceInfo> sources,
  ) =>
      [
        for (final source in sources)
          _DrawerSource(
            icon: sourceIcon(source.id),
            name: source.name,
            description: _descriptionFor(l10n, source),
            official: source.official,
            statusLabel: sourceStatusLabel(l10n, source),
            statusTone: sourceStatusTone(source),
            detail: source.available ? null : source.availableMessage,
          ),
      ];

  /// Built-in list — what we show while loading or when the registry is
  /// unreachable. Deliberately the same four providers the UI has always shown.
  static List<_DrawerSource> _builtIn(AppLocalizations l10n) => [
        _DrawerSource(
          icon: Icons.cloud_outlined,
          name: 'Open-Meteo',
          description: l10n.sourceOpenMeteo,
        ),
        _DrawerSource(
          icon: Icons.verified_outlined,
          name: 'SACHET · NDMA',
          description: l10n.sourceSachet,
          official: true,
        ),
        _DrawerSource(
          icon: Icons.my_location_outlined,
          name: 'BigDataCloud',
          description: l10n.sourceBigDataCloud,
        ),
        _DrawerSource(
          icon: Icons.map_outlined,
          name: 'OpenStreetMap',
          description: l10n.sourceOpenStreetMap,
        ),
      ];

  static String _descriptionFor(AppLocalizations l10n, SourceInfo source) =>
      switch (source.id) {
        'imd' => l10n.sourceImd,
        'open_meteo' => l10n.sourceOpenMeteo,
        'sachet' => l10n.sourceSachet,
        'geocoding_open_meteo' => l10n.sourceGeocoding,
        'bigdatacloud' => l10n.sourceBigDataCloud,
        'openstreetmap' => l10n.sourceOpenStreetMap,
        'llm' => l10n.sourceLlm,
        'mosdac' => l10n.sourceMosdac,
        'noaa_gfs' => l10n.sourceGfs,
        _ => source.role,
      };
}

/// "Live registry · 6 of 9 available" — proof the panel is reading the API.
class _RegistryChip extends StatelessWidget {
  const _RegistryChip({required this.l10n, required this.sources});

  final AppLocalizations l10n;
  final List<SourceInfo> sources;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final available = sources.where((s) => s.available).length;
    return Tooltip(
      message: l10n.sourcesLive,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: theme.colorScheme.primary.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          l10n.sourcesSummary(available, sources.length),
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: theme.colorScheme.primary,
          ),
        ),
      ),
    );
  }
}

/// View model for one drawer row — built either from the registry or the
/// built-in list, so the tile widget is identical for both.
class _DrawerSource {
  const _DrawerSource({
    required this.icon,
    required this.name,
    required this.description,
    this.official = false,
    this.statusLabel,
    this.statusTone,
    this.detail,
  });

  final IconData icon;
  final String name;
  final String description;
  final bool official;
  final String? statusLabel;
  final SourceStatusTone? statusTone;
  final String? detail;
}

class _SourceTile extends StatelessWidget {
  const _SourceTile({required this.source});

  final _DrawerSource source;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final official = source.official;

    return ListTile(
      leading: CircleAvatar(
        backgroundColor:
            (official ? theme.colorScheme.primary : theme.colorScheme.surfaceContainerHighest)
                .withValues(alpha: 0.9),
        child: Icon(
          source.icon,
          size: 20,
          color: official
              ? theme.colorScheme.onPrimary
              : theme.colorScheme.onSurfaceVariant,
        ),
      ),
      title: Row(
        children: [
          Flexible(
            child: Text(
              source.name,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (official) ...[
            const SizedBox(width: 8),
            SourceStatusBadge(
              label: l10n.officialSource,
              tone: SourceStatusTone.ok,
            ),
          ],
        ],
      ),
      isThreeLine: source.detail != null,
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(source.description, style: theme.textTheme.bodySmall),
          if (source.statusLabel != null) ...[
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerLeft,
              child: SourceStatusBadge(
                label: source.statusLabel!,
                tone: source.statusTone ?? SourceStatusTone.neutral,
              ),
            ),
          ],
          if (source.detail != null) ...[
            const SizedBox(height: 4),
            Text(
              source.detail!,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.outline),
            ),
          ],
        ],
      ),
    );
  }
}
