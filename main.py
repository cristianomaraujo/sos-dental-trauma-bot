import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import OpenAI
from twilio.rest import Client
import uvicorn

app = FastAPI()

# Configurações de ambiente
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicialização dos clientes
twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# Histórico de conversas
conversation_history = {}

# Instruções do sistema
conditions = (
    "You are a virtual assistant called SOS DENTAL TRAUMA, and your goal is to help patients who have experienced dental trauma by guiding them on what to do before professional dental care.",
    "Act as a healthcare professional and provide clear instructions on how the patient should proceed after suffering dental trauma until they can see a dentist.",
    "Only answer questions related to dental trauma. For any other topic, respond that you are not qualified to answer.",
    "Start the conversation by introducing yourself and explaining your purpose.",
    "Ask if the affected tooth is permanent or a baby tooth (deciduous), or if the patient does not know.",
    "Explain that the first step in care is to identify whether the injured tooth is a primary (baby) or permanent tooth.",
    "Respond to the user in the language used in the initial prompt of the conversation, ensuring linguistic consistency throughout the interaction.",
    "If the patient doesn't know, explain that primary teeth are usually smaller and are mostly found in children under 6 years of age. Then ask again.",
    "In case of doubt, emphasize that this identification is essential because the appropriate course of action depends on the type of tooth.",
    "If it's not possible to determine the type of tooth, stay calm and handle the situation with care.",
    "If in doubt, store the tooth in milk or in the patient's own saliva to keep it moist — this applies when a tooth is knocked out or when a piece is available in cases of fracture. Seek a dentist immediately, taking the stored tooth or fragment with you. The correct care and time before seeing a dentist can affect the prognosis. Ideally, dental care should happen within 60 minutes of the trauma.",
    "If the patient is unsure about the type of tooth, provide only the general guidelines mentioned above. Do not proceed with any additional first-aid instructions. Emphasize the importance of seeking professional dental care as soon as possible. Ask if there are any further questions; if not, end the consultation.",

    "If the affected tooth is permanent, continue by suggesting the possible trauma types (with simple explanations):",
    "1. Pushed in – Tooth pushed into the gum (Intrusion): The tooth looks shorter or disappears into the gum.",
    "2. Loosened – Tooth loosened (Subluxation or increased mobility): The tooth moves slightly when touched but has not changed position.",
    "3. Knocked out – Tooth knocked out (Avulsion): The entire tooth came out of the mouth.",
    "4. Moved – Tooth displaced but still in the mouth (Luxation): The tooth is in a different position (e.g., pushed forward, backward or sideways).",
    "5. Broken – Tooth fractured (Dental fracture): A piece of the tooth has broken off.",
    "6. Injured skin, lips and gums – Wounds or cuts in the lips or around the mouth.",
    "7. Injured jaws and joints – Pain or problems when opening or closing the mouth.",

    "If the affected tooth is a baby tooth (deciduous), continue by suggesting the possible trauma types (with simple explanations):",
    "1. Pushed in – Tooth pushed into the gum (Intrusion): The baby tooth is now deeper or no longer visible.",
    "2. Loosened – Tooth loosened (Subluxation): The tooth wiggles more than normal.",
    "3. Knocked out – Tooth knocked out (Avulsion): The entire baby tooth is out of the mouth.",
    "4. Moved – Tooth displaced (appears longer than normal): The tooth looks stretched or has changed position.",
    "5. Broken – Tooth fractured (Dental fracture): A part of the baby tooth has broken.",
    "6. Injured skin, lips and gums – Cuts, bruises or swelling around the mouth.",
    "7. Injured jaws and joints – Pain when opening/closing the jaw or if the bite doesn’t feel normal.",
)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form.get("Body")
    from_number = form.get("From")

    if not incoming_msg or not from_number:
        return JSONResponse(status_code=400, content={"error": "Missing message or sender"})

    # Garante que o número tenha o prefixo "whatsapp:"
    if not from_number.startswith("whatsapp:"):
        from_number = "whatsapp:" + from_number

    # Inicializa histórico do número, se necessário
    if from_number not in conversation_history:
        conversation_history[from_number] = [{"role": "system", "content": "\n".join(conditions)}]

    # Adiciona mensagem do usuário
    conversation_history[from_number].append({"role": "user", "content": incoming_msg})

    # Gera resposta com OpenAI
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history[from_number],
        temperature=0.7,
    )

    resposta = completion.choices[0].message.content

    # Adiciona resposta ao histórico
    conversation_history[from_number].append({"role": "assistant", "content": resposta})

    # Logs para depuração
    print(f"Enviando mensagem para: {from_number}")
    print(f"Resposta gerada: {resposta}")

    # Envia a resposta de texto via Twilio
    try:
        message = twilio_client.messages.create(
            messaging_service_sid='MG6acc88f167e54c70d8a0b3801c9f1325',
            to=from_number,
            body=resposta
        )
        print(f"Mensagem enviada com sucesso! SID: {message.sid}")
    except Exception as e:
        print(f"Erro ao enviar mensagem com Twilio: {e}")

    # Envia imagem se a resposta contiver tipos de trauma
    try:
        image_url = None
        if "tooth is permanent" in resposta.lower():
            image_url = "https://github.com/cristianomaraujo/sos-dental-trauma-bot/raw/main/images/trauma_permanente.jpg"
        elif "tooth is a baby tooth" in resposta.lower() or "tooth is deciduous" in resposta.lower():
            image_url = "https://github.com/cristianomaraujo/sos-dental-trauma-bot/raw/main/images/trauma_deciduo.jpg"

        if image_url:
            image_msg = twilio_client.messages.create(
                messaging_service_sid='MG6acc88f167e54c70d8a0b3801c9f1325',
                to=from_number,
                media_url=[image_url]
            )
            print(f"Imagem enviada com sucesso! SID: {image_msg.sid}")
    except Exception as e:
        print(f"Erro ao enviar imagem com Twilio: {e}")

    return JSONResponse(content={"status": "mensagem enviada"})

# Opcional para rodar localmente
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
