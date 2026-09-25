import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../l10n/app_localizations.dart';
import '../../state/app_state.dart';

/// App-wide language picker (Phase 4 Step 7).
///
/// A globe icon in the shell app bar that switches EN / HI / Hinglish. The
/// choice lives in [AppState], so every tab re-localizes instantly. Language
/// names show in their own script (English, हिन्दी, Hinglish) — standard for
/// language pickers, so no l10n keys are needed for the entries themselves.
class LanguageSelector extends StatelessWidget {
  const LanguageSelector({super.key});

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final l10n = AppLocalizations.of(context);

    return PopupMenuButton<AppLanguage>(
      icon: const Icon(Icons.language),
      tooltip: l10n.language,
      onSelected: (language) =>
          context.read<AppState>().setLanguage(language),
      itemBuilder: (context) => [
        for (final language in AppLanguage.values)
          PopupMenuItem(
            value: language,
            child: Row(
              children: [
                Icon(
                  language == appState.language
                      ? Icons.check
                      : Icons.check_box_outline_blank,
                  size: 18,
                  color: language == appState.language
                      ? Theme.of(context).colorScheme.primary
                      : Colors.transparent,
                ),
                const SizedBox(width: 8),
                Text(language.label),
              ],
            ),
          ),
      ],
    );
  }
}