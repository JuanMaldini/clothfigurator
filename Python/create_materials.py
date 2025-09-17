import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------- Config ----------------
# Padres en Unreal
PARENT_MATERIAL_OBJECT_PATH = "/Game/Materials/MI_Sample.MI_Sample"

# Bases de rutas
BASE_ASSET_ROOT = "/Game/Materials"

# Carpeta del fabricante dentro de Materials
MANUFACTURER_FOLDER = "MayerFabrics"

# Candidatos iniciales de ubicación del JSON (rutas absolutas opcionales).
# Mantenemos la variable para permitir añadir rutas manuales si se desea.
JSON = [
    # Agrega aquí rutas absolutas específicas si quieres forzar una ubicación.
    # Ejemplo: r"D:\\GitHub\\cloth_configurator\\Python\\collections.json"
]


# ---------------- Utilidades de sanitización ----------------
def strip_accents(text: str) -> str:
    """Elimina acentos/diacríticos para quedarnos con ASCII plano."""
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def sanitize_token(text: str) -> str:
    """Normaliza un token para NOMBRE de MI:
    - Reemplaza espacios por '-'
    - Elimina caracteres especiales (solo A-Z, 0-9, '-')
    - Colapsa guiones repetidos y recorta en extremos
    - Convierte a MAYÚSCULAS
    """
    if text is None:
        return ''
    text = strip_accents(str(text)).strip()
    text = text.replace(' ', '-')
    text = re.sub(r'[^A-Za-z0-9-]', '', text)
    text = re.sub(r'-{2,}', '-', text)
    text = text.strip('-')
    return text.upper()


INVALID_WIN = r'[<>:"/\\|?*]'


def sanitize_folder(name: str) -> str:
    """Sanitiza nombres de carpetas estilo Windows-safe (similar a Folders.py):
    - Reemplaza caracteres inválidos por '_'
    - Colapsa múltiples espacios
    - Quita punto/espacio al final
    - Mantiene espacios (no los convierte a '-')
    """
    s = re.sub(INVALID_WIN, "_", str(name).strip())
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(". ")
    return s if s else "_"


# ---------------- Core ----------------
# Adaptadores de JSON (compatibilidad hacia atrás)
def _get_collection_name(coll: Dict[str, Any]) -> str:
    # Nuevo: "collection-name" | Antiguo: "collection"
    return (coll.get("collection-name") or coll.get("collection") or "").strip()


def _get_subcollection_list(coll: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Ambos usan "subcollection" como lista (si no existe, []):
    subs = coll.get("subcollection")
    return subs or []


def _get_subcollection_name(sub: Dict[str, Any]) -> str:
    # Nuevo: "subcollection-name" | Antiguo: "name"
    return (sub.get("subcollection-name") or sub.get("name") or "").strip()


def _get_variations_list(sub: Dict[str, Any]) -> List[Any]:
    # Nuevo: "variations" (lista de dicts) | Antiguo: "variation" (lista de strings)
    v = sub.get("variations")
    if v is None:
        v = sub.get("variation")
    return v or []


def _get_variation_label(variation_item: Any) -> str:
    # Nuevo: dict => queremos "{variation-name}-{variation-pattern}" si ambos existen
    # Fallback: solo uno de ellos; Antiguo: string
    if isinstance(variation_item, dict):
        vname = (variation_item.get("variation-name") or "").strip()
        vpat = (variation_item.get("variation-pattern") or "").strip()
        if vname and vpat:
            return f"{vname}-{vpat}"
        return vname or vpat or ""
    return str(variation_item).strip()


def find_json_file(cli_path: Optional[str]) -> Path:
    """Localiza el archivo JSON de colecciones.

    Prioridad de búsqueda:
      1. Ruta proporcionada por CLI (--json)
      2. Variable de entorno COLLECTIONS_JSON
      3. Lista JSON (rutas absolutas definidas arriba)
      4. Misma carpeta del script (collections.json / okcollections.json)
      5. Directorios ascendentes (hasta 4 niveles) buscando 'Python/collections.json' o 'collections.json'
    """
    candidates: List[Path] = []

    # 1. CLI
    if cli_path:
        p = Path(cli_path).expanduser().resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"No existe JSON en ruta proporcionada: {cli_path}")

    # 2. Variable de entorno
    env_path = os.environ.get("COLLECTIONS_JSON")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        candidates.append(p)

    # 3. Lista manual JSON
    for c in JSON:
        try:
            candidates.append(Path(c).expanduser().resolve())
        except Exception:
            pass

    # 4. Misma carpeta del script
    script_dir = Path(__file__).parent.resolve()
    candidates.append(script_dir / 'collections.json')
    candidates.append(script_dir / 'okcollections.json')

    # 5. Ascender buscando
    current = script_dir
    for _ in range(4):  # subir hasta 4 niveles por seguridad
        # a) <nivel>/Python/collections.json (si estamos fuera de Python)
        python_variant = current / 'Python' / 'collections.json'
        candidates.append(python_variant)
        candidates.append(current / 'collections.json')
        candidates.append(current / 'okcollections.json')
        current = current.parent

    # Filtrar duplicados preservando orden
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    for cand in unique_candidates:
        if cand.exists():
            print(f"[find_json_file] Usando JSON: {cand}")
            return cand

    # Mensaje de depuración para ayudar
    debug_list = "\n".join(str(c) for c in unique_candidates)
    raise FileNotFoundError(
        "No se encontró 'collections.json' en rutas conocidas. Usa --json <ruta> o define COLLECTIONS_JSON.\n"
        f"Candidatos probados:\n{debug_list}"
    )


def resolve_roots(json_file: Path) -> Dict[str, Path | str]:
    # Proyecto = carpeta padre de la carpeta que contiene collections.json (asumiendo estructura del repo)
    # Si el JSON está en .../Python/collections.json => project_root = .../ (padre de Python)
    # Si está en .../collections.json => project_root = .../
    project_root = json_file.parent
    if project_root.name.lower() == 'python':
        project_root = project_root.parent
    base_fs_root = project_root / 'Content' / 'Materials'
    base_fs_root_vendor = base_fs_root / MANUFACTURER_FOLDER
    base_asset_root_vendor = f"{BASE_ASSET_ROOT}/{MANUFACTURER_FOLDER}"
    return {
        'project_root': project_root,
        'base_fs_root': base_fs_root,
        'base_fs_root_vendor': base_fs_root_vendor,
        'base_asset_root': BASE_ASSET_ROOT,
        'base_asset_root_vendor': base_asset_root_vendor,
    }


def build_material_specs(data, base_fs_root_vendor: Path, base_asset_root_vendor: str) -> List[Dict[str, Any]]:
    """Devuelve objetos con name + rutas (asset, object, filesystem).
    Compatible con JSON antiguo y nuevo.
    """
    specs: List[Dict[str, Any]] = []
    for coll in data or []:
        coll_raw = _get_collection_name(coll)
        if not coll_raw:
            continue
        coll_folder = sanitize_folder(coll_raw)
        sub_list = _get_subcollection_list(coll)
        for sub in sub_list:
            sub_raw = _get_subcollection_name(sub)
            if not sub_raw:
                continue
            sub_folder = sanitize_folder(sub_raw)
            for var in _get_variations_list(sub):
                var_raw = _get_variation_label(var)
                coll_tok = sanitize_token(coll_raw)
                sub_tok = sanitize_token(sub_raw)
                var_tok = sanitize_token(var_raw)
                if not (coll_tok and sub_tok and var_tok):
                    # Saltar entradas incompletas para evitar nombres inválidos
                    continue
                name = f"MI_{coll_tok}_{sub_tok}_{var_tok}"
                folder_rel = f"{coll_folder}/{sub_folder}" if sub_folder else coll_folder
                package_path = f"{base_asset_root_vendor}/{folder_rel}" if folder_rel else base_asset_root_vendor
                asset_path = f"{package_path}/{name}"
                object_path = f"{asset_path}.{name}"
                fs_path = (base_fs_root_vendor / coll_folder / sub_folder / f"{name}.uasset").resolve()
                specs.append({
                    'name': name,
                    'package_path': package_path,
                    'asset_path': asset_path,
                    'object_path': object_path,
                    'filesystem_path': str(fs_path),
                    'parent': PARENT_MATERIAL_OBJECT_PATH,
                })
    return specs


def create_folders_from_json(data) -> None:
    """Crea carpetas en el Content Browser según JSON bajo /Game/Materials/<MANUFACTURER>.
    Si ya existen, hace skip. Solo funciona dentro de Unreal.
    """
    try:
        import unreal  # type: ignore
    except Exception as e:
        # Fuera de Unreal: no hacemos nada
        return

    roots = []
    base_pkg_root = f"{BASE_ASSET_ROOT}/{MANUFACTURER_FOLDER}"
    # Asegura carpeta del fabricante
    if not unreal.EditorAssetLibrary.does_directory_exist(base_pkg_root):
        unreal.EditorAssetLibrary.make_directory(base_pkg_root)
        unreal.log(f"Creada carpeta fabricante: {base_pkg_root}")

    for coll in data or []:
        coll_name = _get_collection_name(coll)
        if not coll_name:
            continue
        coll_pkg = f"{base_pkg_root}/{sanitize_folder(coll_name)}"
        if not unreal.EditorAssetLibrary.does_directory_exist(coll_pkg):
            unreal.EditorAssetLibrary.make_directory(coll_pkg)
            unreal.log(f"Creada carpeta colección: {coll_pkg}")
        for sub in _get_subcollection_list(coll):
            sub_name = _get_subcollection_name(sub)
            if not sub_name:
                continue
            sub_pkg = f"{coll_pkg}/{sanitize_folder(sub_name)}"
            if not unreal.EditorAssetLibrary.does_directory_exist(sub_pkg):
                unreal.EditorAssetLibrary.make_directory(sub_pkg)
                unreal.log(f"  Creada subcarpeta: {sub_pkg}")


def create_material_instances(specs: List[Dict[str, Any]], dry_run: bool = False) -> None:
    """Crea MaterialInstanceConstant en Unreal según specs. Requiere entorno Unreal."""
    try:
        import unreal  # type: ignore
    except Exception as e:
        raise RuntimeError("El módulo 'unreal' no está disponible. Ejecuta dentro del Editor de Unreal.") from e

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialInstanceConstantFactoryNew()
    parent_asset = unreal.load_asset(PARENT_MATERIAL_OBJECT_PATH)
    if not parent_asset:
        raise RuntimeError(f"No se pudo cargar el parent: {PARENT_MATERIAL_OBJECT_PATH}")
    # Establece el parent directamente en la factory (algunas versiones lo requieren para setear en creación)
    try:
        factory.set_editor_property('initial_parent', parent_asset)
    except Exception:
        try:
            factory.initial_parent = parent_asset  # fallback
        except Exception:
            pass

    for spec in specs:
        name = spec['name']
        package_path = spec['package_path']
        asset_path = spec['asset_path']
        object_path = spec['object_path']

        if dry_run:
            unreal.log(f"[DRY] Crear MI: {object_path}  (parent: {PARENT_MATERIAL_OBJECT_PATH})")
            continue

        # Asegura el directorio en el Content Browser
        unreal.EditorAssetLibrary.make_directory(package_path)

        # Si ya existe, cargar y actualizar parent si hace falta
        if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
            existing = unreal.EditorAssetLibrary.load_asset(asset_path)
            if existing:
                try:
                    existing.set_editor_property('parent', parent_asset)
                except Exception:
                    try:
                        existing.parent = parent_asset
                    except Exception:
                        unreal.log_warning(f"No se pudo asignar el parent a existente: {object_path}")
                unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
                unreal.log(f"Actualizado parent: {object_path}")
                continue

        # Crea el asset (parent establecido en factory)
        new_asset = asset_tools.create_asset(
            asset_name=name,
            package_path=package_path,
            asset_class=unreal.MaterialInstanceConstant,
            factory=factory,
        )

        if not new_asset:
            unreal.log_warning(f"No se pudo crear el MI: {object_path}")
            continue

        # Asigna parent
        try:
            new_asset.set_editor_property('parent', parent_asset)
        except Exception:
            # Fallback para versiones antiguas
            try:
                new_asset.parent = parent_asset
            except Exception:
                unreal.log_warning(f"No se pudo asignar el parent a: {object_path}")

        # Guarda el asset
        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        unreal.log(f"Creado: {object_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera nombres MI + rutas; opcionalmente crea los assets en Unreal.")
    parser.add_argument('--json', dest='json_path', help='Ruta a collections.json (opcional)')
    parser.add_argument('--create', action='store_true', help='Crear Material Instances en Unreal (por defecto solo imprime).')
    parser.add_argument('--dry-run', action='store_true', help='Con --create, solo mostrar acciones sin crear.')
    args = parser.parse_args()

    json_file = find_json_file(args.json_path)
    roots = resolve_roots(json_file)

    print("Starting material spec generation (names + paths)...")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    specs = build_material_specs(data, roots['base_fs_root_vendor'], roots['base_asset_root_vendor'])

    # Siempre imprimimos el super array para validar
    print(json.dumps(specs, indent=2, ensure_ascii=False))

    # Si estamos dentro de Unreal, crear por defecto aunque no se pase --create
    def _in_unreal() -> bool:
        try:
            import unreal  # type: ignore
            return True
        except Exception:
            return False

    # Crear carpetas primero (si estamos en Unreal)
    if _in_unreal():
        create_folders_from_json(data)

    if args.create or _in_unreal():
        # Ejecutar creación dentro de Unreal Editor
        create_material_instances(specs, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
