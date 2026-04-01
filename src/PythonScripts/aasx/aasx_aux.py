import json
import re
from urllib import response
import zipfile
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom
import base64
import os
from flask import Flask, request, jsonify
import requests
import ast

#**************************//**************************#
# Variables
#**************************//**************************#

PORT = int(os.getenv("PORT", 5011))

AASURL = os.getenv("AAS_URL", "192.168.0.10:5001") # Casa
AASURL = os.getenv("AAS_URL", "192.168.2.90:5001") # Lab

TEMPLATE_L = "productl/"
TEMPLATE_QUALITYTESTS = "qualitytests/"

TEMPLATE_BASEPACKAGE = "basepackage.json"
TEMPLATE_PRODUCT = "product.json"
TEMPLATE_PRODUCT_COMPLETE = "completeproduct.json"
TEMPLATE_Z1 = "z1.json"
TEMPLATE_Z4 = "z4.json"
TEMPLATE_EXPLANATION = "explanation.json"
TEMPLATE_MEASUREMENTS_QUADRADO_RETANGULO = "measurementsquadradoretangulo.json"
TEMPLATE_MEASUREMENTS_L = "measurementsl.json"

TEMPLATE_MEASUREMENTS_VALORTIPO = "mm"
TEMPLATE_MEASUREMENTS_INCERTEZA = "0.1"

REPLACE_ID = "91"
REPLACE_PRODUCT_TYPE = "Quadrado"
REPLACE_INFERENCE_TYPE = "z1"
REPLACE_SPEED = "REPLACESPEED"
REPLACE_GCODE = "REPLACEGCODE"
REPLACE_STATE = "REPLACESTATE"
REPLACE_INFERENCE_INPUTMETRICS = "REPLACEIINPUTMETRICS"
REPLACE_INFERENCE_RESULT = "REPLACEIRESULT"
REPLACE_EXPLANATION_RESULT = "REPLACEERESULT"
REPLACE_QUALITYTEST_RESULT = "REPLACEQTRESULT"
REPLACE_MEASUREMENTS_VALORTIPOLARGURA = "REPLACEVALORTIPOLARGURA"
REPLACE_MEASUREMENTS_INCERTEZALARGURA = "REPLACEINCERTEZALARGURA"
REPLACE_MEASUREMENTS_VALORLARGURA = "REPLACEVALORLARGURA"
REPLACE_MEASUREMENTS_VALORTIPOCOMPRIMENTO = "REPLACEVALORTIPOCOMPRIMENTO"
REPLACE_MEASUREMENTS_INCERTEZACOMPRIMENTO = "REPLACEINCERTEZACOMPRIMENTO"
REPLACE_MEASUREMENTS_VALORCOMPRIMENTO = "REPLACEVALORCOMPRIMENTO"
REPLACE_MEASUREMENTS_VALORTIPOALTURA = "REPLACEVALORTIPOALTURA"
REPLACE_MEASUREMENTS_INCERTEZAALTURA = "REPLACEINCERTEZAALTURA"
REPLACE_MEASUREMENTS_VALORALTURA = "REPLACEVALORALTURA"

#**************************//**************************#
# AAS Functions
#**************************//**************************#

def CreateAASX(full_json_data, returnorstore, output_path = ""):
    
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

    if(returnorstore):
        zip_buffer.seek(0)
        return zip_buffer
    else:
        try:
            with open(output_path, 'wb') as f:
                f.write(zip_buffer.getvalue())
            print(f"--- SUCCESS! ---")
            print(f"File saved: {os.path.basename(output_path)}")
        except Exception as e:
            print(f"--- ERROR SAVING FILE ---")
            print(f"Could not save to '{output_path}': {e}")

def GerarAASJSON(template_path, lista_substituicoes):
    
    with open(template_path, "r", encoding="utf-8") as f:
        conteudo_modificado = f.read()

    for antigo, novo in lista_substituicoes:
        
        antigo = str(antigo)
        novo = str(novo)

        # Sub exata
        conteudo_modificado = conteudo_modificado.replace(antigo, novo)
        # Sub com capitalizacao
        conteudo_modificado = conteudo_modificado.replace(antigo.capitalize(), novo.capitalize())
        # Sub minuscula
        conteudo_modificado = conteudo_modificado.replace(antigo.lower(), novo.lower())

    try:
        return json.loads(conteudo_modificado)
    except json.JSONDecodeError as e:
        print(f"[Erro] - As substituições quebraram o formato JSON. Detalhes: {e}")
        return None

#**************************//**************************#
# Flask
#**************************//**************************#

app = Flask(__name__)

@app.route('/addbasepackage', methods=['POST'])
def AddBasePackage():
    try:
        toReplace = []
        
        customAASJson = GerarAASJSON(TEMPLATE_BASEPACKAGE, toReplace)
        
        aas = CreateAASX(customAASJson, True)
        
        files = {
            'file': ('basepackage.aasx', aas, 'application/asset-administration-shell-package')
        }
        response = requests.post("http://" + AASURL + "/packages", files=files)
        
        return jsonify({"message": "BasePackage added with success", "Response from Swagger": str(response.json())}), 200
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 31,
#         "type": "L",
#         "speed": 200,
#         "gcode": "teste.gcode"
#     }
# }
@app.route('/addproduct', methods=['POST'])
def AddNewProduct():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        type = data.get("type")

        if type == "Complete":
            
            toReplace = [
                (REPLACE_ID, id),
                (REPLACE_STATE, "Assembled")
            ]

            customAASJson = GerarAASJSON(TEMPLATE_PRODUCT_COMPLETE, toReplace)
        
            subproductsraw = data.get("subproducts")
            subproducts = []
            
            def ProductTemplateMaker(id) :
                return {
                    "idShort": "Product_" + id,
                    "modelType": "ReferenceElement",
                    "value": {
                        "type": "ModelReference",
                        "keys": [
                            {
                                "type": "Submodel",
                                "value": "http://zdm/aas/product_" + id
                            }
                        ]
                    }
                }
                
            for product in subproductsraw:
                subproducts.append(ProductTemplateMaker(str(product)))
            
            customAASJson["submodels"][0]["submodelElements"] = subproducts
            
            aasPackage = CreateAASX(customAASJson, True)
        
        else: 

            speed = str(data.get("speed"))
            gcode = data.get("gcode")

            toReplace = [
                (REPLACE_ID, id),
                (REPLACE_PRODUCT_TYPE , type),
                (REPLACE_SPEED, speed),
                (REPLACE_GCODE, gcode),
                (REPLACE_STATE, "Printing")
            ]

            customAASJson = GerarAASJSON(TEMPLATE_PRODUCT, toReplace)
        
            aasPackage = CreateAASX(customAASJson, True)
        
        files = {
            'file': ('product' + id + '.aasx', aasPackage, 'application/asset-administration-shell-package')
        }

        response = requests.post("http://" + AASURL + "/packages", files=files)
        
        return jsonify({"message": "AASX created with success", "Response from Swagger": str(response.json())}), 200
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500
    
# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30
#     }
# }
@app.route('/getproductstate', methods=['POST'])
def GetProductState():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        
        productDataPath = "http://zdm/submodels/product_" + id + "_data"
        
        productData = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productDataPath.encode("utf-8")).decode('utf-8')).json()
        
        response = productData["submodelElements"][1]["value"]
        
        return jsonify({"message": "Measurements retrieved with success", "Response from Swagger": str(response)}), 200
                
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "state": "In Storage"
#     }
# }
@app.route('/setproductstate', methods=['POST'])
def SetProductState():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        state = str(data.get("state"))
        
        productDataPath = "http://zdm/submodels/product_" + id + "_data"
        
        dataToSend = {
            "idShort": "State",
            "modelType": "Property",
            "valueType": "xs:string",
            "value": state
        }
        
        requests.patch("http://" + AASURL + "/submodels/" + base64.b64encode(productDataPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/State", json = dataToSend)
        
        return jsonify({"message": "State updated with success"}), 200
                
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30
#     }
# }
@app.route('/getproductdata', methods=['POST'])
def GetProductData():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        
        productAssetPath = "http://zdm/aas/product_" + id
        
        productAsset = requests.get("http://" + AASURL + "/shells/" + base64.b64encode(productAssetPath.encode("utf-8")).decode('utf-8')).json()
                
        productDataPath = "http://zdm/submodels/product_" + id + "_data"
        
        productData = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productDataPath.encode("utf-8")).decode('utf-8')).json()
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        processData = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8')).json()
                
        productTypePath = str(productData["submodelElements"][2]["value"]["keys"][0]["value"])

        productType = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productTypePath.encode("utf-8")).decode('utf-8')).json()
                
        response = {
            "productInfo": productAsset,
            "productData": productData,
            "processData": processData,
            "productType": productType
        }
                
        return jsonify({"message": "Product data retrieved with success", "Response from Swagger": str(response)}), 200
                
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30
#     }
# }
@app.route('/getproducttype', methods=['POST'])
def GetProducType():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        
        productDataPath = "http://zdm/submodels/product_" + id + "_data"
        
        productData = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productDataPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/Type").json()

        print(productData)

        productTypePath = productData["value"]["keys"][0]["value"]

        print(productTypePath)

        productType = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productTypePath.encode("utf-8")).decode('utf-8') + "/submodel-elements/Name").json()
        
        print(productType)
        
        response = productType["value"]
        
        return jsonify({"message": "Product data retrieved with success", "Response from Swagger": response}), 200
                
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500


# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30
#     }
# }
@app.route('/getproducts', methods=['GET'])
def GetProducts():
    try:
        print("[INFO] Dados recebidos com sucesso.")
        
        allAssets = requests.get("http://" + AASURL + "/shells").json()["result"]
        
        productList = []
        
        for asset in allAssets:
            
            if asset["assetInformation"]["assetType"] == "Product" and asset["assetInformation"]["assetKind"] == "Instance":

                match = re.search(r"id (\d+)$", asset["description"][0]["text"])
                
                if match: productList.append({
                    match.group(1): asset["id"],
                })

        return jsonify({"message": "Product data retrieved with success", "Response from Swagger": str(productList)}), 200
                
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500


# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "timestamp": "coisas",
#         "temp_nozzle": "2graus",
#         "temp_target_nozzle": "1",
#         "temp_delta_nozzle": "2",
#         "pwm_nozzle": "3",
#         "temp_bed": "4",
#         "temp_target_bed": "5",
#         "temp_delta_bed": "6",
#         "pwm_bed": "7",
#         "X": "8",
#         "Y": "9",
#         "Z": "10",
#         "E": "11",
#         "speed_factor": "200",
#         "filename": "GAS"
#     }
# }
@app.route('/updateoperationvalues', methods=['POST'])
def UpdateOperationValues():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        def dataToSend(name, value): 
            return {
                "idShort": name,
                "modelType": "Property",
                "valueType": "xs:string",
                "value": value
            }
        
        keys = {
            "timestamp": "timestamp",
            "temp_nozzle": "nozzle_temp",
            "temp_target_nozzle": "nozzle_target",
            "temp_delta_nozzle": "nozzle_delta",
            "pwm_nozzle": "nozzle_pwm",
            "temp_bed": "bed_temp",
            "temp_target_bed": "bed_target",
            "temp_delta_bed": "bed_delta",
            "pwm_bed": "bed_pwm",
            "X": "X",
            "Y": "Y",
            "Z": "Z",
            "E": "extrusion_level",
            "speed_factor": "speed_factor",
            "filename": "filename"
        }

        responses = []

        for key in keys:
            value = str(data.get(key))
            
            valorNasAASs = keys[key]
            
            if (value != None and value != "None"):
                
                responses.append(requests.patch("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedOperations.Operation_Print.AssociatedValues." + valorNasAASs, json = dataToSend(name=valorNasAASs, value=value)))
        
        return jsonify({"message": "State updated with success", "responses": str(responses)}), 200
                
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30
#     }
# }
@app.route('/getoperationvalues', methods=['POST'])
def GetOperationValues():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        
        productDataPath = "http://zdm/submodels/process_product_" + id
        
        values = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productDataPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedOperations.Operation_Print.AssociatedValues").json()["value"]
        
        response = []
        
        for value in values:
            response.append({
                value["idShort"].lower(): str(value["value"])
            })
        
        return jsonify({"message": "State updated with success", "responses": response}), 200
                
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "inference": "wabisabi",
#         "qualitytest": "deu?",
#         "metrics": "muita metrica"
#     }
# }
@app.route('/addz1', methods=['POST'])
def AddZ1():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        inference = data.get("inference")
        qualitytest = data.get("qualitytest")
        metrics = data.get("metrics")
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        toReplace = [
            (REPLACE_ID, id),
            (REPLACE_INFERENCE_RESULT , inference),
            (REPLACE_QUALITYTEST_RESULT , qualitytest),
            # (REPLACE_INFERENCE_INPUTMETRICS , metrics)
            (REPLACE_INFERENCE_INPUTMETRICS , "")
        ]
        
        newQualityTestjSON = GerarAASJSON(TEMPLATE_QUALITYTESTS + TEMPLATE_Z1, toReplace)
        
        response = requests.post("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests", json = newQualityTestjSON)
        
        return jsonify({"message": "Z1 added with success", "Response from Swagger": str(response.json())}), 200
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "type": "Retangulo",
#         "inference": "wabisabi",
#         "qualitytest": "deu?",
#         "metrics": "muita metrica"
#     }
# }
@app.route('/addz4', methods=['POST'])
def AddZ4():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        producttype = data.get("type")
        inference = data.get("inference")
        qualitytest = data.get("qualitytest")
        metrics = data.get("metrics")
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        toReplace = [
            (REPLACE_ID, id),
            (REPLACE_INFERENCE_TYPE, "z4"),
            (REPLACE_PRODUCT_TYPE, producttype),
            (REPLACE_INFERENCE_RESULT , inference),
            (REPLACE_QUALITYTEST_RESULT , qualitytest),
            # (REPLACE_INFERENCE_INPUTMETRICS , metrics)
            (REPLACE_INFERENCE_INPUTMETRICS , "")
        ]
        
        newQualityTestjSON = GerarAASJSON(TEMPLATE_QUALITYTESTS + TEMPLATE_Z4, toReplace)
        
        response = requests.post("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests", json = newQualityTestjSON)
        
        return jsonify({"message": "Z4 added with success", "Response from Swagger": str(response.json())}), 200
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "type": "Retangulo",
#         "qualitytest": "SAUCY",
#         "valorlargura": "2",
#         "valorcomprimento": "3",
#         "valoraltura": "4"
#     }
# }
@app.route('/addmeasurements', methods=['POST'])
def AddMeasurements():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        type = data.get("type")
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        if(type == "Retangulo" or type == "Quadrado"):
            
            qualitytest = data.get("qualitytest")
            valorlargura = str(data.get("valorlargura"))
            valorcomprimento = str(data.get("valorcomprimento"))
            valoraltura = str(data.get("valoraltura"))
            
            toReplace = [
                (REPLACE_ID, id),
                (REPLACE_PRODUCT_TYPE , type),
                (REPLACE_QUALITYTEST_RESULT, qualitytest),
                (REPLACE_MEASUREMENTS_VALORTIPOLARGURA, TEMPLATE_MEASUREMENTS_VALORTIPO),
                (REPLACE_MEASUREMENTS_INCERTEZALARGURA, TEMPLATE_MEASUREMENTS_INCERTEZA),
                (REPLACE_MEASUREMENTS_VALORLARGURA, valorlargura),
                (REPLACE_MEASUREMENTS_VALORTIPOCOMPRIMENTO, TEMPLATE_MEASUREMENTS_VALORTIPO),
                (REPLACE_MEASUREMENTS_INCERTEZACOMPRIMENTO, TEMPLATE_MEASUREMENTS_INCERTEZA),
                (REPLACE_MEASUREMENTS_VALORCOMPRIMENTO, valorcomprimento),
                (REPLACE_MEASUREMENTS_VALORTIPOALTURA, TEMPLATE_MEASUREMENTS_VALORTIPO),
                (REPLACE_MEASUREMENTS_INCERTEZAALTURA, TEMPLATE_MEASUREMENTS_INCERTEZA),
                (REPLACE_MEASUREMENTS_VALORALTURA, valoraltura)
            ]
            
            measurementsQualityTest = GerarAASJSON(TEMPLATE_QUALITYTESTS + TEMPLATE_MEASUREMENTS_QUADRADO_RETANGULO, toReplace)
            
        else:
        
            qualitytest = data.get("qualitytest")
            valorlargura = str(data.get("valorlargura"))
            valorcomprimento = str(data.get("valorcomprimento"))
            
            toReplace = [
                
            ]
            
            measurementsQualityTest = GerarAASJSON(TEMPLATE_QUALITYTESTS + TEMPLATE_MEASUREMENTS_L, toReplace)
        
        response = requests.post("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests", json = measurementsQualityTest)
        
        return jsonify({"message": "Measurements added with success", "Response from Swagger": str(response.json())}), 200

    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30
#     }
# }
@app.route('/getmeasurements', methods=['POST'])
def GetMeasurements():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        qualityTests = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests").json()
        
        def check_test_exists(json_data):
            elements = json_data.get('value', [])            
            for element in elements:
                if element.get('idShort') == "Quality_Test_Measurements":
                    return True
            return False
        
        if check_test_exists(qualityTests): 
        
            measurementsCollection = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests.Quality_Test_Measurements.Operation_Check_Measurements.AssociatedMeasurements").json()
            
            response = []
            
            for measurement in measurementsCollection["value"]:
                
                response.append({
                    measurement["idShort"].lower():measurement["value"][2]["value"]
                })
        else:
            try:
                measurementsCollection = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests.Quality_Test_Z4.Operation_Check_Z4.Inference.Result").json()["value"]
            except:
                return jsonify({"message": "Product still printing"}), 200
            
            measurements = ast.literal_eval(measurementsCollection)
            
            response = []
            
            measurementsTemplates = ["Comprimento", "Largura", "Altura"]
            auxCounter = 0
            
            for measurement in measurements:
                response.append({
                    measurementsTemplates[auxCounter]:measurement
                })
                auxCounter+=1
        
        return jsonify({"message": "Measurements retrieved with success", "Response from Swagger": response}), 200
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "inferencetype": "z1"
#     }
# }
@app.route('/getmetrics', methods=['POST'])
def GetMetrics():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        inference = str(data.get("inferencetype"))
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        metrics = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests.Quality_Test_" + inference.upper() + ".Operation_Check_" + inference.upper() + ".Inference.AssociatedInputMetrics").json()["value"]
        
        print(metrics)
        
        return jsonify({"message": "Metrics retrieved with success", "Response from Swagger": str(metrics)}), 200
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "inferencetype": "z1",
#         "producttype": "quadrado",
#         "result": "RESULTADODAEXPLANATIONDEUMAINFERENCIA"
#     }
# }
@app.route('/addexplanation', methods=['POST'])
def AddExplanation():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        productType = data.get("producttype")
        inferenceType = data.get("inferencetype")
        result = str(data.get("result"))
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        type_aux = inferenceType
        
        if inferenceType == "z4":
            type_aux += "_" + productType.lower()
        
        toReplace = [
            (REPLACE_ID, id),
            (REPLACE_INFERENCE_TYPE, type_aux),
            (REPLACE_EXPLANATION_RESULT , result)
        ]

        explanationJSON = GerarAASJSON(TEMPLATE_QUALITYTESTS + TEMPLATE_EXPLANATION, toReplace)
        
        response = requests.post("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests.Quality_Test_" + inferenceType.upper() + ".Operation_Check_" + inferenceType.upper() + ".Inference.AssociatedExplanations", json=explanationJSON)
        
        return jsonify({"message": "Explanation added with success", "Response from Swagger": str(response.json())}), 200

    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

# TEMPLATE DE BODY
# {
#     "destination": "192.168.2.90:5011",
#     "msg": {
#         "id": 30,
#         "inferencetype": "z1"
#     }
# }
@app.route('/getexplanationdata', methods=['POST'])
def GetExplanationData():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")
        
        id = str(data.get("id"))
        inferenceType = data.get("inferencetype")
        
        productProcessPath = "http://zdm/submodels/process_product_" + id
        
        response = requests.get("http://" + AASURL + "/submodels/" + base64.b64encode(productProcessPath.encode("utf-8")).decode('utf-8') + "/submodel-elements/AssociatedQualityTests.Quality_Test_" + inferenceType.upper() + ".Operation_Check_" + inferenceType.upper() + ".Inference.AssociatedExplanations.Explanation_1.Result").json()["value"]
        
        return jsonify({"message": "Explanation results retrieved with success", "Response from Swagger": str(response)}), 200
        
    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)