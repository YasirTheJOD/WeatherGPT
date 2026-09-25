import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../l10n/app_localizations.dart';
import '../../models/source.dart';
import '../../state/sources_controller.dart';

/// Shared presentation of the data-source registry, used by the sources drawer
/// and by the compact [SourceStatusStrip] on the alerts and map tabs — one
/// definition of "what does this source's status look like, and is it
/// localized", so the three surfaces cannot drift apart.
enum SourceStatusTone {
  /// Serving data right now.
  ok,

  /// Known, but not usable yet (pending authorization) or currently down.
  attention,

  /// Not part of the MVP by design (planned / future scope).
  neutral,
}

SourceStatusTone sourceStatusTone(SourceInfo source) {
  if (source.available) return SourceStatusTone.ok;
  if (source.status == 'planned' || source.status == 'future_scope') {
    return SourceStatusTone.neutral;
  }
  return SourceStatusTone.attention;
}

/// Localized status label. The curated [SourceInfo.status] and the live
/// [SourceInfo.available] flag are different things and are shown as such:
/// "Requires authorization" (curated) vs simply "Unavailable" (anything else).
String sourceStatusLabel(AppLocalizations l10n, SourceInfo source) {
  if (source.available) return l10n.sourceAvailable;
  return switch (source.status) {
    'requires_authorization' => l10n.sourceRequiresAuth,
    'planned' || 'future_scope' => l10n.sourcePlanned,
    _ => l10n.sourceUnavailable,
  };
}

/// Icon for a registry source id (brand-ish glyphs; ids come from the backend).
IconData sourceIcon(String id) => switch (id) {
      'imd' => Icons.verified_outlined,
      'open_meteo' => Icons.cloud_outlined,
      'sachet' => Icons.campaign_outlined,
      'geocoding_open_meteo' => Icons.travel_explore,
      'bigdatacloud' => Icons.my_location_outlined,
      'openstreetmap' => Icons.map_outlined,
      'llm' => Icons.forum_outlined,
      'mosdac' => Icons.satellite_alt_outlined,
      'noaa_gfs' => Icons.dataset_outlined,
      _ => Icons.dns_outlined,
    };

/// Short, stable display name for a source pill. These are brand/proper nouns,
/// so they stay in English in both locales (as the drawer's built-in list does)
/// — only the *status* is translated.
String sourceShortName(String id) => switch (id) {
      'imd' => 'IMD',
      'open_meteo' => 'Open-Meteo',
      'sachet' => 'SACHET · NDMA',
      'geocoding_open_meteo' => 'Geocoding',
      'bigdatacloud' => 'BigDataCloud',
      'openstreetmap' => 'OpenStreetMap',
      'llm' => 'LLM',
      'mosdac' => 'MOSDAC',
      'noaa_gfs' => 'GFS',
      _ => id,
    };

/// The small status/badge chip used for "Available", "Requires authorization"
/// and the OFFICIAL SOURCE marker.
class SourceStatusBadge extends StatelessWidget {
  const SourceStatusBadge({
    super.key,
    required this.label,
    required this.tone,
  });

  final String label;
  final SourceStatusTone tone;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (background, foreground) = switch (tone) {
      // The "ok" tone doubles as the official-source badge: a tint of primary.
      SourceStatusTone.ok => (scheme.primaryContainer, scheme.onPrimaryContainer),
      SourceStatusTone.attention => (
          scheme.tertiaryContainer,
          scheme.onTertiaryContainer,
        ),
      SourceStatusTone.neutral => (
          scheme.surfaceContainerHighest,
          scheme.onSurfaceVariant,
        ),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: foreground,
        ),
      ),
    );
  }
}

/// Compact "which sources back this tab, and are they up?" strip. Renders one
/// pill per requested source id with its live status, or an error + retry when
/// the registry is unreachable.
class SourceStatusStrip extends StatefulWidget {
  const SourceStatusStrip({super.key, required this.sourceIds});

  final List<String> sourceIds;

  @override
  State<SourceStatusStrip> createState() => _SourceStatusStripState();
}

class _SourceStatusStripState extends State<SourceStatusStrip> {
  @override
  void initState() {
    super.initState();
    // Post-frame, like the other screens' loads: notifying listeners during
    // build would be illegal.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<SourcesController>().load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<SourcesController>();
    final l10n = AppLocalizations.of(context);

    if (controller.failed) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
        child: SourceRegistryErrorBanner(
          message: l10n.sourcesRegistryUnreachable,
          retrying: controller.loading,
          onRetry: () => context.read<SourcesController>().retry(),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final id in widget.sourceIds)
            _StatusPill(source: controller.byId(id), sourceId: id),
        ],
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.source, required this.sourceId});

  /// Null while the registry is still loading, or if the backend didn't report
  /// this source — the pill then shows no status rather than a guess.
  final SourceInfo? source;
  final String sourceId;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final resolved = source;

    final tone = resolved == null
        ? SourceStatusTone.neutral
        : sourceStatusTone(resolved);
    final toneColor = switch (tone) {
      SourceStatusTone.ok => theme.colorScheme.primary,
      SourceStatusTone.attention => theme.colorScheme.error,
      SourceStatusTone.neutral => theme.colorScheme.outline,
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(sourceIcon(sourceId), size: 14, color: theme.colorScheme.outline),
          const SizedBox(width: 6),
          Text(
            sourceShortName(sourceId),
            style: theme.textTheme.labelMedium
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(width: 6),
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: toneColor, shape: BoxShape.circle),
          ),
          if (resolved != null) ...[
            const SizedBox(width: 5),
            Text(
              sourceStatusLabel(l10n, resolved),
              style: theme.textTheme.labelSmall?.copyWith(color: toneColor),
            ),
          ],
        ],
      ),
    );
  }
}

/// Error row with a retry action, shared by the drawer and the strips so the
/// "registry unreachable" state looks the same everywhere.
class SourceRegistryErrorBanner extends StatelessWidget {
  const SourceRegistryErrorBanner({
    super.key,
    required this.message,
    required this.retrying,
    required this.onRetry,
  });

  final String message;
  final bool retrying;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final onContainer = theme.colorScheme.onErrorContainer;

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 6, 6, 6),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_off_outlined, size: 18, color: onContainer),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.bodySmall?.copyWith(color: onContainer),
            ),
          ),
          if (retrying)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: onContainer,
                ),
              ),
            )
          else
            TextButton(
              onPressed: onRetry,
              style: TextButton.styleFrom(
                foregroundColor: onContainer,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                minimumSize: const Size(0, 32),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: Text(l10n.retry),
            ),
        ],
      ),
    );
  }
}
