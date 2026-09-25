import 'provenance.dart';

/// Mirrors `backend/app/domain/models.py` — `CapArea`.
class CapArea {
  const CapArea({required this.areaDesc, this.circles = const [], this.polygons = const []});

  final String areaDesc;
  final List<String> circles; // "lat,lon radius"
  final List<String> polygons; // "lat,lon lat,lon ..."

  factory CapArea.fromJson(Map<String, dynamic> json) => CapArea(
        areaDesc: json['area_desc'] as String? ?? '',
        circles: _stringList(json['circles']),
        polygons: _stringList(json['polygons']),
      );

  static List<String> _stringList(Object? value) =>
      value is List ? value.whereType<String>().toList() : const [];
}

/// Mirrors `backend/app/domain/models.py` — `Alert` (full CAP 1.2).
///
/// Official government warning data. Severity/urgency are passed through
/// verbatim from SACHET — the UI must never re-label them.
class Alert {
  const Alert({
    required this.identifier,
    this.sender,
    this.sentAt,
    this.status,
    this.msgType,
    this.scope,
    required this.event,
    this.category,
    this.urgency,
    this.severity,
    this.certainty,
    this.effectiveAt,
    this.expiresAt,
    this.headline,
    this.description,
    this.instruction,
    this.areas = const [],
    this.polygonUrl,
    required this.provenance,
  });

  final String identifier;
  final String? sender;
  final DateTime? sentAt;
  final String? status;
  final String? msgType;
  final String? scope;
  final String event;
  final String? category;
  final String? urgency;
  final String? severity;
  final String? certainty;
  final DateTime? effectiveAt;
  final DateTime? expiresAt;
  final String? headline;
  final String? description;
  final String? instruction;
  final List<CapArea> areas;
  final String? polygonUrl;
  final Provenance provenance;

  factory Alert.fromJson(Map<String, dynamic> json) => Alert(
        identifier: json['identifier'] as String? ?? '',
        sender: json['sender'] as String?,
        sentAt: _parseDate(json['sent_at']),
        status: json['status'] as String?,
        msgType: json['msg_type'] as String?,
        scope: json['scope'] as String?,
        event: json['event'] as String? ?? 'Weather alert',
        category: json['category'] as String?,
        urgency: json['urgency'] as String?,
        severity: json['severity'] as String?,
        certainty: json['certainty'] as String?,
        effectiveAt: _parseDate(json['effective_at']),
        expiresAt: _parseDate(json['expires_at']),
        headline: json['headline'] as String?,
        description: json['description'] as String?,
        instruction: json['instruction'] as String?,
        areas: json['areas'] is List
            ? (json['areas'] as List)
                .whereType<Map<String, dynamic>>()
                .map(CapArea.fromJson)
                .toList()
            : const [],
        polygonUrl: json['polygon_url'] as String?,
        provenance: Provenance.fromJson(
          json['provenance'] as Map<String, dynamic>? ?? const {},
        ),
      );

  static DateTime? _parseDate(Object? value) =>
      value is String && value.isNotEmpty ? DateTime.tryParse(value) : null;
}

/// Mirrors `backend/app/domain/models.py` — `AlertSummary` (feed index entry).
class AlertSummary {
  const AlertSummary({
    required this.identifier,
    required this.title,
    this.category,
    this.author,
    this.publishedAt,
    this.detailUrl,
    required this.provenance,
  });

  final String identifier;
  final String title;
  final String? category;
  final String? author;
  final DateTime? publishedAt;
  final String? detailUrl;
  final Provenance provenance;

  factory AlertSummary.fromJson(Map<String, dynamic> json) => AlertSummary(
        identifier: json['identifier'] as String? ?? '',
        title: json['title'] as String? ?? '',
        category: json['category'] as String?,
        author: json['author'] as String?,
        publishedAt: json['published_at'] is String
            ? DateTime.tryParse(json['published_at'] as String)
            : null,
        detailUrl: json['detail_url'] as String?,
        provenance: Provenance.fromJson(
          json['provenance'] as Map<String, dynamic>? ?? const {},
        ),
      );
}