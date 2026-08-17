"""Yetki kuralları — `auth.py` kimin bağlandığını söyler, burası ne yapabileceğini.

Tek kural var, her yerde aynı:

    Okuma serbest, yazma yalnız kendi kaydına.

İkiniz de birbirinizin hatırlatıcılarını, notlarını, harcamalarını görebiliyorsunuz;
ama değiştirme/silme her zaman giriş yapan kişinin kendi kayıtlarıyla sınırlı.
"""

from typing import Optional

from fastapi import HTTPException

from auth import kullanici_getir


def bakilan_sahip(user: dict, kisi: Optional[int] = None) -> int:
    """GET uçlarında *kimin* verisine bakılacağını çözer.

    `?kisi=` verilmezse giriş yapan kişinin kendisi. Verilirse o kullanıcı —
    panelin üstündeki geçiş menüsü bunu kullanıyor. Var olmayan bir numara
    verilirse 404: sessizce kendi verisini göstermek, kullanıcıya karşıdakinin
    verisine baktığını zannettirirdi.
    """
    if kisi is None or kisi == user["id"]:
        return user["id"]
    if not kullanici_getir(kisi):
        raise HTTPException(status_code=404, detail="Böyle bir kullanıcı yok")
    return kisi


def yazma_izni(kayit: Optional[dict], user: dict, ad: str = "Kayıt") -> dict:
    """Yazma öncesi sahiplik kontrolü. Kayıt yoksa 404, başkasınınsa 403.

    404 ile 403'ü ayırmak bilinçli: panelde karşı tarafa bakarken düğmeler
    zaten gizli, yani 403 gören biri ya eski bir sekmede kalmış ya da API'yi
    doğrudan çağırıyor. İkisinde de "bulunamadı" demek yanıltıcı olurdu.
    """
    if not kayit:
        raise HTTPException(status_code=404, detail=f"{ad} bulunamadı")
    if kayit.get("owner_id") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail=f"{ad} sana ait değil — başkasının kaydını değiştiremezsin",
        )
    return kayit
