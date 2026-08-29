package com.eyup.prism.data.api

import com.google.gson.annotations.SerializedName

// Backend JSON alanlarıyla birebir eşleşir (snake_case → @SerializedName)
//
// ⚠️ Burada yalnız SENSÖR yolunun modelleri var. Hatırlatıcı/not/harcama
// modelleri, uygulama sensöre indirgenirken silindi — o ekranların işini
// artık web paneli yapıyor (bkz. CLAUDE.md "Android: sensör uygulaması").

/** Banka bildiriminin sunucuya gönderilen hâli */
data class NotificationIngest(
    @SerializedName("package_name") val packageName: String,
    val title: String = "",
    val text: String,
    @SerializedName("posted_at") val postedAt: String? = null,
    val source: String = "notification",
)

/**
 * Kaydedilen harcamanın yakalama kaydında gösterilen kadarı.
 *
 * Sunucu tam kaydı döndürüyor; burada yalnız "Son Yakalananlar" listesinde
 * yazan iki alan tutuluyor ("273.90 TL - yemek"). Gson bilmediği alanları
 * sessizce atlıyor, o yüzden eksik tutmak güvenli.
 */
data class CapturedExpense(
    val amount: Double,
    val category: String = "",
)

/** Sunucunun cevabı — harcama değilse recorded=false döner, bu hata değildir */
data class IngestResult(
    val recorded: Boolean,
    val reason: String = "",
    val expense: CapturedExpense? = null,
)

data class HealthResponse(val status: String, val service: String)
