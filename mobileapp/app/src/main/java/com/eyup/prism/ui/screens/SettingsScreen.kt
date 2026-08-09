package com.eyup.prism.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.eyup.prism.data.SettingsStore
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.data.api.describeError
import com.eyup.prism.ui.components.LabeledRow
import com.eyup.prism.ui.components.ScreenHeader
import com.eyup.prism.ui.theme.PrismGreen
import com.eyup.prism.ui.theme.PrismPurple
import com.eyup.prism.ui.theme.PrismRed
import com.eyup.prism.ui.theme.PrismSurface2
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint
import com.eyup.prism.ui.theme.PrismTextMuted
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(store: SettingsStore) {
    val scope = rememberCoroutineScope()
    val saved by store.settings.collectAsState(initial = null)

    var url by remember { mutableStateOf("") }
    var apiKey by remember { mutableStateOf("") }
    var initialized by remember { mutableStateOf(false) }
    var showKey by remember { mutableStateOf(false) }
    var testing by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<Pair<Boolean, String>?>(null) }

    // DataStore'dan ilk değer gelince alanları bir kez doldur
    LaunchedEffect(saved) {
        val s = saved ?: return@LaunchedEffect
        if (!initialized) {
            url = s.baseUrl
            apiKey = s.apiKey
            initialized = true
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        ScreenHeader("Ayarlar", "Sunucu bağlantısı")

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(PrismSurface2, RoundedCornerShape(16.dp))
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("API Bağlantısı", color = PrismText, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)

            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("Sunucu URL") },
                placeholder = { Text("https://kendi-alan-adin.example.com", color = PrismTextFaint) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                label = { Text("API Anahtarı") },
                singleLine = true,
                visualTransformation = if (showKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { showKey = !showKey }) {
                        Icon(
                            if (showKey) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                            contentDescription = if (showKey) "Gizle" else "Göster",
                            tint = PrismTextMuted,
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )

            Button(
                onClick = {
                    scope.launch {
                        testing = true
                        status = null
                        try {
                            store.save(url, apiKey)
                            ApiClient.configure(url, apiKey)
                            val health = ApiClient.api().health()
                            status = true to "Bağlantı başarılı — ${health.service} çalışıyor ✅"
                        } catch (e: Exception) {
                            status = false to describeError(e)
                        }
                        testing = false
                    }
                },
                enabled = url.isNotBlank() && !testing,
                colors = ButtonDefaults.buttonColors(containerColor = PrismPurple),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (testing) "Deneniyor..." else "Kaydet ve Bağlantıyı Test Et")
            }

            status?.let { (ok, message) ->
                Text(
                    message,
                    color = if (ok) PrismGreen else PrismRed,
                    fontSize = 13.sp,
                )
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(PrismSurface2, RoundedCornerShape(16.dp))
                .padding(16.dp),
        ) {
            Text(
                "Hakkında",
                color = PrismText,
                fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(bottom = 8.dp),
            )
            LabeledRow("Uygulama", "PRISM Mobil v1.0")
            LabeledRow("Backend", "FastAPI + Groq + SQLite")
            LabeledRow("AI", "llama-3.3-70b + Whisper + Vision")
            Text(
                "Sunucu URL ve API anahtarı yalnızca bu cihazda saklanır (DataStore).",
                color = PrismTextFaint,
                fontSize = 12.sp,
                modifier = Modifier.padding(top = 10.dp),
            )
        }
    }
}
