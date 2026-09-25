/// Mirrors `backend/app/domain/models.py` — `ValidationReport` / `ValidationIssue`.
///
/// The backend gate validates schema, plausibility and freshness. Issues of
/// level "warning" are surfaced to the user (staleness is never hidden);
/// "error"-level issues mean the source was discarded (the provider chain then
/// falls back or fails).
class ValidationReport {
  const ValidationReport({required this.valid, this.issues = const []});

  final bool valid;
  final List<ValidationIssue> issues;

  factory ValidationReport.fromJson(Map<String, dynamic> json) =>
      ValidationReport(
        valid: json['valid'] as bool? ?? true,
        issues: json['issues'] is List
            ? (json['issues'] as List)
                .whereType<Map<String, dynamic>>()
                .map(ValidationIssue.fromJson)
                .toList()
            : const [],
      );
}

class ValidationIssue {
  const ValidationIssue({
    required this.level,
    required this.code,
    required this.message,
    this.field,
  });

  final String level; // "warning" | "error"
  final String code;
  final String message;
  final String? field;

  bool get isWarning => level == 'warning';

  factory ValidationIssue.fromJson(Map<String, dynamic> json) => ValidationIssue(
        level: json['level'] as String? ?? 'warning',
        code: json['code'] as String? ?? '',
        message: json['message'] as String? ?? '',
        field: json['field'] as String?,
      );
}