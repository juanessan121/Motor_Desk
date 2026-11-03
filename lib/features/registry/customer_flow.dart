import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/state/workshop_controller.dart';

import '../orders/orders_page.dart';
import 'registry_forms.dart';

/// Cada paso se abre solamente después de guardar y cerrar el anterior.
/// Cancelar conserva los registros ya guardados y detiene la secuencia.
Future<void> startCustomerFlow(BuildContext context) async {
  final customerId = await editCustomer(context, null, true);
  if (!context.mounted || customerId == null) return;
  await startVehicleFlow(context, ownerId: customerId);
}

Future<void> startVehicleFlow(BuildContext context, {int? ownerId}) async {
  if (context.read<WorkshopController>().customers.isEmpty) {
    await startCustomerFlow(context);
    return;
  }
  final vehicleId = await editVehicle(context, null, ownerId, true);
  if (!context.mounted || vehicleId == null) return;
  await createOrder(context, vehicleId: vehicleId);
}
