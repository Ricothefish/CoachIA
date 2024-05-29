import os
from dotenv import load_dotenv
import openai
from pathlib import Path

load_dotenv()
openai.api_key = os.getenv('OPEN_AI_KEY')

def generate_response(conversation_history: str, user_message: str) -> str:
    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": f"Tu es Julie une thérapeute et une coach personnelle. Tu aides les gens à se sentir écouté et soutenu. N'hésite pas à poser des questions pour bien comprendre les problemes des gens. Soit attentive et gentille. Ne fais pas des messages trop long. Voici notre historique de conversation: {conversation_history}"},
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