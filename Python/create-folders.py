"""Crea carpetas de colecciones y subcolecciones a partir de `collections.json`.

Requerimientos actuales:
 - El script y el JSON están en:  C:\\Users\\Tatooine\\Documents\\GitHub\\cloth_configurator\\Python
 - Debe crear las carpetas en:    C:\\Users\\Tatooine\\Documents\\GitHub\\cloth_configurator\\Content\\Texture\\MayerFabrics
 - Una carpeta por cada collection.
 - Dentro de cada collection, una carpeta por cada subcollection.
 - NO crear carpetas de variaciones.
 - Nombres: minúsculas, espacios -> '_', eliminar caracteres especiales (solo a-z 0-9 y _). Múltiples '_' se reducen.

Uso:
    python create-folders.py

Idempotente: no sobrescribe ni borra; solo crea lo que falta.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List


JSON_FILENAME = "collections.json"
DEST_DIR = Path(r"C:\Users\Tatooine\Documents\GitHub\cloth_configurator\Content\Texture\MayerFabrics")


def slugify(name: str) -> str:
    """Convierte un nombre en un nombre de carpeta válido.

    - Minúsculas
    - Espacios y separadores -> '_'
    - Solo deja a-z0-9 y '_'
    - Colapsa múltiples '_'
    - Quita '_' inicial/final
    """
    name = name.strip().lower()
    name = re.sub(r"[\s/\\]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip('_')
    return name or "unnamed"


def load_collections(json_path: Path) -> List[Dict[str, Any]]:
	if not json_path.exists():
		raise FileNotFoundError(f"No se encontró el archivo JSON en: {json_path}")
	with json_path.open("r", encoding="utf-8") as f:
		data = json.load(f)
	if not isinstance(data, list):  # Validación mínima
		raise ValueError("El JSON raíz debe ser una lista de colecciones")
	return data


def ensure_dir(path: Path) -> bool:
    """Crea el directorio si no existe. Retorna True si fue creado ahora.

    Incluye prints de depuración para diagnosticar problemas en Windows.
    """
    if path.exists():
        print(f"[DEBUG] Ya existe: {path}")
        return False
    try:
        print(f"[DEBUG] Intentando crear: {path}")
        path.mkdir(parents=True, exist_ok=True)
        # Verificación inmediata
        if path.exists():
            print(f"[DEBUG] Creado OK: {path}")
        else:
            print(f"[DEBUG][WARN] mkdir no lanzó error pero la carpeta no existe: {path}")
        return True
    except Exception as e:
        print(f"[ERROR] Falló crear '{path}': {e}")
        traceback.print_exc()
        return False


def create_structure(collections: List[Dict[str, Any]], dest: Path) -> Dict[str, int]:
    created_collections = 0
    existing_collections = 0
    created_subcollections = 0
    existing_subcollections = 0

    for idx, collection in enumerate(collections, start=1):
        print(f"[DEBUG] Procesando colección #{idx}: {collection.get('collection-name')}")
        col_name = collection.get("collection-name") or collection.get("name") or "collection"
        col_slug = slugify(col_name)
        col_path = dest / col_slug
        print(f"[DEBUG]  Nombre original: '{col_name}' -> slug: '{col_slug}'")
        if ensure_dir(col_path):
            created_collections += 1
            print(f"[CREADO] colección: {col_slug}")
        else:
            existing_collections += 1
            print(f"[EXISTE] colección: {col_slug}")

        subcollections = collection.get("subcollection") or []
        for sidx, sub in enumerate(subcollections, start=1):
            print(f"[DEBUG]    Subcolección #{sidx}: {sub.get('subcollection-name')}")
            sub_name = sub.get("subcollection-name") or sub.get("name") or "subcollection"
            sub_slug = slugify(sub_name)
            sub_path = col_path / sub_slug
            print(f"[DEBUG]      Nombre original: '{sub_name}' -> slug: '{sub_slug}'")
            if ensure_dir(sub_path):
                created_subcollections += 1
                print(f"  [CREADO] subcolección: {col_slug}/{sub_slug}")
            else:
                existing_subcollections += 1
                print(f"  [EXISTE] subcolección: {col_slug}/{sub_slug}")

    return {
        "created_collections": created_collections,
        "existing_collections": existing_collections,
        "created_subcollections": created_subcollections,
        "existing_subcollections": existing_subcollections,
    }


def main() -> None:
    json_path = Path(__file__).parent / JSON_FILENAME

    print(f"[DEBUG] Python executable : {sys.executable}")
    print(f"[DEBUG] Versión Python    : {sys.version}")
    print(f"[DEBUG] cwd (os.getcwd)   : {os.getcwd()}")
    print(f"[DEBUG] __file__          : {__file__}")
    print(f"[DEBUG] JSON esperado     : {json_path}")
    print(f"[DEBUG] Destino final     : {DEST_DIR}")
    print(f"[DEBUG] Existe destino?   : {DEST_DIR.exists()}")
    print(f"[DEBUG] Padre destino     : {DEST_DIR.parent}")
    print(f"[DEBUG] Padre existe?     : {DEST_DIR.parent.exists()}")
    print(f"[DEBUG] Permisos destino padre (lect/escr): R={os.access(DEST_DIR.parent, os.R_OK)} W={os.access(DEST_DIR.parent, os.W_OK)}")

    print("=====================================")
    print(" Creación de carpetas MayerFabrics ")
    print("=====================================")
    print(f"JSON origen : {json_path}")
    print(f"Destino     : {DEST_DIR}")
    print("(Solo colecciones y subcolecciones)")
    print("-------------------------------------")

    if not json_path.exists():
        print(f"[ERROR] No se encuentra el JSON en: {json_path}")
        print("[SUGERENCIA] Asegúrate de que 'collections.json' está en la carpeta Python junto al script.")
        return

    try:
        collections = load_collections(json_path)
        print(f"[DEBUG] Colecciones cargadas: {len(collections)}")
    except Exception as e:
        print(f"ERROR al leer JSON: {e}")
        traceback.print_exc()
        return

    print("[DEBUG] Creando (si falta) directorio destino raíz...")
    if ensure_dir(DEST_DIR):
        print("[DEBUG] Directorio destino recién creado.")
    else:
        print("[DEBUG] Directorio destino ya existía.")
    print(f"[DEBUG] Verificación post mkdir destino existe?: {DEST_DIR.exists()}")

    summary = create_structure(collections, DEST_DIR)

    print("-------------------------------------")
    print("Resumen:")
    print(f"  Colecciones creadas      : {summary['created_collections']}")
    print(f"  Colecciones existentes   : {summary['existing_collections']}")
    print(f"  Subcolecciones creadas   : {summary['created_subcollections']}")
    print(f"  Subcolecciones existentes: {summary['existing_subcollections']}")
    print("-------------------------------------")
    print("Finalizado.")


if __name__ == "__main__":
	main()

