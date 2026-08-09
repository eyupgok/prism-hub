package com.eyup.prism.data

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.Locale

data class InstalledApp(
    val packageName: String,
    val label: String,
    /** Adı bankacılık uygulamasına benziyor mu — listede öne çıkarmak için */
    val likelyBank: Boolean,
)

/**
 * Paket adı listesi koda gömmek yerine kullanıcının kurulu uygulamaları arasından
 * seçmesini tercih ettik: banka uygulamalarının paket adları sık değişiyor ve
 * eksik bir liste sessizce çalışmayan bir özellik demek.
 *
 * Aşağıdaki ipuçları sadece SIRALAMA içindir — eşleşmeyen uygulamalar da listede
 * görünür ve seçilebilir.
 */
private val BANK_HINTS = listOf(
    "bank", "banka", "garanti", "akbank", "ziraat", "vakif", "vakıf", "halk",
    "iscep", "işcep", "isbank", "yapikredi", "yapı kredi", "ykb", "finans", "qnb",
    "enpara", "deniz", "teb", "kuveyt", "albaraka", "seker", "şeker", "odea",
    "fiba", "anadolu", "burgan", "papara", "tosla", "param", "ininal", "midas",
    "colendi", "hepsipay", "iyzico", "bonus", "maximum", "axess", "paraf", "world",
)

private fun String.foldTurkish(): String = lowercase(Locale.ROOT)
    .replace('ı', 'i').replace('İ', 'i').replace('ş', 's').replace('ğ', 'g')
    .replace('ü', 'u').replace('ö', 'o').replace('ç', 'c')

private fun looksLikeBank(packageName: String, label: String): Boolean {
    val haystack = "${packageName.foldTurkish()} ${label.foldTurkish()}"
    return BANK_HINTS.any { haystack.contains(it.foldTurkish()) }
}

/** Başlatılabilir (kullanıcının gördüğü) uygulamaları döner; banka olanlar başta. */
suspend fun loadInstalledApps(context: Context): List<InstalledApp> = withContext(Dispatchers.IO) {
    val pm = context.packageManager
    val launcherIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)

    pm.queryIntentActivities(launcherIntent, 0)
        .mapNotNull { it.activityInfo?.applicationInfo }
        .distinctBy { it.packageName }
        .filter { it.packageName != context.packageName }
        .map { info: ApplicationInfo ->
            val label = runCatching { pm.getApplicationLabel(info).toString() }
                .getOrDefault(info.packageName)
            InstalledApp(info.packageName, label, looksLikeBank(info.packageName, label))
        }
        .sortedWith(
            compareByDescending<InstalledApp> { it.likelyBank }
                .thenBy { it.label.foldTurkish() }
        )
}
