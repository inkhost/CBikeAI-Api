import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ===== Configuração (vem das variáveis de ambiente do Render) =====
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "registros")

app = FastAPI(title="CBikeAI API")

# Libera acesso do seu dashboard/app pra chamar essa API sem bloqueio de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _headers():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL ou SUPABASE_KEY não configurados nas variáveis de ambiente."
        )
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def buscar_registros(limite: int = 20):
    """Busca os últimos N registros no Supabase, do mais recente pro mais antigo."""
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    params = {
        "select": "*",
        "order": "id.desc",
        "limit": str(limite),
    }
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Supabase: {resp.text}")
    return resp.json()


@app.get("/")
def raiz():
    return {"status": "online", "servico": "CBikeAI API"}


@app.get("/fadiga/ultimo")
def fadiga_ultimo():
    """Analisa o BPM mais recente e retorna um alerta simples de fadiga."""
    registros = buscar_registros(limite=1)
    if not registros:
        raise HTTPException(status_code=404, detail="Nenhum registro encontrado.")

    ultimo = registros[0]
    bpm = ultimo.get("batimentos_cardiacos")

    if bpm is None:
        alerta = "sem_dados"
        mensagem = "Sem leitura de batimentos disponível."
    elif bpm > 160:
        alerta = "critico"
        mensagem = "Frequência cardíaca muito alta. Considere parar e descansar."
    elif bpm > 140:
        alerta = "atencao"
        mensagem = "Frequência cardíaca elevada. Reduza o ritmo."
    elif bpm < 40 and bpm > 0:
        alerta = "atencao"
        mensagem = "Frequência cardíaca muito baixa detectada. Verifique o sensor ou seu estado."
    else:
        alerta = "normal"
        mensagem = "Frequência cardíaca dentro do esperado."

    return {
        "bpm": bpm,
        "latitude": ultimo.get("latitude"),
        "longitude": ultimo.get("longitude"),
        "alerta": alerta,
        "mensagem": mensagem,
    }


@app.get("/fadiga/tendencia")
def fadiga_tendencia(quantidade: int = 20):
    """Analisa a tendência dos últimos batimentos para detectar fadiga sustentada."""
    registros = buscar_registros(limite=quantidade)
    bpms = [r["batimentos_cardiacos"] for r in registros if r.get("batimentos_cardiacos")]

    if len(bpms) < 3:
        return {"alerta": "sem_dados", "mensagem": "Dados insuficientes para análise de tendência."}

    media = sum(bpms) / len(bpms)
    # bpms vem do mais recente pro mais antigo; pega os 3 mais recentes
    recentes = bpms[:3]
    media_recente = sum(recentes) / len(recentes)

    if media_recente > media * 1.15:
        alerta = "fadiga_crescente"
        mensagem = "Batimentos subindo em relação à média recente. Possível início de fadiga."
    else:
        alerta = "estavel"
        mensagem = "Batimentos estáveis."

    return {
        "media_geral": round(media, 1),
        "media_recente": round(media_recente, 1),
        "amostras": len(bpms),
        "alerta": alerta,
        "mensagem": mensagem,
    }
