import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../features/alerts/severity.dart';
import '../../../l10n/app_localizations.dart';
import '../../../models/alert.dart';

/// One official warning, rendered as an OFFICIAL WARNING block.
///
/// Safety contract: severity/urgency/event/description/instruction are shown
/// exactly as received from the CAP feed — nothing is re-labelled, upgraded or
/// downgraded. The card carries the validity window and provenance.
class AlertCard extends StatelessWidget {
  const AlertCard({super.key, required this.alert});

  final Alert alert;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final severity = severityFrom(alert.severity);
    final color = severityColor(severity);

    final areaNames = alert.areas.map((a) => a.areaDesc).where((s) => s.isNotEmpty);
    final validFrom = _format(alert.effectiveAt);
    final validUntil = _format(alert.expiresAt);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Container(
        decoration: BoxDecoration(
          border: Border(left: BorderSide(color: color, width: 5)),
          color: color.withValues(alpha: 0.05),
        ),
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.warning_amber_rounded, size: 20, color: color),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    l10n.officialWarning,
                    style: theme.textTheme.labelLarge?.copyWith(
                      color: color,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
                _SeverityChip(severity: severity, color: color, l10n: l10n),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              alert.event,
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            if (alert.headline != null && alert.headline != alert.event) ...[
              const SizedBox(height: 4),
              Text(alert.headline!, style: theme.textTheme.bodyMedium),
            ],
            if (alert.description != null) ...[
              const SizedBox(height: 8),
              Text(alert.description!, style: theme.textTheme.bodyMedium),
            ],
            if (alert.instruction != null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.campaign_outlined, size: 16, color: theme.colorScheme.primary),
                  const SizedBox(width: 6),
                  Text(
                    l10n.whatToDo,
                    style: theme.textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: theme.colorScheme.primary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(alert.instruction!, style: theme.textTheme.bodyMedium),
            ],
            if (areaNames.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                '${l10n.affectedAreas}: ${areaNames.join(', ')}',
                style: theme.textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 10),
            Row(
              children: [
                if (validFrom != null)
                  Text(
                    l10n.issuedAt(validFrom),
                    style: theme.textTheme.bodySmall,
                  ),
                if (validUntil != null) ...[
                  const SizedBox(width: 12),
                  Text(
                    l10n.expiresAt(validUntil),
                    style: theme.textTheme.bodySmall,
                  ),
                ],
                const Spacer(),
                Flexible(
                  child: Text(
                    alert.provenance.sourceName,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.outline,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static String? _format(DateTime? value) {
    if (value == null) return null;
    return DateFormat('d MMM, HH:mm').format(value.toLocal());
  }
}

class _SeverityChip extends StatelessWidget {
  const _SeverityChip({required this.severity, required this.color, required this.l10n});

  final CapSeverity severity;
  final Color color;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    final label = switch (severity) {
      CapSeverity.extreme => l10n.severityExtreme,
      CapSeverity.severe => l10n.severitySevere,
      CapSeverity.moderate => l10n.severityModerate,
      CapSeverity.minor => l10n.severityMinor,
      CapSeverity.unknown => '',
    };
    if (label.isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }
}