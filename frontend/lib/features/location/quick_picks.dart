import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../models/location.dart';
import '../../services/locations_service.dart';

/// Demo-friendly quick picks shown when no location is selected yet.
/// Tapping a chip searches and resolves to the top candidate.
///
/// The chip label is localized, but the search always goes out as the
/// canonical Latin name: the Open-Meteo geocoder is Latin-only, so a
/// Devanagari label sent as a query would resolve to nothing. The backend's
/// offline alias index *can* fold `कोलकाता` back to Kolkata, but relying on
/// that would make the chips depend on the curated seed list staying complete.
class QuickPicks extends StatelessWidget {
  const QuickPicks({super.key, required this.locations, required this.onPicked});

  final LocationsService locations;
  final ValueChanged<SelectedLocation> onPicked;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final picks = <({String query, String label})>[
      (query: 'Kolkata', label: l10n.quickPickKolkata),
      (query: 'Mumbai', label: l10n.quickPickMumbai),
      (query: 'Delhi', label: l10n.quickPickDelhi),
      (query: 'Bengaluru', label: l10n.quickPickBengaluru),
    ];

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(l10n.quickPicks, style: theme.textTheme.bodySmall),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          alignment: WrapAlignment.center,
          children: [
            for (final pick in picks)
              ActionChip(
                label: Text(pick.label),
                onPressed: () async {
                  try {
                    final result = await locations.search(pick.query);
                    if (result.candidates.isEmpty) return;
                    onPicked(
                      SelectedLocation.fromCandidate(result.candidates.first),
                    );
                  } on Exception {
                    // Search errors surface through the location bar itself.
                  }
                },
              ),
          ],
        ),
      ],
    );
  }
}
