import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../l10n/app_localizations.dart';
import '../../models/provenance.dart';

/// Renders a [Provenance] envelope — the "source transparency" building block.
///
/// Every weather/alert/chat answer shows who provided the data, when it was
/// fetched, and whether it is an authoritative (official) source. Official
/// sources are never re-labelled: the badge only states the fact.
class SourceCard extends StatelessWidget {
  const SourceCard({super.key, required this.provenance});

  final Provenance provenance;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);

    final asOf = provenance.fetchedAt != null
        ? l10n.asOfTime(DateFormat('d MMM, HH:mm').format(provenance.fetchedAt!.toLocal()))
        : null;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(
              provenance.authoritative
                  ? Icons.verified_outlined
                  : Icons.cloud_outlined,
              size: 20,
              color: provenance.authoritative
                  ? theme.colorScheme.primary
                  : theme.colorScheme.outline,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          provenance.sourceName,
                          style: theme.textTheme.bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w600),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (provenance.authoritative) ...[
                        const SizedBox(width: 8),
                        _Badge(
                          label: l10n.officialSource,
                          color: theme.colorScheme.primary,
                        ),
                      ],
                    ],
                  ),
                  if (asOf != null) ...[
                    const SizedBox(height: 2),
                    Text(asOf, style: theme.textTheme.bodySmall),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}