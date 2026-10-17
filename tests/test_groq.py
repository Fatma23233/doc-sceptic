import requests

from doc_sceptic.config import Settings


settings = Settings()

print("Provider :", settings.llm_provider)
print("Model :", settings.llm_model)
print("URL :", settings.groq_base_url)
print("Clé présente :", bool(settings.llm_api_key))

url = (
    settings.groq_base_url.rstrip("/")
    + "/chat/completions"
)

response = requests.post(
    url,
    headers={
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": settings.llm_model,
        "messages": [
            {
                "role": "user",
                "content": "Réponds uniquement par OK.",
            }
        ],
        "temperature": 0,
    },
    timeout=120,
)

print("\nCode HTTP :", response.status_code)
print("Réponse :")
print(response.text)