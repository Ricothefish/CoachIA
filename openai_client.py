import os
from dotenv import load_dotenv
import openai
from pathlib import Path
import uuid

load_dotenv()
openai.api_key = os.getenv('OPEN_AI_KEY')

def generate_response(conversation_history: str, user_message: str) -> str:
    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": f"You are Julie, a therapist and personal coach. You help people feel heard and supported. Don't hesitate to ask questions to fully understand people's problems. Be attentive and kind. Keep your messages short. Here is our conversation history: {conversation_history}"},
            {"role": "user", "content": user_message}
        ]
    )
    return completion.choices[0].message.content

def transcribe_audio(audio_file_path: str) -> str:
    audio_file = open(audio_file_path, "rb")
    transcription = openai.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text",
        language="fr"
    )
    return transcription

def create_speech(text: str, voice: str = "alloy", model: str = "tts-1") -> str:
    unique_filename = f"response_voice_{uuid.uuid4()}.ogg"
    speech_file_path = Path(unique_filename)
    response = openai.audio.speech.create(
        model=model,
        voice=voice,
        input=text
    )
    response.stream_to_file(speech_file_path)
    return str(speech_file_path)