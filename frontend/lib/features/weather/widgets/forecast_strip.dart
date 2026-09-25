import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../l10n/app_localizations.dart';
import '../../../models/weather.dart';

/// Horizontally scrollable 7-day forecast strip. Each card shows the weekday,
/// high/low and condition; fields the source didn't provide are omitted.
class ForecastStrip extends StatelessWidget {
  const ForecastStrip({super.key, required this.days, required this.localeCode});

  final List<ForecastDay> days;
  final String localeCode;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Text(
            l10n.forecastHeader,
            style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
        SizedBox(
          height: 160,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: days.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final day = days[index];
              final isToday = day.dateTime.day == DateTime.now().day;
              final weekday = isToday
                  ? l10n.today
                  : DateFormat('EEE', localeCode).format(day.dateTime);
              return _DayCard(
                weekday: weekday,
                date: DateFormat('d MMM', localeCode).format(day.dateTime),
                day: day,
              );
            },
          ),
        ),
      ],
    );
  }
}

class _DayCard extends StatelessWidget {
  const _DayCard({
    required this.weekday,
    required this.date,
    required this.day,
  });

  final String weekday;
  final String date;
  final ForecastDay day;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: 110,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            weekday,
            style: theme.textTheme.labelLarge?.copyWith(
              fontWeight: FontWeight.w600,
              color: theme.colorScheme.primary,
            ),
            overflow: TextOverflow.ellipsis,
          ),
          Text(date, style: theme.textTheme.bodySmall),
          if (day.tmaxC != null || day.tminC != null)
            Text(
              [
                if (day.tmaxC != null) '${day.tmaxC!.round()}°',
                if (day.tminC != null) '${day.tminC!.round()}°',
              ].join(' / '),
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
          if (day.conditionText != null) ...[
            const SizedBox(height: 2),
            Text(
              day.conditionText!,
              style: theme.textTheme.bodySmall,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
          if (day.rainfallMm != null)
            Text(
              '🌧 ${day.rainfallMm} mm',
              style: theme.textTheme.bodySmall,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
        ],
      ),
    );
  }
}