import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------- Config ----------------------------------
# Carpeta fija de destino (relativa a la raíz del proyecto)
DEST_RELATIVE = Path('Content') / 'Texture' / 'MayerFabrics'

# Nombre del archivo de datos por defecto. Se auto-detecta similar a create_materials.py
DEFAULT_JSON_CANDIDATES = [
    'collections.json',
    'okcollections.json',
]


# URL builder (no thumbnails):
# Ejemplo proporcionado: https://images.mayerfabrics.com/item/804-004/image?download=804-004
def build_download_url(variation_pattern: str) -> str:
    pat = variation_pattern.strip()
    return f"https://images.mayerfabrics.com/item/{pat}/image?download={pat}"


# ----------------------------- Sanitización nombres -----------------------------
# Copiado del estilo de create_materials.py para carpetas (no tokens MI)
INVALID_WIN = r'[<>:"/\\|?*]'


def sanitize_folder(name: str) -> str:
    """Sanitiza nombres de carpetas estilo Windows-safe.
    - Reemplaza caracteres inválidos por '_'
    - Colapsa espacios múltiples
    - Quita punto/espacio al final
    - Mantiene espacios (no los convierte a '-')
    """
    s = re.sub(INVALID_WIN, "_", str(name).strip())
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(". ")
    return s if s else "_"


# ---------------------------------- JSON helpers ----------------------------------
def _get_collection_name(coll: Dict[str, Any]) -> str:
    return (coll.get("collection-name") or coll.get("collection") or "").strip()


def _get_subcollection_list(coll: Dict[str, Any]) -> List[Dict[str, Any]]:
    subs = coll.get("subcollection")
    return subs or []


def _get_subcollection_name(sub: Dict[str, Any]) -> str:
    return (sub.get("subcollection-name") or sub.get("name") or "").strip()


def _get_variations_list(sub: Dict[str, Any]) -> List[Any]:
    v = sub.get("variations")
    if v is None:
        v = sub.get("variation")
    return v or []


def _get_variation_pattern(variation_item: Any) -> Optional[str]:
    if isinstance(variation_item, dict):
        vp = (variation_item.get("variation-pattern") or "").strip()
        return vp or None
    # Si es string plano, no hay patrón confiable -> no podemos descargar
    return None


# ------------------------------- Descubrimiento JSON -------------------------------
def find_json_file(cli_path: Optional[str]) -> Path:
    """Localiza el archivo JSON de colecciones.
    Prioridad:
      1) --json de CLI
      2) Var entorno COLLECTIONS_JSON
      3) Mismos directorios cercanos (Python/, raíz proyecto)
    """
    if cli_path:
        p = Path(cli_path).expanduser().resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"No existe JSON en ruta proporcionada: {cli_path}")

    env_path = os.environ.get("COLLECTIONS_JSON")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p

    # Buscar a partir del directorio de este script
    script_dir = Path(__file__).parent.resolve()
    candidates: List[Path] = []
    # En misma carpeta
    for name in DEFAULT_JSON_CANDIDATES:
        candidates.append(script_dir / name)
    # En carpeta Python padre
    if script_dir.name.lower() == 'python':
        project_root = script_dir.parent
    else:
        project_root = script_dir
    for name in DEFAULT_JSON_CANDIDATES:
        candidates.append(project_root / 'Python' / name)
        candidates.append(project_root / name)

    # Subir hasta 3 niveles por si acaso
    cur = project_root
    for _ in range(3):
        cur = cur.parent
        for name in DEFAULT_JSON_CANDIDATES:
            candidates.append(cur / 'Python' / name)
            candidates.append(cur / name)

    seen = set()
    for c in candidates:
        c = c.resolve()
        if c in seen:
            continue
        seen.add(c)
        if c.exists():
            return c

    raise FileNotFoundError("No se encontró 'collections.json'. Usa --json <ruta> o define COLLECTIONS_JSON.")


def resolve_project_root(json_file: Path) -> Path:
    # Si el JSON está en .../Python/collections.json => project_root = .../
    project_root = json_file.parent
    if project_root.name.lower() == 'python':
        project_root = project_root.parent
    return project_root


# -------------------------------- Descargas --------------------------------
def http_get(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(
        url,
        method='GET',
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36',
            'Accept': 'image/*,application/octet-stream;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # No inferimos extensión; guardaremos como .jpg según preferencia del usuario
        return resp.read()


def download_with_retries(url: str, dest_path: Path, retries: int = 3, timeout: float = 20.0, backoff: float = 1.5) -> Tuple[bool, str]:
    last_err: Optional[BaseException] = None
    for attempt in range(1, retries + 1):
        try:
            data = http_get(url, timeout=timeout)
            # Guardado atómico
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest_path.with_suffix(dest_path.suffix + '.part')
            with open(tmp, 'wb') as f:
                f.write(data)
            tmp.replace(dest_path)
            return True, "ok"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff ** attempt)
            else:
                break
    return False, str(last_err) if last_err else "error"


# ---------------------------------- Proceso ----------------------------------
def process_all(json_path: Path, dest_root: Path) -> Tuple[int, int, int, List[str]]:
    """Procesa el JSON y descarga imágenes.
    Retorna: (descargados, saltados, fallidos, errores[])
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    downloaded = 0
    skipped = 0
    failed = 0
    errors: List[str] = []

    for coll in data or []:
        coll_name = _get_collection_name(coll)
        if not coll_name:
            continue
        coll_folder = sanitize_folder(coll_name)
        for sub in _get_subcollection_list(coll):
            sub_name = _get_subcollection_name(sub)
            if not sub_name:
                continue
            sub_folder = sanitize_folder(sub_name)
            target_dir = (dest_root / coll_folder / sub_folder).resolve()

            for var in _get_variations_list(sub):
                pattern = _get_variation_pattern(var)
                if not pattern:
                    failed += 1
                    errors.append(f"Sin 'variation-pattern' -> {coll_name}/{sub_name}")
                    continue

                url = build_download_url(pattern)
                filename = f"{pattern}.jpg"  # Preferencia explícita del usuario
                dest_file = target_dir / filename

                if dest_file.exists():
                    skipped += 1
                    continue

                ok, msg = download_with_retries(url, dest_file)
                if ok:
                    downloaded += 1
                else:
                    failed += 1
                    errors.append(f"{pattern}: {msg}")

    return downloaded, skipped, failed, errors


def show_final_popup(downloaded: int, skipped: int, failed: int, errors: List[str]) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        # Sin entorno gráfico
        print("Descargas finalizadas.")
        print(f"Descargados: {downloaded}, Saltados: {skipped}, Fallidos: {failed}")
        if errors:
            print("Errores:")
            for e in errors:
                print(" -", e)
        return

    if failed and errors:
        # Ventana scrollable para errores
        root = tk.Tk()
        root.title("MayerFabrics - Errores de Descarga")
        root.geometry("600x400")
        root.resizable(True, True)
        frame = tk.Frame(root, padx=12, pady=10)
        frame.pack(fill='both', expand=True)

        summary = f"Descargas finalizadas.\n\nDescargados: {downloaded}\nSaltados (existían): {skipped}\nFallidos: {failed}\n\nErrores:"
        lbl = tk.Label(frame, text=summary, anchor='w', justify='left', font=('Segoe UI', 10, 'bold'))
        lbl.pack(fill='x', pady=(0, 8))

        text_frame = tk.Frame(frame)
        text_frame.pack(fill='both', expand=True)
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')
        text = tk.Text(text_frame, wrap='word', yscrollcommand=scrollbar.set, font=('Consolas', 10))
        text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=text.yview)

        for e in errors:
            text.insert('end', f"- {e}\n")
        text.config(state='disabled')

        btn = tk.Button(frame, text='Cerrar', command=root.destroy, width=12)
        btn.pack(pady=10)
        root.eval('tk::PlaceWindow . center')
        root.mainloop()
    else:
        # Popup simple si no hay errores
        root = tk.Tk()
        root.withdraw()
        summary = f"Descargas finalizadas.\n\nDescargados: {downloaded}\nSaltados (existían): {skipped}\nFallidos: {failed}"
        messagebox.showinfo("MayerFabrics - Descargas", summary)
        root.destroy()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Descarga texturas de MayerFabrics según collections.json")
    parser.add_argument('--json', dest='json_path', help='Ruta a collections.json (opcional)')
    parser.add_argument('--no-gui', action='store_true', help='No mostrar popup final (solo consola)')
    args = parser.parse_args(argv)

    try:
        json_file = find_json_file(args.json_path)
    except FileNotFoundError as e:
        print(str(e))
        return 2

    project_root = resolve_project_root(json_file)
    dest_root = (project_root / DEST_RELATIVE).resolve()

    print(f"Usando JSON: {json_file}")
    print(f"Destino: {dest_root}")

    if args.no_gui:
        # Modo sin interfaz
        downloaded, skipped, failed, errors = process_all(json_file, dest_root)
        print(f"Descargados: {downloaded}, Saltados: {skipped}, Fallidos: {failed}")
        if errors:
            for e in errors[:10]:
                print(" -", e)
        return 0 if failed == 0 else 1

    # Con interfaz: construir lista de tareas y mostrar confirmación + ventana de progreso simple
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        # Sin Tk disponible, ejecuta en modo consola
        downloaded, skipped, failed, errors = process_all(json_file, dest_root)
        print(f"Descargados: {downloaded}, Saltados: {skipped}, Fallidos: {failed}")
        if errors:
            for e in errors[:10]:
                print(" -", e)
        show_final_popup(downloaded, skipped, failed, errors)
        return 0 if failed == 0 else 1

    # Construir tareas a descargar (excluyendo ya existentes y entradas sin pattern)
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tasks: List[Tuple[str, str, str, str, Path]] = []  # (coll, sub, pattern, url, dest_file)
    for coll in data or []:
        coll_name = _get_collection_name(coll)
        if not coll_name:
            continue
        coll_folder = sanitize_folder(coll_name)
        for sub in _get_subcollection_list(coll):
            sub_name = _get_subcollection_name(sub)
            if not sub_name:
                continue
            sub_folder = sanitize_folder(sub_name)
            target_dir = (dest_root / coll_folder / sub_folder).resolve()
            for var in _get_variations_list(sub):
                pattern = _get_variation_pattern(var)
                if not pattern:
                    continue
                url = build_download_url(pattern)
                dest_file = target_dir / f"{pattern}.jpg"
                if dest_file.exists():
                    continue
                tasks.append((coll_name, sub_name, pattern, url, dest_file))

    total = len(tasks)

    root = tk.Tk()
    root.title("MayerFabrics - Descargas")
    root.geometry("520x140")
    root.resizable(False, False)
    root.eval('tk::PlaceWindow . center')

    # Confirmación inicial
    root.withdraw()
    if total == 0:
        messagebox.showinfo("MayerFabrics - Descargas", "No hay nada para descargar. Archivos ya existen o JSON vacío.")
        root.destroy()
        return 0
    msg = f"Se descargarán {total} imágenes en:\n{dest_root}\n\n¿Desea continuar?"
    if not messagebox.askokcancel("Confirmar descarga", msg):
        root.destroy()
        return 0

    # Ventana de progreso simple (sin barra), con botón Cancelar
    root.deiconify()
    frame = tk.Frame(root, padx=12, pady=10)
    frame.pack(fill='both', expand=True)
    status_var = tk.StringVar()
    status_lbl = tk.Label(frame, textvariable=status_var, justify='left', anchor='w')
    status_lbl.pack(fill='x', expand=True)

    counts_var = tk.StringVar()
    counts_lbl = tk.Label(frame, textvariable=counts_var, font=('Segoe UI', 10, 'bold'))
    counts_lbl.pack(fill='x', pady=(6, 8))

    cancel_flag = {'val': False}
    def on_cancel() -> None:
        cancel_flag['val'] = True
        status_var.set("Cancelando... espera a que termine la operación en curso.")
        root.update()

    btn = tk.Button(frame, text='Cancelar', command=on_cancel, width=12)
    btn.pack(side='right')

    downloaded = 0
    skipped = 0
    failed = 0
    errors: List[str] = []

    for i, (coll_name, sub_name, pattern, url, dest_file) in enumerate(tasks, start=1):
        if cancel_flag['val']:
            break
        status_var.set(f"[{i}/{total}] {coll_name} / {sub_name} -> {pattern}.jpg")
        counts_var.set(f"Descargados: {downloaded}   Fallidos: {failed}")
        root.update()

        ok, msg = download_with_retries(url, dest_file)
        if ok:
            downloaded += 1
        else:
            failed += 1
            errors.append(f"{pattern}: {msg}")

        counts_var.set(f"Descargados: {downloaded}   Fallidos: {failed}")
        root.update()

    root.destroy()

    # Mostrar popup final con resumen
    show_final_popup(downloaded, skipped, failed, errors)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

