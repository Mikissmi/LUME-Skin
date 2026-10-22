import json
import urllib.request

url = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=-29.94&longitude=-50.99"
    "&current=uv_index&timezone=America/Sao_Paulo"
)

with urllib.request.urlopen(url, timeout=5) as resposta:
    dados = json.load(resposta)

print("Resposta completa:", dados)
print("UV arredondado:", round(dados["current"]["uv_index"]))