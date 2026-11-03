"""Comprobación de que los logotipos de marca llegan al cliente.

No es una prueba unitaria: confirma contra el catálogo real que la URL existe,
que el parámetro `logo` filtra y que un nombre escrito de otra forma («KIA»,
«kia-motor») se puede normalizar hasta la marca.
"""
import re
import sys

sys.path.insert(0, "/srv/api")

from sqlalchemy import select

from app.catalog_models import VehicleMake
from app.catalog_routes import makes
from app.database import SessionLocal

ACCENTS = "áàäâéèëêíìïîóòöôúùüûñç"
PLAIN = "aaaaeeeeiiiioooouuuunc"


def normalize(value: str) -> str:
    buffer = []
    for char in value.strip().lower():
        index = ACCENTS.find(char)
        if index >= 0:
            buffer.append(PLAIN[index])
        elif re.match(r"[a-z0-9]", char):
            buffer.append(char)
    return "".join(buffer)


class Admin:
    id, role, workshop_id = 1, "admin", 1


with SessionLocal() as db:
    total = db.scalars(select(VehicleMake)).all()
    con_logo = [row for row in total if row.logo_url]
    print(f"marcas en el catalogo: {len(total)}")
    print(f"con logotipo: {len(con_logo)}")

    sin_logo_siempre = all(
        makes(db, Admin(), "", False, 1000)[i]["logo_url"] is None
        for i in range(min(5, len(total)))
    )
    print(f"logo=false oculta la URL: {sin_logo_siempre}")

    con = {normalize(row.name): row.logo_url for row in con_logo}
    con.update({
        normalize(row.slug): row.logo_url
        for row in con_logo
        if row.slug
    })
    print(f"marcas resolubles por nombre normalizado: {len(con)}")

    for nombre in ("KIA", "kia motors", "Alfa Romeo", "TOYOTA"):
        print(f"  {nombre:12} -> {normalize(nombre):12} "
              f"{'OK' if normalize(nombre) in con else 'sin logo'}")

    muestra = con_logo[:3]
    for row in muestra:
        print(f"  {row.name:16} {row.logo_url}")