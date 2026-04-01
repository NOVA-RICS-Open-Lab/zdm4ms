import json
import base64

# --- Configuração ---
# Mude estes nomes se necessário
input_file = "b.txt"         # O ficheiro de onde ler (JSON com HTML, TXT com Base64, ou TXT com HTML)
output_file = "explanation_output.html" # O ficheiro .html final a ser criado
jsonobject = "explanationpage"  # A chave JSON que contém o HTML/Base64
# --------------------

input_content_str = ""
html_content = ""
is_base64 = False

print(f"A ler de '{input_file}'...")

try:
    with open(input_file, 'r', encoding='utf-8') as f:
        input_content_str = f.read()

    # 1. Tentar ler o ficheiro como JSON (como o seu 'ada.html')
    try:
        data = json.loads(input_content_str)
        if isinstance(data, dict) and jsonobject in data:
            print(f"Ficheiro JSON detectado. A extrair a chave {jsonobject}")
            # Assumir que o conteúdo dentro do JSON pode ser HTML direto ou Base64
            potential_html = data[jsonobject]
            # Tentativa heurística: Se começa com <html ou <!DOCTYPE, provavelmente é HTML
            if potential_html.strip().startswith('<html') or potential_html.strip().startswith('<!DOCTYPE'):
                 html_content = potential_html
                 print(f"Conteúdo da {jsonobject} parece ser HTML direto.")
            else:
                 # Se não parecer HTML, assumir que é Base64
                 print(f"Conteúdo da {jsonobject} não parece HTML, a tentar descodificar como Base64...")
                 input_content_str = potential_html # Usar este conteúdo para descodificação
                 is_base64 = True
        else:
            print(f"Ficheiro JSON detectado, mas sem chave {jsonobject} ou formato inválido. A tentar ler o ficheiro inteiro como Base64...")
            is_base64 = True # Tentar descodificar o ficheiro inteiro

    except json.JSONDecodeError:
        # 2. Se falhar, não é JSON. Assumir que é um ficheiro de texto simples.
        # Pode conter HTML direto ou Base64.
        print("Ficheiro não é JSON.")
        # Tentativa heurística: Se NÃO começa com <html ou <!DOCTYPE, assumir Base64
        if not input_content_str.strip().startswith('<html') and not input_content_str.strip().startswith('<!DOCTYPE'):
             print("A assumir que o conteúdo do ficheiro é Base64...")
             is_base64 = True
        else:
             print("A assumir que o conteúdo do ficheiro é HTML direto.")
             html_content = input_content_str

    # 3. Se marcámos como Base64, tentar descodificar
    if is_base64:
        try:
            # Remover possíveis espaços/newlines extra antes de descodificar
            base64_bytes = input_content_str.strip().encode('utf-8')
            html_bytes = base64.b64decode(base64_bytes)
            html_content = html_bytes.decode('utf-8')
            print("Descodificação Base64 bem-sucedida.")
        except base64.binascii.Error as e:
            print(f"Erro ao descodificar Base64: {e}")
            print("A guardar o conteúdo original, pois pode não ser Base64.")
            html_content = input_content_str # Falha na descodificação, guardar como está
        except Exception as e:
            print(f"Erro inesperado durante a descodificação Base64: {e}")
            html_content = f"<html><body>Erro ao descodificar: {e}</body></html>"

except FileNotFoundError:
    print(f"Erro: Ficheiro de entrada '{input_file}' não encontrado.")
    html_content = f"<html><body>Erro: Ficheiro '{input_file}' não encontrado.</body></html>"
    
except Exception as e:
    print(f"Ocorreu um erro inesperado ao ler o ficheiro '{input_file}': {e}")
    html_content = f"<html><body>Erro ao ler ficheiro: {e}</body></html>"

# 4. Se tivermos conteúdo HTML (original ou descodificado), guardá-lo
if html_content:
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\nSucesso! O HTML foi guardado em '{output_file}'.")
        print(f"Pode abrir o ficheiro '{output_file}' no seu browser.")
    except IOError as e:
        print(f"\nErro: Não foi possível guardar em '{output_file}'. {e}")
else:
    print("\nOperação falhou. Nenhum conteúdo HTML foi encontrado ou extraído para guardar.")

