"""
TranspoBot — Backend FastAPI + Interface
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import httpx
import re
import json

app = FastAPI(title="TranspoBot API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────
# CONFIG IA (optionnel)
# ─────────────────────────────
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = "https://api.openai.com/v1"

SYSTEM_PROMPT = """
Tu es TranspoBot. Réponds en JSON :
{"sql": "...", "explication": "..."}
"""

# ─────────────────────────────
# PAGE D'ACCUEIL API
# ─────────────────────────────
@app.get("/")
def home():
    return {
        "message": "TranspoBot API is running 🚀",
        "docs": "/docs",
        "ui": "/ui"
    }

# ─────────────────────────────
# INTERFACE FRONTEND
# ─────────────────────────────
@app.get("/ui")
def ui():
    return FileResponse("index.html")

# ─────────────────────────────
# HEALTH
# ─────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "app": "TranspoBot"}

# ─────────────────────────────
# STATS (DEMO FIXÉ)
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
# CHAT IA (optionnel)
# ─────────────────────────────
async def ask_llm(question: str):
    if not LLM_API_KEY:
        return {"sql": None, "explication": "IA non configurée"}

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                "temperature": 0
            }
        )

        content = r.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())

        return {"sql": None, "explication": "Erreur IA"}

# ─────────────────────────────
# CHAT API
# ─────────────────────────────
@app.post("/api/chat")
async def chat(msg: dict):
    try:
        res = await ask_llm(msg["question"])
        return {
            "answer": res.get("explication"),
            "sql": res.get("sql"),
            "data": []
        }
    except Exception as e:
        return {"error": str(e)}