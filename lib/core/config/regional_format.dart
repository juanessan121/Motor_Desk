import 'package:intl/intl.dart';

/// Formato de presentación, sin convertir valores técnicos ni depender de la
/// zona del ordenador. Ecuador continental usa UTC-5; Galápagos usa UTC-6.
class RegionalFormat {
  const RegionalFormat([this.regional = const {}]);
  final Map<String, dynamic> regional;

  String get timezone => regional['timezone'] as String? ?? 'America/Guayaquil';
  String get locale => (regional['locale'] as String? ?? 'es-EC').replaceAll('-', '_');
  int get _offset => switch (timezone) {
    'America/Guayaquil' => -300,
    'Pacific/Galapagos' => -360,
    _ => 0,
  };
  String get timezoneLabel => switch (timezone) {
    'America/Guayaquil' => 'Ecuador continental · UTC−5',
    'Pacific/Galapagos' => 'Galápagos · UTC−6',
    _ => 'UTC',
  };

  DateTime? _date(dynamic value) {
    if (value == null) return null;
    if (value is DateTime) return value.toUtc().add(Duration(minutes: _offset));
    final text = value.toString();
    final parsed = DateTime.tryParse(text);
    if (parsed == null) return null;
    // Una fecha sin hora es una fecha de calendario, no un instante UTC.
    if (RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) return parsed;
    final utc = parsed.isUtc ? parsed : DateTime.utc(parsed.year, parsed.month,
        parsed.day, parsed.hour, parsed.minute, parsed.second, parsed.millisecond);
    return utc.add(Duration(minutes: _offset));
  }

  String date(dynamic value) {
    final date = _date(value);
    if (date == null) return '—';
    return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
  }

  String dateTime(dynamic value) {
    final date = _date(value);
    if (date == null) return '—';
    return '${this.date(value)} · ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
  }

  String money(dynamic value) {
    final parsed = num.tryParse(value?.toString() ?? '');
    if (parsed == null || !parsed.isFinite) return '—';
    final currency = regional['currency'] as String? ?? 'USD';
    final symbol = regional['currency_symbol'] as String? ?? r'$';
    return NumberFormat.currency(locale: locale, name: currency, symbol: symbol,
        decimalDigits: 2).format(parsed);
  }

  String distance(dynamic value) {
    final parsed = num.tryParse(value?.toString() ?? '');
    if (parsed == null || !parsed.isFinite || parsed < 0) return '—';
    return '${NumberFormat.decimalPattern(locale).format(parsed)} km';
  }
}
