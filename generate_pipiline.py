# ============================================================
# SCRIPT ÚNICO – PIPELINE COMPLETO REPOSITÓRIO KODI
# 1. Processa ZIPs (extrai addon.xml, assets, renomeia zip)
# 2. Gera addons.xml e addons.xml.md5
# 3. Gera / remove index.html (bottom-up)
# ============================================================

import os
import zipfile
import shutil
import hashlib
import re
from pathlib import Path
import xml.etree.ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent

EXCLUDED_DIRS = {
    ".git", ".svn", "__pycache__", ".idea"
}

# ============================================================
# UTILIDADES GERAIS
# ============================================================

def safe_mkdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

# ============================================================
# ======= ETAPA 1 – PROCESSAR ZIPs DE ADDONS =================
# ============================================================

def find_addon_xml(z: zipfile.ZipFile):
    for name in z.namelist():
        low = name.lower()
        if low == "addon.xml" or low.endswith("/addon.xml"):
            return name
    return None

def extract_asset_paths(root):
    assets = []
    for tag in ("icon", "fanart", "screenshot"):
        for el in root.findall(f".//{tag}"):
            if el.text and el.text.strip():
                assets.append(el.text.strip())
    return assets

def process_zip(zip_path: Path):
    original_name = zip_path.name

    with zipfile.ZipFile(zip_path, "r") as z:
        addon_xml_internal = find_addon_xml(z)
        if not addon_xml_internal:
            print(f"⚠ addon.xml não encontrado em {original_name}")
            return

        addon_root_dir = Path(addon_xml_internal).parent
        addon_xml_bytes = z.read(addon_xml_internal)
        root = ET.fromstring(addon_xml_bytes)

        addon_id = root.attrib.get("id")
        addon_version = root.attrib.get("version", "0.0.0")

        folder_name = addon_id or zip_path.stem
        addon_folder = BASE_DIR / folder_name
        safe_mkdir(addon_folder)

        # addon.xml
        (addon_folder / "addon.xml").write_bytes(addon_xml_bytes)

        # assets
        for asset in extract_asset_paths(root):
            internal = (addon_root_dir / asset).as_posix().lstrip("/")
            if internal in z.namelist():
                target = addon_folder / asset
                safe_mkdir(target.parent)
                target.write_bytes(z.read(internal))
            else:
                print(f"⚠ Asset não encontrado: {internal}")

    # renomeia zip
    new_name = f"{addon_id}-{addon_version}.zip" if addon_id else original_name
    final_zip = addon_folder / new_name
    shutil.move(zip_path, final_zip)

    if new_name != original_name:
        print(f"🔄 Zip renomeado: {original_name} → {new_name}")

    print(f"✔ Addon processado: {folder_name}")

def etapa_processar_zips():
    zips = [
        p for p in BASE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".zip"
    ]

    if not zips:
        print("Nenhum zip encontrado.")
        return

    for z in zips:
        process_zip(z)

# ============================================================
# ======= ETAPA 2 – GERA addons.xml + MD5 ====================
# ============================================================

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i

def gerar_addons_xml():
    root = ET.Element("addons")
    addons = []

    for entry in BASE_DIR.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in EXCLUDED_DIRS:
            continue

        addon_xml = entry / "addon.xml"
        if not addon_xml.exists():
            continue

        try:
            tree = ET.parse(addon_xml)
            addon = tree.getroot()
            if addon.tag == "addon":
                addons.append(addon)
        except Exception as e:
            print(f"Erro em {addon_xml}: {e}")

    addons.sort(key=lambda a: a.attrib.get("id", "").lower())

    for a in addons:
        root.append(a)

    indent(root)

    tree = ET.ElementTree(root)
    tree.write(
        BASE_DIR / "addons.xml",
        encoding="UTF-8",
        xml_declaration=True
    )

def gerar_md5():
    data = (BASE_DIR / "addons.xml").read_bytes()
    md5 = hashlib.md5(data).hexdigest()
    (BASE_DIR / "addons.xml.md5").write_text(md5, encoding="utf-8")

def etapa_addons_xml():
    gerar_addons_xml()
    gerar_md5()
    print("✔ addons.xml e addons.xml.md5 gerados")

# ============================================================
# ======= ETAPA 3 – INDEX.HTML ===============================
# ============================================================

def extrair_versao(nome: str):
    m = re.search(r"One\.repo-(\d+(?:\.\d+)*)\.zip", nome)
    return tuple(map(int, m.group(1).split("."))) if m else ()

def pasta_tem_zip(pasta: Path) -> bool:
    return any(p.suffix.lower() == ".zip" for p in pasta.rglob("*.zip"))

def encontrar_repos_mais_recentes(raiz: Path):
    encontrados = []
    for item in raiz.rglob("One.repo-*.zip"):
        v = extrair_versao(item.name)
        if v:
            encontrados.append((v, item))

    if not encontrados:
        return []

    maior = max(v for v, _ in encontrados)
    return [p for v, p in encontrados if v == maior]

def gerar_ou_remover_index(pasta: Path, raiz: Path):
    index = pasta / "index.html"
    tem_zip = pasta_tem_zip(pasta)

    if pasta != raiz and not tem_zip:
        if index.exists():
            index.unlink()
        return

    repos = encontrar_repos_mais_recentes(raiz)

    if pasta == raiz and not repos:
        if index.exists():
            index.unlink()
        return

    linhas = [
        "<!DOCTYPE html>",
        "<html><head>",
        '<meta charset="utf-8">',
        "<title>Directory listing</title>",
        "</head><body>",
        "<h1>Directory listing</h1><hr/><pre>",
    ]

    if pasta != raiz:
        linhas.append('<a href="../index.html">..</a>')

    for item in sorted(pasta.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        if item.name.startswith(".") or item.name == "index.html":
            continue
        if item.is_dir() and pasta_tem_zip(item):
            linhas.append(f'<a href="./{item.name}/index.html">{item.name}/</a>')
        elif item.is_file() and item.suffix.lower() == ".zip":
            linhas.append(f'<a href="./{item.name}">{item.name}</a>')

    linhas.extend(["</pre></body></html>"])

    if pasta == raiz and repos:
        linhas += [
            "",
            "<!-- REPOSITORIO KODI (FORA DO HTML) -->",
            '<div id="Repositorio-KODI" style="display:none"><table>',
        ]
        for r in repos:
            rel = r.relative_to(raiz).as_posix()
            linhas.append(f'<tr><td><a href="{rel}">{rel}</a></td></tr>')
        linhas += ["</table></div>"]

    index.write_text("\n".join(linhas), encoding="utf-8")
    print(f"✔ index atualizado: {pasta}")

def varrer_bottom_up(pasta: Path, raiz: Path):
    for sub in pasta.iterdir():
        if sub.is_dir() and not sub.name.startswith("."):
            varrer_bottom_up(sub, raiz)
    gerar_ou_remover_index(pasta, raiz)

def etapa_index():
    raiz = BASE_DIR
    varrer_bottom_up(raiz, raiz)
    gerar_ou_remover_index(raiz, raiz)

# ============================================================
# ============================ MAIN ==========================
# ============================================================

def main():
    print("🚀 Iniciando pipeline...")
    etapa_processar_zips()
    etapa_addons_xml()
    etapa_index()
    print("🏁 Pipeline finalizado com sucesso")

if __name__ == "__main__":
    main()
