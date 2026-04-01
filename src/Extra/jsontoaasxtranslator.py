import zipfile
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom
import base64
import os
import json

# --- Base translator ---

def create_and_save_aasx(full_json_data, output_path):
    
    def create_element(tag, namespace="https://admin-shell.io/aas/3/0"):
        """Creates an XML element with the correct namespace."""
        return ET.Element(f"{{{namespace}}}{tag}")


    def create_element_with_text(tag, text):
        """Creates an XML element with text, handling null values."""
        el = create_element(tag)
        el.text = str(text) if text is not None else ""
        return el


    def build_keys_xml(parent, keys_data):
        """Builds the <keys> section."""
        keys_el = create_element('keys')
        parent.append(keys_el)
        for key_item in keys_data:
            key_el = create_element('key')
            keys_el.append(key_el)
            for k, v in key_item.items():
                if k != "modelType":
                    sub_el = create_element(k)
                    sub_el.text = str(v)
                    key_el.append(sub_el)


    def build_reference_xml(parent_el, tag_name, ref_data):
        """Builds a reference element (e.g., <reference>, <semanticId>)."""
        ref_parent = create_element(tag_name)
        parent_el.append(ref_parent)
        if 'type' in ref_data:
            type_el = create_element('type')
            type_el.text = ref_data['type']
            ref_parent.append(type_el)
        if 'keys' in ref_data:
            build_keys_xml(ref_parent, ref_data['keys'])


    def build_description_xml(parent_el, description_data):
        """Builds the standardized <description> element with LangStringTextType."""
        if not description_data:
            return
        
        desc_el = create_element('description')
        parent_el.append(desc_el)
        
        for item in description_data:
            ls_el = create_element('langStringTextType')
            desc_el.append(ls_el)
            
            # CORRECTED STRUCTURE: <language> and <text> as child elements
            lang_el = create_element_with_text('language', item.get('language', 'en'))
            ls_el.append(lang_el)
            
            text_el = create_element_with_text('text', item.get('text', ''))
            ls_el.append(text_el)


    def build_sme_recursively(parent, sme_list):
        """Recursively builds the SubmodelElement tree."""
        for sme in sme_list:
            model_type = sme.get("modelType")
            if not model_type: continue

            # Convert "Property" -> "property", "SubmodelElementCollection" -> "submodelElementCollection"
            tag_name = model_type[0].lower() + model_type[1:]
            sme_el = create_element(tag_name)
            parent.append(sme_el)

            children_value = sme.get("value")

            for key, val in sme.items():
                if key in ["modelType", "value"]: continue
                
                if key == "semanticId" and isinstance(val, dict):
                    build_reference_xml(sme_el, key, val)
                elif key == "description" and isinstance(val, list):
                    # FIX: Now correctly builds descriptions for SubmodelElements
                    build_description_xml(sme_el, val)
                else:
                    sme_el.append(create_element_with_text(key, val))

            if children_value is not None:
                if model_type == "SubmodelElementCollection":
                    value_parent = create_element('value')
                    sme_el.append(value_parent)
                    build_sme_recursively(value_parent, children_value)
                elif model_type == "ReferenceElement":
                    build_reference_xml(sme_el, 'value', children_value)
                else:  # For Property, etc.
                    value_el = create_element('value')
                    value_el.text = str(children_value)
                    sme_el.append(value_el)


    def dict_to_full_aas_xml(data):
        """Converts the full Python dict to a valid AAS V3 XML string."""
        namespace = "https://admin-shell.io/aas/3/0"
        ET.register_namespace('', namespace)
        root = create_element("environment")

        shells_parent = create_element('assetAdministrationShells')
        root.append(shells_parent)
        for shell_data in data.get("assetAdministrationShells", []):
            shell_el = create_element('assetAdministrationShell')
            shells_parent.append(shell_el)
            asset_info_data = shell_data.get("assetInformation", {})
            submodels_data = shell_data.get("submodels", [])
            description_data = shell_data.get("description", [])

            shell_el.append(create_element_with_text('idShort', shell_data.get('idShort')))
            shell_el.append(create_element_with_text('id', shell_data.get('id')))

            # Handle top-level Description (FIXED)
            if description_data:
                build_description_xml(shell_el, description_data)

            asset_info_el = create_element('assetInformation')
            shell_el.append(asset_info_el)
            for key, val in asset_info_data.items():
                asset_info_el.append(create_element_with_text(key, val))

            if submodels_data:
                submodels_ref_el = create_element('submodels')
                shell_el.append(submodels_ref_el)
                for sm_ref in submodels_data:
                    build_reference_xml(submodels_ref_el, 'reference', sm_ref)

        submodels_parent = create_element('submodels')
        root.append(submodels_parent)
        for sm_data in data.get("submodels", []):
            sm_el = create_element('submodel')
            submodels_parent.append(sm_el)
            elements_data = sm_data.get("submodelElements", [])
            semantic_id_data = sm_data.get("semanticId")

            sm_el.append(create_element_with_text('idShort', sm_data.get('idShort')))
            sm_el.append(create_element_with_text('id', sm_data.get('id')))
            if sm_data.get('kind'):
                sm_el.append(create_element_with_text('kind', sm_data.get('kind')))

            if semantic_id_data:
                build_reference_xml(sm_el, 'semanticId', semantic_id_data)

            if elements_data:
                smes_parent = create_element('submodelElements')
                sm_el.append(smes_parent)
                build_sme_recursively(smes_parent, elements_data)

        cds_parent = create_element('conceptDescriptions')
        root.append(cds_parent)
        for cd_data in data.get("conceptDescriptions", []):
            cd_el = create_element('conceptDescription')
            cds_parent.append(cd_el)
            cd_el.append(create_element_with_text('idShort', cd_data.get('idShort')))
            cd_el.append(create_element_with_text('id', cd_data.get('id')))

        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode('utf-8')

        
    print(f"Creating AASX package at: {output_path}...")

    # Determine internal filename based on the first Shell's idShort
    try:
        id_short_for_path = full_json_data["assetAdministrationShells"][0]["idShort"]
    except (KeyError, IndexError):
        id_short_for_path = "AAS"

    xml_content_str = dict_to_full_aas_xml(full_json_data)
    xml_filename_in_zip = f"aasx/{id_short_for_path}/{id_short_for_path}.aas.xml"

    # Standard Open Packaging Conventions (OPC) files for AASX
    content_types_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="xml" ContentType="text/xml"/>
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="png" ContentType="image/png"/>
    <Override PartName="/aasx/aasx-origin" ContentType="text/plain"/>
</Types>"""

    root_rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="R0" Type="http://www.admin-shell.io/aasx/relationships/aasx-origin" Target="/aasx/aasx-origin"/>
    <Relationship Id="R_thumb" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="/thumbnail.png"/>
</Relationships>"""

    origin_rels_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="R1" Type="http://www.admin-shell.io/aasx/relationships/aas-spec" Target="/{xml_filename_in_zip}"/>
</Relationships>"""

    # Placeholder thumbnail (1x1 transparent PNG)
    png_1x1_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    png_1x1_bytes = base64.b64decode(png_1x1_base64)

    # Create Zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("thumbnail.png", png_1x1_bytes)
        zf.writestr("aasx/aasx-origin", "Generated by Python Script")
        zf.writestr("aasx/_rels/aasx-origin.rels", origin_rels_xml)
        zf.writestr(xml_filename_in_zip, xml_content_str.encode('utf-8'))

    # Write to disk
    try:
        with open(output_path, 'wb') as f:
            f.write(zip_buffer.getvalue())
        print(f"--- SUCCESS! ---")
        print(f"File saved: {os.path.basename(output_path)}")
    except Exception as e:
        print(f"--- ERROR SAVING FILE ---")
        print(f"Could not save to '{output_path}': {e}")

# --- With scanf ---

def convert_json_to_aasx(json_filepath):
    """Reads a JSON file and converts it to an AASX package in the same folder."""
    
    if not os.path.exists(json_filepath):
        print(f"Error: File not found: {json_filepath}")
        return

    # 1. Read JSON
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded JSON: {json_filepath}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return

    # 2. Determine Output Filename
    # Changes extension from .json to .aasx
    folder = os.path.dirname(json_filepath)
    filename_no_ext = os.path.splitext(os.path.basename(json_filepath))[0]
    output_path = os.path.join(folder, f"{filename_no_ext}.aasx")

    # 3. Create AASX
    create_and_save_aasx(data, output_path)


# --- Main Execution ---
if __name__ == "__main__":
    # You can hardcode a path here or ask for input
    target_file = input("Enter the path to your JSON file (e.g., model_z1.json): ")
    
    # Remove quotes if the user copied path as "path/to/file"
    target_file = target_file.strip('"').strip("'")
    
    convert_json_to_aasx(target_file)