/// Mirrors `backend/app/domain/models.py` — `Provenance`.
///
/// Every answer from the backend is traceable to a source, a fetch time and a
/// validity window. The UI renders this in source cards; the model is
/// deliberately a plain mirror of the API shape.
class Provenance {
  const Provenance({
    required this.sourceId,
    required this.sourceName,
    required this.authoritative,
    this.fetchedAt,
    this.validAt,
    this.ttlSeconds,
    this.rawEndpoint,
  });

  final String sourceId;
  final String sourceName;
  final bool authoritative;
  final DateTime? fetchedAt;
  final DateTime? validAt;
  final int? ttlSeconds;
  final String? rawEndpoint;

  factory Provenance.fromJson(Map<String, dynamic> json) => Provenance(
        sourceId: json['source_id'] as String? ?? '',
        sourceName: json['source_name'] as String? ?? '',
        authoritative: json['authoritative'] as bool? ?? false,
        fetchedAt: _parseDate(json['fetched_at']),
        validAt: _parseDate(json['valid_at']),
        ttlSeconds: json['ttl_seconds'] as int?,
        rawEndpoint: json['raw_endpoint'] as String?,
      );

  static DateTime? _parseDate(Object? value) {
    if (value is String && value.isNotEmpty) {
      return DateTime.tryParse(value);
    }
    return null;
  }
}