"""Groq çağrıları için ortak sarmalayıcı.

İki dayanıklılık önlemi:

1. **JSON modu.** `response_format={"type": "json_object"}` ile model geçerli JSON
   dönmeye zorlanır. Öncesinde yanıt bazen ``` bloğuna sarılı geliyordu ve bunu
   ayıklamak kırılgandı. Model bu parametreyi desteklemezse otomatik olarak
   düz metne düşülür (ayıklama yedeği duruyor).

2. **Model yedeği.** Ana model kota dolduğunda ya da geçici olarak yanıt
   vermediğinde her mesaj hataya düşüyordu. Artık `GROQ_FALLBACK_MODEL`
   devreye giriyor — daha küçük ama çalışır bir yanıt, hiç yanıt vermemekten iyi.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from groq import AsyncGroq

from logging_setup import get_logger

log = get_logger("prism.groq")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")


def get_client() -> AsyncGroq:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY ortam değişkeni ayarlanmamış")
    return AsyncGroq(api_key=key)


def _unsupported_json_mode(error: Exception) -> bool:
    """Hata 'bu model json modunu desteklemiyor' anlamına mı geliyor?"""
    text = str(error).lower()
    return "response_format" in text or "json_object" in text


# Akıl yürüten modeller (`gpt-oss` ailesi gibi) cevabı vermeden önce içeriden
# düşünme adımları üretiyor ve o adımlar da `max_tokens` bütçesinden yiyor.
# Bütçe dolunca JSON yarım kalıyor, Groq da 400 dönüyor:
#
#   json_validate_failed: max completion tokens reached before
#                         generating a valid document
#
# Kodun her yerindeki `max_tokens` değerleri bu modellere geçilmeden önce
# belirlenmişti; hepsi birden dar kaldı. Tek tek büyütmek yerine burada
# merkezî bir yedek var: bütçe yüzünden düşen çağrı, aynı modelle daha geniş
# bütçeyle bir kez daha deneniyor. Böylece yeni bir çağrı eklerken aynı tuzağa
# düşmek mümkün olmuyor.
TOKEN_ARTIS_KATI = 3


def _token_yetmedi(error: Exception) -> bool:
    return "max completion tokens" in str(error).lower()


def extract_json(raw: str) -> Dict[str, Any]:
    """Yanıttan JSON çıkarır. JSON modu açıkken gerekmez ama yedek olarak duruyor."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Yanıtta JSON bulunamadı")
    return json.loads(cleaned[start : end + 1])


async def _call(
    client: AsyncGroq,
    model: str,
    messages: List[Dict],
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> str:
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        try:
            response = await client.chat.completions.create(
                **kwargs, response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            if not _unsupported_json_mode(e):
                raise
            log.info("Model %s JSON modunu desteklemiyor, düz metin deneniyor", model)

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def complete_json(
    messages: List[Dict],
    max_tokens: int = 400,
    temperature: float = 0.1,
    models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Groq'a sorar ve JSON olarak çözümlenmiş sonucu döner.

    Ana model başarısız olursa yedek modele geçilir. İkisi de olmazsa son hata yükseltilir.
    """
    client = get_client()
    candidates = models or [m for m in (GROQ_MODEL, GROQ_FALLBACK_MODEL) if m]
    last_error: Optional[Exception] = None

    for index, model in enumerate(candidates):
        butce = max_tokens
        while True:
            try:
                raw = await _call(client, model, messages, butce, temperature, json_mode=True)
                parsed = extract_json(raw)
                if index > 0:
                    log.warning("Yanıt yedek modelden alındı: %s", model)
                return parsed
            except Exception as e:
                last_error = e
                # Bütçe yüzünden düştüyse aynı modele bir kez daha, daha geniş
                # bütçeyle şans ver — yedek model de aynı aileden olabilir ve
                # ona geçmek sorunu çözmez (nitekim çözmedi).
                if _token_yetmedi(e) and butce == max_tokens:
                    butce = max_tokens * TOKEN_ARTIS_KATI
                    log.info(
                        "Model %s bütçeyi doldurdu (akıl yürütme), %d token ile tekrar",
                        model, butce,
                    )
                    continue
                log.warning("Groq isteği başarısız (model=%s): %s: %s",
                            model, type(e).__name__, e)
                break

    raise last_error if last_error else RuntimeError("Groq'tan yanıt alınamadı")
