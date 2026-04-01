import zipfile
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom
import base64
import os


# --- Funções de Geração de XML (Completas e Corrigidas) ---

def create_element(tag, namespace="https://admin-shell.io/aas/3/0"):
    """Cria um elemento XML com o namespace correto."""
    return ET.Element(f"{{{namespace}}}{tag}")


def create_element_with_text(tag, text):
    """Cria um elemento XML com texto, tratando valores nulos."""
    el = create_element(tag)
    el.text = str(text) if text is not None else ""
    return el


def build_keys_xml(parent, keys_data):
    """Constrói a secção <keys> com as tags <key> corretas."""
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
    """Constrói um elemento de referência completo (ex: <reference>, <semanticId>)."""
    ref_parent = create_element(tag_name)
    parent_el.append(ref_parent)
    if 'type' in ref_data:
        type_el = create_element('type')
        type_el.text = ref_data['type']
        ref_parent.append(type_el)
    if 'keys' in ref_data:
        build_keys_xml(ref_parent, ref_data['keys'])


def build_sme_recursively(parent, sme_list):
    """Constrói recursivamente a árvore de SubmodelElements."""
    for sme in sme_list:
        model_type = sme.get("modelType")
        if not model_type: continue

        tag_name = model_type[0].lower() + model_type[1:]
        sme_el = create_element(tag_name)
        parent.append(sme_el)

        children_value = sme.get("value")

        for key, val in sme.items():
            if key in ["modelType", "value"]: continue
            if key == "semanticId" and isinstance(val, dict):
                build_reference_xml(sme_el, key, val)
            else:
                sme_el.append(create_element_with_text(key, val))

        if children_value is not None:
            if model_type == "SubmodelElementCollection":
                value_parent = create_element('value')
                sme_el.append(value_parent)
                build_sme_recursively(value_parent, children_value)
            elif model_type == "ReferenceElement":
                build_reference_xml(sme_el, 'value', children_value)
            else:  # Para Property, etc.
                value_el = create_element('value')
                value_el.text = str(children_value)
                sme_el.append(value_el)


def dict_to_full_aas_xml(data):
    """Converte o dicionário Python completo para uma string XML AAS V3 válida."""
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

        shell_el.append(create_element_with_text('idShort', shell_data.get('idShort')))
        shell_el.append(create_element_with_text('id', shell_data.get('id')))

        asset_info_el = create_element('assetInformation')
        shell_el.append(asset_info_el)
        for key, val in asset_info_data.items():
            asset_info_el.append(create_element_with_text(key, val))

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


# --- Função Principal para Criar e GUARDAR o Pacote ---
def create_and_save_aasx(full_json_template, output_path):
    print(f"A criar pacote AASX em: {output_path}...")

    try:
        id_short_for_path = full_json_template["assetAdministrationShells"][0]["idShort"]
    except:
        id_short_for_path = "default"

    xml_content_str = dict_to_full_aas_xml(full_json_template)
    xml_filename_in_zip = f"aasx/{id_short_for_path}/{id_short_for_path}.aas.xml"

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

    aasx_origin_content = ""
    png_1x1_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    png_1x1_bytes = base64.b64decode(png_1x1_base64)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("thumbnail.png", png_1x1_bytes)
        zf.writestr("aasx/aasx-origin", aasx_origin_content)
        zf.writestr("aasx/_rels/aasx-origin.rels", origin_rels_xml)
        zf.writestr(xml_filename_in_zip, xml_content_str.encode('utf-8'))

    try:
        with open(output_path, 'wb') as f:
            f.write(zip_buffer.getvalue())
        print(f"--- SUCESSO! ---")
        print(f"Ficheiro '{os.path.basename(output_path)}' guardado com sucesso.")
        print("Para o ver, tens de reiniciar o servidor (docker restart aasx-server).")
    except Exception as e:
        print(f"\n--- ERRO AO GUARDAR O FICHEIRO ---")
        print(f"Não foi possível guardar o ficheiro em '{output_path}': {e}")


# --- Ponto de Entrada do Script ---
if __name__ == "__main__":
    # ASSUME que a pasta 'AASdata' está no mesmo nível que a pasta onde este script corre.
    # Ex:
    # meu_projeto/
    # |-- AASdata/
    # |-- scripts/
    #     |-- gerar_aasx.py  <-- estás aqui
    # Altera o caminho se a tua estrutura de pastas for diferente.
    AAS_DATA_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'AASdata')

    product_id = input("Introduz o ID do produto: ")
    product_type = input("Introduz o TIPO do produto (ex: QUADRADO): ")

    if not product_id or not product_type:
        print("ID ou TIPO inválidos. A sair.")
    else:
        filename = f"Product_{product_id}.aasx"
        output_filepath = os.path.normpath(os.path.join(AAS_DATA_FOLDER, filename))


        def get_template(id, type):
            # O teu template JSON completo
            return {
                "assetAdministrationShells": [{"idShort": "Product_" + id, "id": "http://zdm.com/aas#Product" + id,
                                               "assetInformation": {"assetKind": "Instance",
                                                                    "globalAssetId": "http://zdm.com/assets#Product" + id,
                                                                    "assetType": "Product " + id}, "submodels": [
                        {"type": "ModelReference",
                         "keys": [{"type": "Submodel", "value": "http://zdm.com/submodels#Product_Stages_" + id}]},
                        {"type": "ModelReference",
                         "keys": [{"type": "Submodel", "value": "http://zdm.com/submodels#Product_Products_" + id}]},
                        {"type": "ModelReference",
                         "keys": [{"type": "Submodel", "value": "http://zdm.com/submodels#Product_Skills_" + id}]},
                        {"type": "ModelReference",
                         "keys": [{"type": "Submodel", "value": "http://zdm.com/submodels#Product_Data_" + id}]}]}],
                "submodels": [{"idShort": "Product_Stages", "id": "http://zdm.com/submodels#Product_Stages_" + id,
                               "kind": "Instance", "semanticId": {"type": "ModelReference", "keys": [
                        {"type": "Submodel", "value": "http://zdm.com/submodels#Product_Stages_" + id}]},
                               "submodelElements": [
                                   {"idShort": "Product_Stages_Collection", "modelType": "SubmodelElementCollection",
                                    "value": [{"idShort": "Product_Stage1", "modelType": "ReferenceElement",
                                               "value": {"type": "ExternalReference", "keys": [
                                                   {"type": "GlobalReference",
                                                    "value": "http://zdm.com/assets#Stage1"}]}}]}]},
                              {"idShort": "Product_Products", "id": "http://zdm.com/submodels#Product_Products_" + id,
                               "kind": "Instance", "semanticId": {"type": "ModelReference", "keys": [
                                  {"type": "Submodel", "value": "http://zdm.com/submodels#Product_Products_" + id}]},
                               "submodelElements": [{"idShort": "Product_Products_Collection",
                                                     "modelType": "SubmodelElementCollection"}]},
                              {"idShort": "Product_Skills", "id": "http://zdm.com/submodels#Product_Skills_" + id,
                               "kind": "Instance", "semanticId": {"type": "ModelReference", "keys": [
                                  {"type": "Submodel", "value": "http://zdm.com/submodels#Product_Skills_" + id}]},
                               "submodelElements": [
                                   {"idShort": "Product_Skills_Collection", "modelType": "SubmodelElementCollection",
                                    "value": [{"idShort": "Product_Skill_1", "modelType": "ReferenceElement",
                                               "value": {"type": "ExternalReference", "keys": [
                                                   {"type": "GlobalReference",
                                                    "value": "http://zdm.com/assets#Skill_" + type}]}}]}]},
                              {"idShort": "Product_Data", "id": "http://zdm.com/submodels#Product_Data_" + id,
                               "kind": "Instance", "semanticId": {"type": "ExternalReference", "keys": [
                                  {"type": "Submodel", "value": "http://zdm.com/submodels#Product_Data_" + id}]},
                               "submodelElements": [{"idShort": "id", "valueType": "xs:string", "value": "" + id,
                                                     "modelType": "Property",
                                                     "semanticId": {"type": "ExternalReference", "keys": [
                                                         {"type": "GlobalReference",
                                                          "value": "http://zdm.com/product" + id + "#id"}]}},
                                                    {"idShort": "type", "valueType": "xs:string", "value": "" + type,
                                                     "modelType": "Property",
                                                     "semanticId": {"type": "ExternalReference", "keys": [
                                                         {"type": "GlobalReference",
                                                          "value": "http://zdm.com/product" + id + "#type"}]}},
                                                    {"idShort": "state", "valueType": "xs:string", "value": "Undefined",
                                                     "modelType": "Property",
                                                     "semanticId": {"type": "ExternalReference", "keys": [
                                                         {"type": "GlobalReference",
                                                          "value": "http://zdm.com/product" + id + "#state"}]}},
                                                    {"idShort": "description", "valueType": "xs:string",
                                                     "value": "Este produto é um " + type, "modelType": "Property",
                                                     "semanticId": {"type": "ExternalReference", "keys": [
                                                         {"type": "GlobalReference",
                                                          "value": "http://zdm.com/product" + id + "#description"}]}},
                                                    {"idShort": "dimensions", "modelType": "SubmodelElementCollection",
                                                     "semanticId": {"type": "ExternalReference", "keys": [
                                                         {"type": "GlobalReference",
                                                          "value": "http://zdm.com/product" + id + "#dimensions"}]},
                                                     "value": [{"idShort": "comprimento", "valueType": "xs:string",
                                                                "value": "Undefined", "modelType": "Property",
                                                                "semanticId": {"type": "ExternalReference", "keys": [
                                                                    {"type": "GlobalReference",
                                                                     "value": "http://zdm.com/product" + id + "#comprimento"}]}},
                                                               {"idShort": "largura", "valueType": "xs:string",
                                                                "value": "Undefined", "modelType": "Property",
                                                                "semanticId": {"type": "ExternalReference", "keys": [
                                                                    {"type": "GlobalReference",
                                                                     "value": "http://zdm.com/product" + id + "#largura"}]}},
                                                               {"idShort": "altura", "valueType": "xs:string",
                                                                "value": "Undefined", "modelType": "Property",
                                                                "semanticId": {"type": "ExternalReference", "keys": [
                                                                    {"type": "GlobalReference",
                                                                     "value": "http://zdm.com/product" + id + "#altura"}]}}]}]}],
                "conceptDescriptions": [
                    {"idShort": "Product_Skills", "id": "http://zdm.com/submodels#Product_Skills_" + id},
                    {"idShort": "Product_Products", "id": "http://zdm.com/submodels#Product_Products_" + id},
                    {"idShort": "Product_Stages", "id": "http://zdm.com/submodels#Product_Stages_" + id},
                    {"idShort": "Product_Data", "id": "http://zdm.com/submodels#Product_Data_" + id}]
            }


        full_template = get_template(product_id, product_type)
        create_and_save_aasx(full_template, output_filepath)