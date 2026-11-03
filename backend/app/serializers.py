from decimal import Decimal


def user_json(user):
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role, "workshop_id": user.workshop_id, "must_change_password": user.must_change_password}


def customer_access_status(customer):
    if not customer.user_id or not customer.user:
        return 'sin_cuenta'
    if not customer.user.active:
        return 'deshabilitado'
    if customer.user.must_change_password or not customer.user.password_hash:
        return 'pendiente_activacion'
    return 'activo'


def customer_json(customer):
    status = customer_access_status(customer)
    return {
        **{key: getattr(customer, key) for key in (
            "id", "user_id", "national_id", "first_name", "last_name", "address", "phone",
            "whatsapp", "email", "telegram_chat_id", "notification_channel",
            "notifications_enabled", "email_notifications_enabled",
            "telegram_notifications_enabled", "whatsapp_notifications_enabled", "active",
        )},
        "full_name": customer.full_name,
        "username": customer.user.username if customer.user else "",
        "access_status": status,
        "has_account": customer.user_id is not None,
        "access_pending": status == 'pendiente_activacion',
    }


def vehicle_json(vehicle, *, user=None):
    # El VIN identifica el vehículo también fuera del taller: se reserva al administrador.
    result = {
        **{key: getattr(vehicle, key) for key in ("id", "owner_id", "plate", "brand", "model", "year", "color", "fuel_type", "mileage", "active")},
        "vin": vehicle.vin,
        "owner_name": vehicle.owner.full_name if user is None or user.role != "mechanic" else None,
        "template_id": vehicle.template_id,
        "catalog": vehicle.catalog_ref(),
    }
    if user is not None and user.role == "mechanic":
        result["vin"] = None
    return result


def activity_json(activity):
    return {
        "id": activity.id,
        "workshop_id": activity.workshop_id,
        "name": activity.label,
        "label": activity.label,
        "normalized_label": activity.normalized_label,
        "description": activity.description,
        "system": activity.system,
        "technical_notes": activity.technical_notes,
        "required": activity.required,
        "estimated_minutes": activity.estimated_minutes,
        "suggested_part_ids": activity.suggested_part_ids,
        "active": activity.active,
        "revision": activity.revision,
    }


def catalog_json(catalog):
    from .maintenance_service import snapshot
    return {
        **snapshot(catalog),
        "id": catalog.id, "name": catalog.name, "description": catalog.description,
        "base_price": str(catalog.base_price), "active": catalog.active,
        "tasks": [task.label for task in catalog.tasks],
        'task_details': snapshot(catalog)['tasks'],
    }


def order_total(order):
    from .pricing import amounts
    return amounts(order)[-1]


def order_json(order, *, show_quotes=True, show_photos=True, db=None, user=None):
    from .access_policy import assignment, photo_allowed, task_ids
    from .maintenance_service import progress, stage, task_status
    mechanic = user is not None and user.role == "mechanic"
    allowed = task_ids(db, order, user) if mechanic else {item.id for item in order.items}
    items = [item for item in order.items if item.id in allowed]
    grant = assignment(db, order.id, user) if mechanic else None
    from .pricing import amounts
    labor, parts, subtotal, tax_rate, tax_amount, total_amount = amounts(order)
    order_code = getattr(order, 'order_code', None) or f"OT-{order.created_at.year}-{order.id:04d}"
    result = {
        "id": order.id, "vehicle_id": order.vehicle_id, "customer_id": order.customer_id,
        "order_code": order_code,
        "maintenance_type": getattr(order, 'maintenance_type', 'preventivo') or 'preventivo',
        "plate": order.vehicle.plate, "vehicle_name": f"{order.vehicle.brand} {order.vehicle.model}",
        "customer_name": order.payer_snapshot["name"], "payer_snapshot": order.payer_snapshot,
        "title": order.title, "status": order.status,
        'operational_stage': stage(order), 'priority': order.priority,
        'revision': order.revision, 'intake_mileage': order.intake_mileage,
        'problem_description': getattr(order, 'problem_description', '') or '',
        'technical_diagnosis': getattr(order, 'technical_diagnosis', '') or '',
        'delay_reason': getattr(order, 'delay_reason', None),
        'estimated_delivery_date': order.estimated_delivery_date.isoformat() if getattr(order, 'estimated_delivery_date', None) else None,
        'delivered_at': order.delivered_at.isoformat() if getattr(order, 'delivered_at', None) else None,
        'symptoms': order.symptoms if user is None or user.role != 'customer' else '',
        'review_required': order.review_required,
        'execution_reviewed': order.execution_reviewed_at is not None,
        'templates': ([{'id': ref['id'], 'revision': ref['revision'], 'name': ref['name']} for ref in order.template_snapshot or []] if user is not None and user.role != 'admin' else order.template_snapshot),
        'historical_template_available': order.template_snapshot is not None,
        "notes": order.notes if user is None or user.role != 'customer' or order.notes_published else '',
        "notes_published": order.notes_published,
        "base_total": str(order.base_total),
        "labor_cost": str(labor),
        "parts_cost": str(parts),
        "tax_rate": str(tax_rate),
        "tax_amount": str(tax_amount),
        "total_amount": str(total_amount),
        "cost_status": "final" if order.status == "delivered" else "estimate",
        "total": str(order_total(order)),
        "created_at": order.created_at.isoformat(),
        "progress": progress(items),
        "items": [{"id": item.id, "label": item.label, "completed": item.completed, 'status': task_status(item),
                   'description': item.description if user is None or user.role != 'customer' else '',
                   'revision': item.revision, 'required': item.required, 'estimated_minutes': item.estimated_minutes,
                   'notes': item.notes if user is None or user.role != 'customer' else '',
                   'suggested_part_ids': item.suggested_part_ids if user is None or user.role != 'customer' else [],
                   'responsible_ids': [grant.mechanic_id for grant in order.assignments if grant.revoked_at is None and item.id in grant.task_ids and (not mechanic or grant.mechanic_id == user.id)],
                   'completed_by': item.completed_by if user is None or user.role != 'customer' else None,
                   "completed_at": item.completed_at.isoformat() if item.completed_at else None} for item in items],
        "base_approval": order.base_approval,
        "can_record_approval": bool(user is not None and user.role == 'admin' and order.customer.user_id is None and order.base_approval == 'pending'),
        "capabilities": {"manage": not mechanic and (user is None or user.role == "admin"),
            "assign": user is None or user.role == "admin", "inspect": user is None or user.role != "customer",
            "upload": user is None or user.role != "customer", "quote": bool(grant.can_quote) if mechanic else user is None or user.role == "admin"},
        "quotes": [{
            "id": quote.id, "title": quote.title, "decision": quote.decision,
            "selected_option_id": quote.selected_option_id,
            "options": [{"id": option.id, "label": option.label, "price": str(option.price)} for option in quote.options],
        } for quote in order.quotes if not mechanic or (grant.can_quote and quote.task_id in allowed)] if show_quotes else [],
        "photos": [{"id": photo.id, "caption": photo.caption, "published": photo.published_at is not None,
            "task_id": photo.task_id, "inspection_id": photo.inspection_id, "finding_id": photo.finding_id,
            "created_at": photo.created_at.isoformat()} for photo in order.photos
            if user is None or photo_allowed(db, photo, order, user)] if show_photos else [],
    }
    if mechanic:
        # `customer_id` reconcilia al mecánico con la ficha de cliente, que es solo de administración.
        for key in ("payer_snapshot", "base_total", "total", "labor_cost", "parts_cost", "tax_amount", "total_amount", "notes", "customer_id"):
            result.pop(key, None)
        result["customer_name"] = None
    return result
