package com.eyup.prism.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "prism_settings")

data class PrismSettings(
    val baseUrl: String,
    val apiKey: String,
    /** Banka bildirimlerinden otomatik harcama yakalama açık mı */
    val captureEnabled: Boolean = false,
    /** Dinlenecek uygulamaların paket adları — boşsa hiçbir şey yakalanmaz */
    val watchedPackages: Set<String> = emptySet(),
) {
    val isConfigured: Boolean get() = baseUrl.isNotBlank()

    /** Yakalama gerçekten çalışır durumda mı (ayar açık + en az bir uygulama seçili + sunucu tanımlı) */
    val captureReady: Boolean get() = captureEnabled && watchedPackages.isNotEmpty() && isConfigured
}

/** Sunucu URL + API anahtarını cihazda saklar (koda gömülmez, Ayarlar'dan girilir) */
class SettingsStore(private val context: Context) {

    companion object {
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        private val KEY_API_KEY = stringPreferencesKey("api_key")
        private val KEY_CAPTURE_ENABLED = booleanPreferencesKey("capture_enabled")
        private val KEY_WATCHED_PACKAGES = stringSetPreferencesKey("watched_packages")
    }

    val settings: Flow<PrismSettings> = context.dataStore.data.map { prefs ->
        PrismSettings(
            baseUrl = prefs[KEY_BASE_URL] ?: "",
            apiKey = prefs[KEY_API_KEY] ?: "",
            captureEnabled = prefs[KEY_CAPTURE_ENABLED] ?: false,
            watchedPackages = prefs[KEY_WATCHED_PACKAGES] ?: emptySet(),
        )
    }

    suspend fun save(baseUrl: String, apiKey: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_BASE_URL] = baseUrl.trim().trimEnd('/')
            prefs[KEY_API_KEY] = apiKey.trim()
        }
    }

    suspend fun setCaptureEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs -> prefs[KEY_CAPTURE_ENABLED] = enabled }
    }

    suspend fun setPackageWatched(packageName: String, watched: Boolean) {
        context.dataStore.edit { prefs ->
            val current = prefs[KEY_WATCHED_PACKAGES] ?: emptySet()
            prefs[KEY_WATCHED_PACKAGES] =
                if (watched) current + packageName else current - packageName
        }
    }
}
