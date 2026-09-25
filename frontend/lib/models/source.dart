/// One data source as reported by `GET /api/v1/sources`.
///
/// Mirrors the backend `SourceInfo` (backend/app/domain/models.py). `status` is
/// the *curated* integration status from docs/DATA-SOURCES.md, while
/// [available] is the live runtime readiness — they differ: IMD is
/// `requires_authorization` (and unavailable) until a key is granted.
class SourceInfo {
  const SourceInfo({
    required this.id,
    required this.name,
    required this.role,
    required this.status,
    required this.auth,
    required this.url,
    this.evidenceUrl,
    this.official = false,
    this.available = true,
    this.availableMessage,
    this.notes,
  });

  final String id;
  final String name;
  final String role;
  final String status;
  final String auth;
  final String url;
  final String? evidenceUrl;
  final bool official;
  final bool available;

  /// Why the source is not available (e.g. a missing API key). Shown as-is:
  /// the registry never hides a gap.
  final String? availableMessage;
  final String? notes;

  factory SourceInfo.fromJson(Map<String, dynamic> json) => SourceInfo(
        id: json['source_id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        role: json['role'] as String? ?? '',
        status: json['status'] as String? ?? 'implemented',
        auth: json['auth'] as String? ?? '',
        url: json['url'] as String? ?? '',
        evidenceUrl: json['evidence_url'] as String?,
        official: json['official'] as bool? ?? false,
        available: json['available'] as bool? ?? true,
        availableMessage: json['available_message'] as String?,
        notes: json['notes'] as String?,
      );
}
