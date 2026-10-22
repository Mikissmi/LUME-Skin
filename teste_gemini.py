import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

pergunta = ("Qual é o índice UV atual em Porto Alegre, RS, Brasil? "
            "Responda apenas com um número inteiro, sem nenhum texto.")

modelos = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
]

for modelo in modelos:
    try:
        r = client.models.generate_content(
            model=modelo,
            contents=pergunta,
            config=types.GenerateContentConfig(
                tools=[types.Tool(googleSearch=types.GoogleSearch())],
            ),
        )
        print(f"{modelo}: OK -> {r.text}")
    except Exception as e:
        print(f"{modelo}: FALHOU -> {str(e)[:110]}")