from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime, timedelta

app = FastAPI(title="BIN Lookup API", version="1.0")

# Simple in-memory cache (24 ghante)
CACHE = {}
CACHE_TTL = timedelta(hours=24)

def get_cached(bin_num):
    if bin_num in CACHE:
        data, ts = CACHE[bin_num]
        if datetime.now() - ts < CACHE_TTL:
            return data
        else:
            del CACHE[bin_num]
    return None

def set_cache(bin_num, data):
    CACHE[bin_num] = (data, datetime.now())

def format_response(bin_num, d):
    bank = d.get("bank", {}).get("name") or "UNKNOWN"
    country = d.get("country", {}).get("name") or "UNKNOWN"
    flag = d.get("country", {}).get("emoji") or "🌍"
    scheme = (d.get("scheme") or "UNKNOWN").upper()
    ctype = (d.get("type") or "UNKNOWN").upper()
    brand = (d.get("brand") or "UNKNOWN").upper()
    prepaid = d.get("prepaid")
    currency = d.get("country", {}).get("currency") or ""

    text = (
        "━━━━ Valid BIN ☂️ ━━━━\n\n"
        f"🍀 BIN ➜ {bin_num}\n"
        f"🍀 Scheme ➜ {scheme}\n"
        f"🍀 Type ➜ {ctype}\n"
        f"🍀 Brand ➜ {brand}\n"
        f"🍀 Bank ➜ {bank}\n"
        f"{flag} Country ➜ {country}\n"
        f"💳 Info ➜ {scheme} {ctype} {brand}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💲 Chat: @premiumxayu"
    )

    return {
        "success": True,
        "bin": bin_num,
        "scheme": scheme,
        "type": ctype,
        "brand": brand,
        "bank": bank,
        "country": country,
        "country_code": d.get("country", {}).get("alpha2"),
        "currency": currency,
        "prepaid": prepaid,
        "formatted": text
    }

@app.get("/")
def root():
    return {"status": "ok", "message": "BIN Lookup API running"}

@app.get("/bin/{bin_number}")
async def bin_lookup(bin_number: str):
    # Validation
    if not bin_number.isdigit():
        raise HTTPException(status_code=400, detail="BIN must contain only digits")
    if len(bin_number) < 6:
        raise HTTPException(status_code=400, detail="BIN must be at least 6 digits")
    
    bin_number = bin_number[:8]
    
    # Cache check
    cached = get_cached(bin_number)
    if cached:
        cached["cached"] = True
        return JSONResponse(cached)
    
    # Upstream call
    url = f"https://lookup.binlist.net/{bin_number}"
    headers = {"Accept-Version": "3"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10)
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Upstream service unreachable")
    
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"BIN {bin_number} not found")
    if resp.status_code == 429:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try later.")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Lookup failed")
    
    data = format_response(bin_number, resp.json())
    data["cached"] = False
    set_cache(bin_number, data)
    return JSONResponse(data)

@app.get("/health")
def health():
    return {"status": "healthy", "cached_bins": len(CACHE)}