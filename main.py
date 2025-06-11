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

# Histórico de conversas e tipo de dente por número
conversation_history = {}
dente_tipo_usuario = {}

# Condições iniciais
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

    "If the affected tooth is permanent, continue by suggesting the possible trauma types:",
    "1. Pushed in – Tooth pushed into the gum (Intrusion): the tooth enters the gum and seems shorter.",
    "2. Loosened – Tooth loosened (Subluxation or increased mobility without displacement): it becomes mobile without changing position.",
    "3. Knocked out – Tooth knocked out (Avulsion): the tooth came out completely.",
    "4. Moved – Tooth displaced but still in the mouth (Luxation): the tooth moved from its position but is still there.",
    "5. Broken – Tooth fractured (Dental fracture): the tooth chipped or broke.",
    "6. Injured skin, lips and gums – Injuries to skin, lips, and gums: injuries in soft tissues around the mouth.",
    "7. Injured jaws and joints – Jaw and joint injuries: pain or trauma in jaw or TMJ area.",
    "Remember to translate the terms into the user's language.",
    "Add the marker [[TRAUMA_IMAGE_PERMANENT]] at the end.",

    "If the affected tooth is a baby tooth (deciduous), continue by suggesting the possible trauma types:",
    "1. Pushed in – Tooth pushed into the gum (Intrusion): baby tooth enters the gum.",
    "2. Loosened – Tooth loosened (Subluxation): mobile without falling.",
    "3. Knocked out – Tooth knocked out (Avulsion): came out entirely.",
    "4. Moved – Tooth displaced (appears longer than normal): moved outwards.",
    "5. Broken – Tooth fractured (Dental fracture): a piece broke off.",
    "6. Injured skin, lips and gums – Injuries to soft tissues of the mouth.",
    "7. Injured jaws and joints – Injury to jawbone or TMJ.",
    "Remember to translate the terms into the user's language.",
    "Add the marker [[TRAUMA_IMAGE_DECIDUOUS]] at the end."
)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form.get("Body")
    from_number = form.get("From")

    if not incoming_msg or not from_number:
        return JSONResponse(status_code=400, content={"error": "Missing message or sender"})

    if not from_number.startswith("whatsapp:"):
        from_number = "whatsapp:" + from_number

    if from_number not in conversation_history:
        conversation_history[from_number] = [{"role": "system", "content": "\n".join(conditions)}]
        dente_tipo_usuario[from_number] = None

    msg_lower = incoming_msg.lower()
    if any(word in msg_lower for word in ["permanent", "permanente"]):
        dente_tipo_usuario[from_number] = "permanente"
    elif any(word in msg_lower for word in ["baby", "deciduous", "decíduo", "deciduo", "leite", "infantil"]):
        dente_tipo_usuario[from_number] = "deciduo"

    conversation_history[from_number].append({"role": "user", "content": incoming_msg})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history[from_number],
        temperature=0.7,
    )
    resposta = completion.choices[0].message.content

    # Remove o marcador invisível antes de enviar ao usuário
    resposta_limpa = resposta.replace("[[TRAUMA_IMAGE_PERMANENT]]", "").replace("[[TRAUMA_IMAGE_DECIDUOUS]]", "")
    conversation_history[from_number].append({"role": "assistant", "content": resposta})

    try:
        twilio_client.messages.create(
            messaging_service_sid='MG6acc88f167e54c70d8a0b3801c9f1325',
            to=from_number,
            body=resposta_limpa
        )
    except Exception as e:
        print(f"Erro ao enviar mensagem principal: {e}")

    # Verifica o marcador invisível e envia imagem apropriada
    if "[[TRAUMA_IMAGE_PERMANENT]]" in resposta:
        image_url = "https://github.com/cristianomaraujo/sos-dental-trauma-bot/raw/main/images/trauma_permanente.jpg"
    elif "[[TRAUMA_IMAGE_DECIDUOUS]]" in resposta:
        image_url = "https://github.com/cristianomaraujo/sos-dental-trauma-bot/raw/main/images/trauma_deciduo.jpg"
    else:
        image_url = None

    if image_url:
        try:
            twilio_client.messages.create(
                messaging_service_sid='MG6acc88f167e54c70d8a0b3801c9f1325',
                to=from_number,
                media_url=[image_url]
            )
        except Exception as e:
            print(f"Erro ao enviar imagem: {e}")

    return JSONResponse(content={"status": "mensagem enviada"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
