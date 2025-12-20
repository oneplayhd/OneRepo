import os
import zipfile
import xml.etree.ElementTree as ET
import shutil

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def safe_mkdir(path):
    os.makedirs(path, exist_ok=True)


def find_addon_xml(z):
    for name in z.namelist():
        name_low = name.lower()
        if name_low == "addon.xml" or name_low.endswith("/addon.xml"):
            return name
    return None


def extract_asset_paths(root):
    assets = []
    for tag in ("icon", "fanart", "screenshot"):
        for el in root.findall(f".//{tag}"):
            if el.text and el.text.strip():
                assets.append(el.text.strip())
    return assets


def process_zip(zip_path):
    original_zip_name = os.path.basename(zip_path)

    with zipfile.ZipFile(zip_path, "r") as z:
        addon_xml_internal = find_addon_xml(z)

        if not addon_xml_internal:
            print(f"⚠ addon.xml não encontrado em {original_zip_name}")
            return

        addon_root_dir = os.path.dirname(addon_xml_internal)
        addon_xml_bytes = z.read(addon_xml_internal)

        root = ET.fromstring(addon_xml_bytes)

        addon_id = root.attrib.get("id")
        addon_version = root.attrib.get("version", "0.0.0")

        addon_folder_name = addon_id or os.path.splitext(original_zip_name)[0]
        addon_folder = os.path.join(BASE_DIR, addon_folder_name)
        safe_mkdir(addon_folder)

        # --- extrai addon.xml ---
        with open(os.path.join(addon_folder, "addon.xml"), "wb") as f:
            f.write(addon_xml_bytes)

        # --- extrai imagens ---
        assets = extract_asset_paths(root)

        for asset in assets:
            internal_path = (
                f"{addon_root_dir}/{asset}" if addon_root_dir else asset
            ).lstrip("/")

            if internal_path in z.namelist():
                target_path = os.path.join(addon_folder, asset)
                safe_mkdir(os.path.dirname(target_path))

                with open(target_path, "wb") as f:
                    f.write(z.read(internal_path))
            else:
                print(f"⚠ Imagem não encontrada no zip: {internal_path}")

    # --- renomeia e move zip ---
    expected_zip_name = (
        f"{addon_id}-{addon_version}.zip"
        if addon_id else original_zip_name
    )

    final_zip_path = os.path.join(addon_folder, expected_zip_name)
    shutil.move(zip_path, final_zip_path)

    if original_zip_name != expected_zip_name:
        print(f"🔄 Zip renomeado: {original_zip_name} → {expected_zip_name}")

    print(f"✔ Extraído corretamente: {addon_folder_name}")


def main():
    # apenas zips na raiz
    zips = [
        f for f in os.listdir(BASE_DIR)
        if f.lower().endswith(".zip")
        and os.path.isfile(os.path.join(BASE_DIR, f))
    ]

    if not zips:
        print("Nenhum zip encontrado.")
        return

    for zip_file in zips:
        process_zip(os.path.join(BASE_DIR, zip_file))


if __name__ == "__main__":
    main()
