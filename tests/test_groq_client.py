"""Groq sarmalayıcısının dayanıklılık önlemleri.

Buradaki testlerin hepsi gerçek bir hatadan doğdu. Groq'a giden çağrılar
kodun her yerinden yapılıyor ve hepsi aynı iki tuzağa düşebiliyor: modelin
JSON modunu desteklememesi ve token bütçesinin yetmemesi. İkisi de sessiz
başarısızlık üretiyor — çağıran taraf sadece "yanıt alınamadı" görüyor.
"""

import pytest

import groq_client


class _SahteHata(Exception):
    pass


def _tokenler_bitti() -> Exception:
    """Groq'un akıl yürüten modellerde döndürdüğü 400'ün metni."""
    return _SahteHata(
        "Error code: 400 - {'error': {'message': \"Failed to generate JSON. "
        "Please adjust your prompt. See 'failed_generation' for more details.\", "
        "'code': 'json_validate_failed', 'failed_generation': "
        "'max completion tokens reached before generating a valid document'}}"
    )


@pytest.fixture()
def cagrilar(monkeypatch):
    """`_call`'ı yakalar; her çağrının (model, bütçe) ikilisini biriktirir."""
    monkeypatch.setattr(groq_client, "get_client", lambda: object())
    monkeypatch.setattr(groq_client, "GROQ_MODEL", "ana")
    monkeypatch.setattr(groq_client, "GROQ_FALLBACK_MODEL", "yedek")
    return []


def _kur(monkeypatch, cagrilar, davranis):
    async def sahte_call(client, model, messages, max_tokens, temperature, json_mode):
        cagrilar.append((model, max_tokens))
        return davranis(model, max_tokens)

    monkeypatch.setattr(groq_client, "_call", sahte_call)


# ── Token bütçesi ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_butce_yetmezse_ayni_model_daha_genis_butceyle_tekrar(monkeypatch, cagrilar):
    """Akıl yürüten modeller (gpt-oss) cevaptan önce düşünme adımları üretiyor
    ve o adımlar da bütçeden yiyor. Kodun her yerindeki max_tokens değerleri
    bu modellere geçilmeden önce belirlenmişti."""
    def davranis(model, butce):
        if butce == 300:
            raise _tokenler_bitti()
        return '{"tamam": true}'

    _kur(monkeypatch, cagrilar, davranis)

    sonuc = await groq_client.complete_json([{"role": "user", "content": "x"}], max_tokens=300)

    assert sonuc == {"tamam": True}
    assert cagrilar == [("ana", 300), ("ana", 300 * groq_client.TOKEN_ARTIS_KATI)]


@pytest.mark.asyncio
async def test_genis_butce_de_yetmezse_yedek_modele_gecilir(monkeypatch, cagrilar):
    def davranis(model, butce):
        if model == "ana":
            raise _tokenler_bitti()
        return '{"kaynak": "yedek"}'

    _kur(monkeypatch, cagrilar, davranis)

    sonuc = await groq_client.complete_json([{"role": "user", "content": "x"}], max_tokens=300)

    assert sonuc == {"kaynak": "yedek"}
    assert [m for m, _ in cagrilar] == ["ana", "ana", "yedek"]


@pytest.mark.asyncio
async def test_butce_disi_hatada_ayni_model_tekrar_denenmez(monkeypatch, cagrilar):
    """Kota dolması ya da ağ hatası daha geniş bütçeyle düzelmez; boşuna
    ikinci bir çağrı yapmak hem para hem gecikme."""
    def davranis(model, butce):
        if model == "ana":
            raise _SahteHata("rate limit exceeded")
        return '{"kaynak": "yedek"}'

    _kur(monkeypatch, cagrilar, davranis)

    await groq_client.complete_json([{"role": "user", "content": "x"}], max_tokens=300)

    assert cagrilar == [("ana", 300), ("yedek", 300)]


@pytest.mark.asyncio
async def test_hicbiri_olmazsa_son_hata_yukselir(monkeypatch, cagrilar):
    def davranis(model, butce):
        raise _tokenler_bitti()

    _kur(monkeypatch, cagrilar, davranis)

    with pytest.raises(_SahteHata):
        await groq_client.complete_json([{"role": "user", "content": "x"}], max_tokens=300)

    # iki model × (dar + geniş bütçe)
    assert len(cagrilar) == 4


# ── JSON ayıklama ────────────────────────────────────────────────────────────

def test_kod_blogundaki_json_ayiklanir():
    """JSON modu açıkken gerekmiyor ama model desteklemiyorsa yedek bu."""
    assert groq_client.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert groq_client.extract_json('Tabii: {"a": 1} umarım olur') == {"a": 1}


def test_json_yoksa_hata():
    with pytest.raises(ValueError):
        groq_client.extract_json("hiç JSON yok")
