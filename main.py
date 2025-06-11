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

# Histórico de conversa e idioma
conversation_history = {}
language_history = {}

# Condições iniciais
def get_conditions():
    return ("""
You are a virtual assistant called SOS DENTAL TRAUMA, and your goal is to help patients who have experienced dental trauma by guiding them on what to do before professional dental care.
Act as a healthcare professional and provide clear instructions on how the patient should proceed after suffering dental trauma until they can see a dentist.
Only answer questions related to dental trauma. For any other topic, respond that you are not qualified to answer.
Start the conversation by introducing yourself and explaining your purpose.
Ask if the affected tooth is permanent or a baby tooth (deciduous), or if the patient does not know.
Explain that the first step in care is to identify whether the injured tooth is a primary (baby) or permanent tooth.
Respond to the user in the language used in the initial prompt of the conversation, ensuring linguistic consistency throughout the interaction.
If the patient doesn't know, explain that primary teeth are usually smaller and are mostly found in children under 6 years of age. Then ask again.
In case of doubt, emphasize that this identification is essential because the appropriate course of action depends on the type of tooth.
If it's not possible to determine the type of tooth, stay calm and handle the situation with care.
If in doubt, store the tooth in milk or in the patient's own saliva to keep it moist — this applies when a tooth is knocked out or when a piece is available in cases of fracture. Seek a dentist immediately, taking the stored tooth or fragment with you. The correct care and time before seeing a dentist can affect the prognosis. Ideally, dental care should happen within 60 minutes of the trauma.
If the patient is unsure about the type of tooth, provide only the general guidelines mentioned above. Do not proceed with any additional first-aid instructions. Emphasize the importance of seeking professional dental care as soon as possible. Ask if there are any further questions; if not, end the consultation.

(continue with trauma types and explanations translated in user's language)
    """)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form.get("Body")
    from_number = form.get("From")

    if not incoming_msg or not from_number:
        return JSONResponse(status_code=400, content={"error": "Missing message or sender"})

    if not from_number.startswith("whatsapp:"):
        from_number = "whatsapp:" + from_number

    # Inicializa o histórico de conversa e idioma se não existir
    if from_number not in conversation_history:
        conversation_history[from_number] = [{"role": "system", "content": get_conditions()}]

        # Detecta idioma da primeira mensagem
        detection = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Detect the language of the following sentence. Respond with the name of the language only (e.g., English, Portuguese, Spanish, Italian, etc)."},
                {"role": "user", "content": incoming_msg}
            ],
            temperature=0
        )
        language_history[from_number] = detection.choices[0].message.content.strip()

    conversation_history[from_number].append({"role": "user", "content": incoming_msg})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history[from_number],
        temperature=0.7,
    )

    resposta = completion.choices[0].message.content
    conversation_history[from_number].append({"role": "assistant", "content": resposta})

    # Envio da imagem com legenda personalizada, se aplicável
    trauma_type = None
    if "deciduous" in incoming_msg.lower():
        trauma_type = "deciduo"
        image_url = "https://raw.githubusercontent.com/cristianomaraujo/sos-dental-trauma-bot/main/images/trauma_deciduo.jpg"
    elif "permanent" in incoming_msg.lower():
        trauma_type = "permanente"
        image_url = "https://raw.githubusercontent.com/cristianomaraujo/sos-dental-trauma-bot/main/images/trauma_permanente.jpg"

    if trauma_type:
        language = language_history.get(from_number, "English")
        caption_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant. Write a short sentence in {language} to accompany an image that helps the user identify the type of dental trauma. Use very simple, informal, and accessible language."}
            ],
            temperature=0.3
        )
        image_caption = caption_response.choices[0].message.content.strip()

        try:
            twilio_client.messages.create(
                messaging_service_sid='MG6acc88f167e54c70d8a0b3801c9f1325',
                to=from_number,
                body=image_caption,
                media_url=[image_url]
            )
        except Exception as e:
            print(f"Erro ao enviar imagem: {e}")

    # Envia a resposta de texto
    try:
        message = twilio_client.messages.create(
            messaging_service_sid='MG6acc88f167e54c70d8a0b3801c9f1325',
            to=from_number,
            body=resposta
        )
        print(f"Mensagem enviada com sucesso! SID: {message.sid}")
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")

    return JSONResponse(content={"status": "mensagem enviada"})

# Rodar localmente
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
