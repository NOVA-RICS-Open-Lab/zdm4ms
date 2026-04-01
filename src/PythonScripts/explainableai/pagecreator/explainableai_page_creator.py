import os
import traceback
import base64
import gradio as gr
import ollama
import requests

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn

import json

import threading

PORT = int(os.getenv("PORT", 5015))
OLLAMAADRESS = os.getenv("OLLAMAADDRESS", "http://192.168.250.220:11434")
OLLAMAMODEL = os.getenv("OLLAMAMODEL", "llama3:8b")
MYADRESS = "http://" + os.getenv("ADDRESS", "192.168.2.90")

CONTEXTZ1 = "You are an interpreter of LIME explanations. LIME visualizes how specific inputs influence a model's prediction. The output displays the predicted value on a scale on the left, while the right side lists features and their contributions to the result. Your task is to provide concise Portugal Portuguese descriptions explaining why the model generated a specific result, relying on the feature weights. The model in question is a classification model that predicts an object's quality at the end of the printing process (OK or NOK) based on a 3D printer's operational parameters, EVERYWHERE you see a OK its a NOK and an NOK its an OK, they are switched, so change EVERYTHING yourself. Here you have the lime explainer output with all the features, predictions and weights: "
CONTEXTZ4 = "You are an interpreter of LIME explanations. LIME visualizes how specific inputs influence a model's prediction. The output displays the predicted value on a scale on the left, while the right side lists features and their contributions to the result. Your task is to provide concise Portugal Portuguese descriptions explaining why the model generated a specific result, relying on the feature weights. The model in question is a regression model that predicts an object's dimensions based on a 3D printer's operational parameters. Here you have the lime explainer output with all the features, predictions and weights: "

# --------------------------------------- // --------------------------------------- #
# Ollama
# --------------------------------------- // --------------------------------------- #

class OllamaChatbot:
    
    def __init__(self):
        
        try:
            self.client = ollama.Client(host=OLLAMAADRESS)
            # print(self.client.list())
            print(f"[OllamaChatbot] New instance created successfully")
        except Exception as e:
            print(f"[OllamaChatbot] ERROR: Could not connect to {OLLAMAADRESS}. {e}")
            raise

    def getExplanationDescription(self, limeExplanation:str):

        request = self.context + " Here you have a lime explanation: " + limeExplanation + " Describe it, focusing on the most impactful features to the predicted values and what they meanc physically, talk about every measurement, with a maximum of 300 characters in Portugal Portuguese. Remember to only return the description and dont write like \"**Comprimento**: something\", do a coerent text."
        
        try:
            response = self.client.chat(model=OLLAMAMODEL, messages=[{'role': 'system', 'content': request}])
            return response["message"]["content"]
        except Exception as e:
            return f"[OllamaChatbot] Error: {e}"

    def reconfigure(self, context):
        
        self.context = context

    def chat(self, newMessage:str, history:list):

        chatMessages = []

        for userMsg, chatBotMsg in history:
            chatMessages.append({"role": "user", "content": userMsg})
            chatMessages.append({"role": "explainer", "content": chatBotMsg})
        
        chatMessages.append({"role": "user", "content": newMessage})

        chatData = [{'role': 'system', 'content': self.context}] + chatMessages
        
        try:
            response = self.client.chat(model=OLLAMAMODEL, messages=chatData)

            history.append([newMessage, response["message"]["content"]])

            return "", history
        except Exception as e:
            return "", history

chatBot = OllamaChatbot()

# --------------------------------------- // --------------------------------------- #
# Gradio
# --------------------------------------- // --------------------------------------- #

def run_gradio_app():
    with gr.Blocks(fill_height=True) as interface:
        gr.Markdown("## ChatBot")
                    
        chatbot_display = gr.Chatbot(
            scale = 1,
            bubble_full_width = False
        )
        with gr.Row():
            msg_box = gr.Textbox(
                label="Perguntar...", 
                placeholder="Explanation Chat",
                scale = 4,
                container = False
            )
            submit_btn = gr.Button(
                "Submeter",
                scale = 1,
                variant = "primary"
            )

        submit_btn.click(
            fn=chatBot.chat,
            inputs=[msg_box, chatbot_display],
            outputs=[msg_box, chatbot_display]
        )
        msg_box.submit(
            fn=chatBot.chat,
            inputs=[msg_box, chatbot_display],
            outputs=[msg_box, chatbot_display]
        )
    interface.launch(server_port=7860, server_name="0.0.0.0")

threading.Thread(target=run_gradio_app, daemon=True).start()

# --------------------------------------- // --------------------------------------- #
# FastAPI
# --------------------------------------- // --------------------------------------- #
app = FastAPI()

template = Jinja2Templates(directory="templates")

@app.post('/setup')
async def setup(request: Request):
    try:
        data = await request.json()
        print("[INFO] Dados recebidos com sucesso.")

        # if not isinstance(data, dict) and "explanation" in data:
        #     return JSONResponse(content={"error": "Esperado um JSON com explanation"}, status_code=400)
    
        explanation_html_raw = data["explanationhtml"]
        base64_bytes = explanation_html_raw.strip().encode('utf-8')
        html_bytes = base64.b64decode(base64_bytes)
        explanation_html = html_bytes.decode('utf-8')
        print("[INFO] Descodificação Base64 bem-sucedida.")
        
        explanation_data_dict = json.dumps(data["explanationdict"], ensure_ascii=False, indent=2)

        print("[INFO] A reconfigurar ChatBot")
        if(data["predict_type"] == "Z=4"):
            context = CONTEXTZ4 + explanation_data_dict
        else :
            context = CONTEXTZ1 + explanation_data_dict
        
        chatBot.reconfigure(context=context)
        print("[INFO] ChatBot reconfigurado")
        
        print("[INFO] A ir buscar description ao chatbot...")
        description = chatBot.getExplanationDescription(explanation_data_dict)
        print("[INFO] Description obtida: ", description)
        
        response = template.TemplateResponse(
            'index.html',
            {
                "request": request,
                "title": "Explaining " + data["predict_type"] + " inference with result: " + data["result"] + " for product: " + data["type"] + " with id: " + data["id"],
                "text": description,
                "lime_html": explanation_html,
                "chatbot": MYADRESS + ":7860"
            }
        ).body.decode('utf-8')
        
        print("[INFO] A enviar template")

        return JSONResponse(content={"explanationpage": base64.b64encode(response.encode('utf-8')).decode('utf-8')}, status_code=200)

    except Exception as e:
        traceback.print_exc()
        print(f"[ERRO] {e}")
        return JSONResponse(content={"error": str(e)}, status_code = 500)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=PORT)
