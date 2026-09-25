import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../../models/weather.dart';

/// Current-conditions card.
///
/// Shows the location, the temperature and condition prominently, then a grid
/// of metrics. **Only parameters the source actually provided are rendered**
/// (`null` ≠ 0) — matching the backend's "show what exists" rule.
class CurrentConditionsCard extends StatelessWidget {
  const CurrentConditionsCard({super.key, required this.observation});

  final WeatherObservation observation;

  static IconData iconFor(int? weatherCode) {
    if (weatherCode == null) return Icons.cloud_outlined;
    if (weatherCode <= 1) return Icons.wb_sunny_outlined;
    if (weatherCode <= 3) return Icons.cloud_outlined;
    if (weatherCode == 45 || weatherCode == 48) return Icons.foggy;
    if (weatherCode <= 67) return Icons.umbrella_outlined;
    if (weatherCode <= 77) return Icons.ac_unit_outlined;
    if (weatherCode <= 82) return Icons.umbrella_outlined;
    if (weatherCode <= 99) return Icons.thunderstorm_outlined;
    return Icons.cloud_outlined;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final o = observation;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.place_outlined, size: 18, color: theme.colorScheme.primary),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    o.locationName ?? '—',
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(iconFor(o.weatherCode), size: 48, color: theme.colorScheme.primary),
                const SizedBox(width: 16),
                if (o.temperatureC != null)
                  Text(
                    '${o.temperatureC!.round()}°C',
                    style: theme.textTheme.displayMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (o.conditionText != null)
                        Text(o.conditionText!, style: theme.textTheme.titleMedium),
                      if (o.observedAt != null)
                        Text(
                          '${l10n.observedAt} ${_time(o.observedAt!)}',
                          style: theme.textTheme.bodySmall,
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 24,
              runSpacing: 8,
              children: [
                if (o.humidityPct != null)
                  _Metric(
                    icon: Icons.water_drop_outlined,
                    label: l10n.humidity,
                    value: '${o.humidityPct!.round()}%',
                  ),
                if (o.windSpeedKmph != null)
                  _Metric(
                    icon: Icons.air,
                    label: l10n.wind,
                    value: o.windDirection != null
                        ? '${o.windSpeedKmph!.round()} km/h ${o.windDirection}'
                        : '${o.windSpeedKmph!.round()} km/h',
                  ),
                if (o.pressureHpa != null)
                  _Metric(
                    icon: Icons.speed_outlined,
                    label: l10n.pressure,
                    value: '${o.pressureHpa!.round()} hPa',
                  ),
                if (o.rainfall24hMm != null)
                  _Metric(
                    icon: Icons.umbrella_outlined,
                    label: _rainfallLabel(l10n, o.rainfallBasis),
                    value: '${o.rainfall24hMm} mm',
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// The same field carries three different things depending on the source, so the
  /// label has to follow what the number *is*: observed past-24h rain (IMD), forecast
  /// rain for the coming 24h (MET Norway) or instantaneous precipitation (Open-Meteo).
  /// An undeclared basis gets a neutral label that claims no window at all.
  static String _rainfallLabel(AppLocalizations l10n, String? basis) =>
      switch (basis) {
        'observed_24h' => l10n.rainfall24h,
        'forecast_24h' => l10n.rainfallNext24h,
        'instant' => l10n.rainfallNow,
        _ => l10n.rainfallGeneric,
      };

  static String _time(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: theme.colorScheme.outline),
        const SizedBox(width: 6),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: theme.textTheme.bodySmall),
            Text(
              value,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ],
    );
  }
}