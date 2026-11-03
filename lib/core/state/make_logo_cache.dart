import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../network/api_client.dart';

/// Resuelve el logotipo de una marca del catálogo a partir de su nombre.
///
/// El catálogo trae 140 logotipos (Entrega 2) y la interfaz no usaba ninguno:
/// todas las tarjetas pintaban la misma silueta genérica, de modo que un
/// Hyundai y un Toyota se confundían en la pantalla.
///
/// El nombre que el taller escribió en el vehículo es texto libre
/// («Chevrolet», «chevrolet», «CHEVROLET»), así que la búsqueda es
/// insensible a mayúsculas y por prefijo. Se pide el catálogo una sola vez y
/// se cachea en memoria; el mapa es pequeño (164 marcas) y no cabe en el
/// almacenamiento local porque caduca con cada importación.
class MakeLogoCache extends ChangeNotifier {
  MakeLogoCache(this.api);

  final ApiClient api;

  Map<String, String>? _bySlug;
  bool _loading = false;

  /// Nombres normalizados por los que no se encontró logotipo. Cacheado para
  /// no reintentar la búsqueda en cada reconstrucción de tarjeta.
  final Set<String> _missing = {};

  bool get loading => _loading;
  bool get loaded => _bySlug != null;

  /// Longitud mínima a la que se admite una coincidencia por prefijo.
  ///
  /// Con tres letras o menos el riesgo de confundir marcas es real: «MG» puede
  /// emparejar con lo que sea y «FI» no significa nada.
  static const _minPrefix = 3;

  /// Logotipo de una marca, o `null` si el catálogo no tiene ninguno o todavía
  /// no se ha cargado. Nunca lanza: la ausencia de un logo no puede romper una
  /// pantalla.
  String? logoFor(String? make) {
    final key = normalize(make ?? '');
    if (key.isEmpty) return null;
    final byName = _bySlug;
    if (byName == null) {
      // No se ha cargado todavía: se pide una vez y el resultado se pinta en
      // el siguiente fotograma.
      if (!_loading) unawaited(load());
      return null;
    }
    // Una marca que no tiene logo no se busca otra vez.
    if (_missing.contains(key)) return null;
    final exacto = byName[key];
    if (exacto != null) return exacto;
    final prefijo = _porPrefijo(key, byName);
    if (prefijo != null) return prefijo;
    _missing.add(key);
    return null;
  }

  /// Busca una marca acortando **la consulta**, nunca alargando el catálogo.
  ///
  /// El taller escribe «Kia Motors», «Toyota Corolla» o «Chevrolet Sail» en el
  /// campo de marca, y el catálogo solo tiene «Kia», «Toyota», «Chevrolet».
  ///
  /// Acortar la consulta es la dirección segura: solo se acepta si el
  /// catálogo tiene **literalmente** esa clave más corta. Al revés —buscar una
  /// marca del catálogo que empiece por la consulta— «MG» emparejaría con
  /// cualquier cosa que empiece por mg.
  String? _porPrefijo(String key, Map<String, String> catalogo) {
    for (var largo = key.length - 1; largo >= _minPrefix; largo--) {
      final candidato = key.substring(0, largo);
      final encontrado = catalogo[candidato];
      if (encontrado != null) return encontrado;
    }
    return null;
  }

  /// Descarga el catálogo de marcas. Si el usuario no tiene acceso —un
  /// cliente no puede consultar el catálogo— se marca como no disponible y la
  /// interfaz sigue con la silueta, que es lo que ya hacía antes.
  Future<void> load() async {
    if (_loading) return;
    _loading = true;
    notifyListeners();
    try {
      final result = await api.request(
        'GET',
        '/catalog/makes?logo=true&limit=1000',
      );
      final rows = result is List ? result : <dynamic>[];
      final map = <String, String>{};
      for (final row in rows) {
        if (row is! Map) continue;
        final url = row['logo_url'];
        final name = row['name'];
        if (url is String && url.isNotEmpty && name is String) {
          // Se registra por nombre y por slug: el vehículo puede traer
          // cualquiera de las dos formas.
          map[normalize(name)] = url;
          final slug = row['slug'];
          if (slug is String) map[normalize(slug)] = url;
        }
      }
      _bySlug = map;
      _missing.clear();
    } catch (_) {
      // Sin acceso al catálogo, o sin red. No se reintenta en bucle: se marca
      // como vacío para que las tarjetas dejen de pedirlo.
      _bySlug = const {};
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  /// Forget cache. Se llama al recargar datos del taller.
  void invalidate() {
    _bySlug = null;
    _missing.clear();
  }

  static String normalize(String value) {
    final trimmed = value.trim().toLowerCase();
    if (trimmed.isEmpty) return '';
    // Se quitan tildes y separadores: «Kia Motors» y «kia-motors» son la misma
    // marca a ojos del taller.
    const accents = 'áàäâéèëêíìïîóòöôúùüûñç';
    const plain = 'aaaaeeeeiiiioooouuuunc';
    final buffer = StringBuffer();
    for (final rune in trimmed.runes) {
      final char = String.fromCharCode(rune);
      final index = accents.indexOf(char);
      if (index >= 0) {
        buffer.write(plain[index]);
      } else if (RegExp(r'[a-z0-9]').hasMatch(char)) {
        buffer.write(char);
      }
      // Cualquier separador se descarta: 'Hyundai-Kia' se reduce a 'hyundaikia'
      // y no encuentra nada, pero 'Kia Motor' sí se empareja con 'Kia'.
    }
    return buffer.toString();
  }
}

/// Logotipo de marca con reserva.
///
/// Nunca lanza ni queda en blanco: mientras carga o si el catálogo no tiene
/// ese logo, se dibuja la marca escrita. Una tarjeta con el nombre siempre se
/// lee, aunque el catálogo no esté disponible.
class MakeLogo extends StatelessWidget {
  const MakeLogo({
    super.key,
    required this.make,
    this.size = 42,
    this.radius = 11,
    this.logoUrl,
    this.loadCatalog = true,
  });

  final String? make;
  final double size;
  final double radius;

  /// URL recibida con el vehículo autorizado, sin descargar el catálogo global.
  final String? logoUrl;
  final bool loadCatalog;

  @override
  Widget build(BuildContext context) {
    if (logoUrl != null && Uri.tryParse(logoUrl!)?.scheme == 'https') {
      return _makeImage(context, make, size, radius, logoUrl!);
    }
    if (!loadCatalog) return _makeInitials(context, make, size, radius);
    // La tarjeta también se renderiza en pruebas y en vistas previas que no
    // montan la aplicación completa. Sin caché debe mostrar la marca escrita,
    // no romper la pantalla.
    final cache = _lookup(context);
    if (cache == null) return _makeInitials(context, make, size, radius);
    // La suscripción va en el hijo: `maybeOf` lee sin escuchar, y sin
    // suscripción las tarjetas en reserva no se repintarían al llegar los
    // logotipos del catálogo.
    return _MakeLogoBody(cache: cache, make: make, size: size, radius: radius);
  }

  /// Busca la caché sin dejar que su ausencia rompa la pantalla.
  ///
  /// La tarjeta se renderiza también en pruebas y en vistas previas que no
  /// montan la aplicación completa. `Provider.of` lanzaría ahí, y una pantalla
  /// entera no puede caerse por un logotipo.
  static MakeLogoCache? _lookup(BuildContext context) {
    try {
      return Provider.of<MakeLogoCache>(context, listen: false);
    } on ProviderNotFoundException {
      return null;
    }
  }
}

/// Casilla con las iniciales de la marca.
///
/// Se usa siempre que no haya logotipo: mientras carga, si el catálogo no
/// tiene ese logo o si la cuenta no puede consultar el catálogo. Una tarjeta
/// con el nombre siempre se lee.
Widget _makeInitials(
  BuildContext context,
  String? make,
  double size,
  double radius,
) {
  final name = (make ?? '').trim();
  final initials = name.isEmpty
      ? '·'
      : name
            .split(RegExp(r'[\s-]+'))
            .where((part) => part.isNotEmpty)
            .take(2)
            .map((part) => part[0].toUpperCase())
            .join();
  final palette = Theme.of(context).colorScheme;
  return Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      color: palette.primary.withValues(alpha: .1),
      borderRadius: BorderRadius.circular(radius),
    ),
    alignment: Alignment.center,
    child: Text(
      initials,
      style: TextStyle(
        fontSize: size * .34,
        fontWeight: FontWeight.w700,
        color: palette.primary,
      ),
    ),
  );
}

/// Cuerpo de [MakeLogo] que sí se suscribe a la caché.
///
/// Separado a propósito: `maybeOf` lee sin escuchar, de modo que la versión
/// que devuelve `null` no puede reconstruirse sola y la que sí tiene la caché
/// necesita `select`.
class _MakeLogoBody extends StatelessWidget {
  const _MakeLogoBody({
    required this.cache,
    required this.make,
    required this.size,
    required this.radius,
  });

  final MakeLogoCache cache;
  final String? make;
  final double size;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final url = context.select<MakeLogoCache, String?>(
      (cache) => cache.logoFor(make),
    );
    if (url == null) return _makeInitials(context, make, size, radius);
    return _makeImage(context, make, size, radius, url);
  }
}

Widget _makeImage(
  BuildContext context,
  String? make,
  double size,
  double radius,
  String url,
) {
  final fallback = _makeInitials(context, make, size, radius);
  return SizedBox(
    width: size,
    height: size,
    child: ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: Padding(
        padding: EdgeInsets.all(size * .16),
        child: Image.network(
          url,
          width: size,
          height: size,
          fit: BoxFit.contain,
          errorBuilder: (_, _, _) => fallback,
          // Mientras baja la imagen se ve la marca escrita, no un hueco.
          loadingBuilder: (context, child, progress) =>
              progress == null ? child : fallback,
        ),
      ),
    ),
  );
}

/// Marca un `Future` como intencionadamente no esperado.
///
/// `unawaited` existe en `dart:async`, pero aquí se reimplementa para que el
/// error de una carga fallida no quede como «unhandled exception» en la
/// consola cuando el usuario no tiene acceso al catálogo.
void unawaited(Future<void> future) {
  future.catchError((_) {});
}
