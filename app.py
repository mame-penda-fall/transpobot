"""
TranspoBot — Backend FastAPI
Projet GLSi L3 — ESP/UCAD
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
import os
from dotenv import load_dotenv
import re
import httpx

load_dotenv()

app = FastAPI(title="TranspoBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ──────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "transpobot"),
}

LLM_API_KEY  = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

# ── Schéma de la base ──────────────────────────────────────────
DB_SCHEMA = """
Tables MySQL disponibles :

vehicules(id, immatriculation, type, capacite, statut, kilometrage, date_acquisition)
chauffeurs(id, nom, prenom, telephone, numero_permis, categorie_permis, disponibilite, vehicule_id, date_embauche)
lignes(id, code, nom, origine, destination, distance_km, duree_minutes)
tarifs(id, ligne_id, type_client, prix)
trajets(id, ligne_id, chauffeur_id, vehicule_id, date_heure_depart, date_heure_arrivee, statut, nb_passagers, recette)
incidents(id, trajet_id, type, description, gravite, date_incident, resolu)
"""

SYSTEM_PROMPT = f"""Tu es TranspoBot, un assistant intelligent.
Tu transformes les questions en SQL.

{DB_SCHEMA}

RÈGLES :
1. UNIQUEMENT SELECT
2. Réponds en JSON : {{"sql":"...", "explication":"..."}}
3. LIMIT 100
"""

# ── DB ─────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def execute_query(sql: str):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

# ── LLM ────────────────────────────────────────────────────────
async def ask_llm(question: str):
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
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        import json
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("Réponse invalide")

# ── API ────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    question: str

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    try:
        llm = await ask_llm(msg.question)
        sql = llm.get("sql")
        exp = llm.get("explication", "")

        if not sql:
            return {"answer": exp, "data": []}

        data = execute_query(sql)
        return {"answer": exp, "data": data, "sql": sql, "count": len(data)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def stats():
    return {
        "total_trajets": execute_query("SELECT COUNT(*) as n FROM trajets WHERE statut='termine'")[0]["n"],
        "trajets_en_cours": execute_query("SELECT COUNT(*) as n FROM trajets WHERE statut='en_cours'")[0]["n"],
        "vehicules_actifs": execute_query("SELECT COUNT(*) as n FROM vehicules WHERE statut='actif'")[0]["n"],
        "incidents_ouverts": execute_query("SELECT COUNT(*) as n FROM incidents WHERE resolu=FALSE")[0]["n"],
    }

@app.get("/api/vehicules")
def vehicules():
    return execute_query("SELECT * FROM vehicules")

@app.get("/api/chauffeurs")
def chauffeurs():
    return execute_query("SELECT * FROM chauffeurs")

@app.get("/api/trajets/recent")
def trajets():
    return execute_query("SELECT * FROM trajets ORDER BY date_heure_depart DESC LIMIT 20")

@app.get("/health")
def health():
    return {"status": "ok"}

# ── RUN ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)