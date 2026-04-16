"""
TranspoBot — Backend FastAPI (version déploiement stable)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx
import re
import json

app = FastAPI(title="TranspoBot API", version="1.0.0")

# CORS (important pour frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────
# CONFIG LLM (IA)
# ─────────────────────────────
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

# ─────────────────────────────
# PROMPT SYSTEM
# ─────────────────────────────
SYSTEM_PROMPT = """
Tu es TranspoBot, assistant intelligent d'une compagnie de transport.
Tu génères des réponses structurées et des requêtes SQL si nécessaire.
Réponds en JSON :
{"sql": "...", "explication": "..."}
"""

# ─────────────────────────────
# MODELE REQUEST
# ─────────────────────────────
class ChatMessage(BaseModel):
    question: str


# ─────────────────────────────
# IA (optionnelle)
# ─────────────────────────────
async def ask_llm(question: str) -> dict:
    if not LLM_API_KEY:
        return {"sql": None, "explication": "IA non configurée"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                "temperature": 0,
            },
            timeout=30,
        )

        content = response.json()["choices"][0]["message"]["content"]

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())

        return {"sql": None, "explication": "Réponse IA invalide"}


# ─────────────────────────────
# CHAT API
# ─────────────────────────────
@app.post("/api/chat")
async def chat(msg: ChatMessage):
    try:
        llm_response = await ask_llm(msg.question)

        return {
            "answer": llm_response.get("explication", ""),
            "sql": llm_response.get("sql"),
            "data": [],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────
# STATS (VERSION FIX POUR DEMO)
# ─────────────────────────────
@app.get("/api/stats")
def get_stats():
    return {
        "total_trajets": 7,
        "trajets_en_cours": 2,
        "vehicules_actifs": 5,
        "incidents_ouverts": 1,
        "recette_totale": 120000
    }


# ─────────────────────────────
# AUTRES ENDPOINTS SIMPLES
# ─────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "app": "TranspoBot"}


@app.get("/")
def home():
    return {
        "message": "TranspoBot API is running 🚀",
        "docs": "/docs"
    }