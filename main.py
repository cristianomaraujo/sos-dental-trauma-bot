
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
    "1. Pushed in – Tooth pushed into the gum (Intrusion)",
    "2. Loosened – Tooth loosened (Subluxation or increased mobility without displacement)",
    "3. Knocked out – Tooth knocked out (Avulsion)",
    "4. Moved – Tooth displaced but still in the mouth (Luxation)",
    "5. Broken – Tooth fractured (Dental fracture)",
    "6. Injured skin, lips and gums – Injuries to skin, lips, and gums",
    "7. Injured jaws and joints – Jaw and joint injuries",
    "Remember to translate the terms into the user's language.",
    "If the affected tooth is a baby tooth (deciduous), continue by suggesting the possible trauma types:",
    "1. Pushed in – Tooth pushed into the gum (Intrusion)",
    "2. Loosened – Tooth loosened (Subluxation)",
    "3. Knocked out – Tooth knocked out (Avulsion)",
    "4. Moved – Tooth displaced (appears longer than normal)",
    "5. Broken – Tooth fractured (Dental fracture)",
    "6. Injured skin, lips and gums – Injuries to skin, lips, and gums",
    "7. Injured jaws and joints – Jaw and joint injuries",
    "Remember to translate the terms into the user's language."
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

    conversation_history[from_number].append({"role": "user", "content": incoming_msg})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history[from_number],
        temperature=0.7,
    )

    resposta = completion.choices[0].message.content
    conversation_history[from_number].append({"role": "assistant", "content": resposta})

    print(f"Enviando mensagem para: {from_number}")
    print(f"Resposta gerada: {resposta}")

    media_url = None
    lower_msg = incoming_msg.lower()

    if "deciduous" in lower_msg or "baby tooth" in lower_msg or "dente de leite" in lower_msg:
        media_url = "https://raw.githubusercontent.com/cristianomaraujo/sos-dental-trauma-bot/main/images/trauma_deciduo.jpg"
    elif "permanent" in lower_msg or "permanente" in lower_msg:
        media_url = "https://raw.githubusercontent.com/cristianomaraujo/sos-dental-trauma-bot/main/images/trauma_permanente.jpg"

    try:
        message = twilio_client.messages.create(
            messaging_service_sid='MG6acc88f167e54c70d8a0b3801c9f1325',
            to=from_number,
            body=resposta,
            media_url=[media_url] if media_url else None
        )
        print(f"Mensagem enviada com sucesso! SID: {message.sid}")
    except Exception as e:
        print(f"Erro ao enviar mensagem com Twilio: {e}")

    return JSONResponse(content={"status": "mensagem enviada"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
