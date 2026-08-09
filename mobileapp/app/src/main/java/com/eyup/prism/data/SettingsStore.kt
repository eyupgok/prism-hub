package com.eyup.prism.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "prism_settings")

data class PrismSettings(val baseUrl: String, val apiKey: String) {
    val isConfigured: Boolean get() = baseUrl.isNotBlank()
}

/** Sunucu URL + API anahtarını cihazda saklar (koda gömülmez, Ayarlar'dan girilir) */
class SettingsStore(private val context: Context) {

    companion object {
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        private val KEY_API_KEY = stringPreferencesKey("api_key")
    }

    val settings: Flow<PrismSettings> = context.dataStore.data.map { prefs ->
        PrismSettings(
            baseUrl = prefs[KEY_BASE_URL] ?: "",
            apiKey = prefs[KEY_API_KEY] ?: "",
        )
    }

    suspend fun save(baseUrl: String, apiKey: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_BASE_URL] = baseUrl.trim().trimEnd('/')
            prefs[KEY_API_KEY] = apiKey.trim()
        }
    }
}
