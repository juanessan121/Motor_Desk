import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/atelier_tokens.dart';
import '../../core/models/entities.dart';
import '../../core/state/make_logo_cache.dart';
import '../../core/state/workshop_controller.dart';
import '../../shared/atelier_controls.dart';
import '../../shared/widgets.dart';
import '../registry/registry_forms.dart';
import 'vehicle_passport.dart';

class VehicleGarageCard extends StatelessWidget {
  const VehicleGarageCard({super.key, required this.vehicle});
  final Vehicle vehicle;
  @override
  Widget build(BuildContext context) {
    final state = context.watch<WorkshopController>();
    final current = state.orders
        .where(
          (order) => order.json['vehicle_id'] == vehicle.id && !order.closed,
        )
        .firstOrNull;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () => openPassport(context, vehicle.id),
            child: Container(
              height: 140,
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              // El fondo del visor es un token del tema, no un literal: con un
              // tema claro la tarjeta salía como un rectángulo negro.
              color: context.atelier.diagnostic,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: Image.asset(
                      'assets/visual/vehiculo_lateral.png',
                      fit: BoxFit.contain,
                    ),
                  ),
                  // El logotipo de la marca va encima del vehículo: identifica
                  // de un vistazo lo que el nombre no distingue a distancia.
                  Positioned(
                    top: 0,
                    right: 0,
                    child: MakeLogo(
                      make: vehicle.json['brand'] as String?,
                      logoUrl:
                          (vehicle.json['catalog'] as Map?)?['logo_url']
                              as String?,
                      loadCatalog: !state.isCustomer,
                      size: 30,
                      radius: 8,
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(19),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  vehicle.name,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        vehicle.plate,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          letterSpacing: .7,
                        ),
                      ),
                    ),
                    Text('${vehicle.json['year']}'),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  '${vehicle.json['mileage']} km registrados',
                  style: const TextStyle(fontSize: 12),
                ),
                if (!state.isMechanic) ...[
                  const SizedBox(height: 7),
                  Text(
                    vehicle.ownerName,
                    style: const TextStyle(fontSize: 12),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 13),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    if (!vehicle.active)
                      const AtelierBadge('Archivado')
                    else if (current != null)
                      StatusChip(current.status)
                    else
                      const AtelierBadge('Sin orden visible activa'),
                    const AtelierBadge('Sin diagnóstico inferido'),
                  ],
                ),
                const SizedBox(height: 15),
                // El color literal se queda ilegible en los temas oscuros: el texto de
                // alcance se pinta con el token secundario.
                Text(
                  'Silueta ilustrativa · No es una foto del modelo',
                  style: TextStyle(
                    fontSize: 10,
                    color: context.atelier.secondaryText,
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: AtelierAction(
                        label: 'Expediente',
                        icon: Icons.badge_outlined,
                        family: AtelierButton.secondary,
                        expand: true,
                        compact: true,
                        onPressed: () => openPassport(context, vehicle.id),
                      ),
                    ),
                    if (state.isAdmin)
                      IconButton(
                        tooltip: 'Editar vehículo',
                        onPressed: () => editVehicle(context, vehicle),
                        icon: const Icon(Icons.edit_outlined, size: 19),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
