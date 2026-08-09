package com.eyup.prism.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.eyup.prism.data.InstalledApp
import com.eyup.prism.data.PrismSettings
import com.eyup.prism.data.SettingsStore
import com.eyup.prism.data.loadInstalledApps
import com.eyup.prism.service.hasNotificationAccess
import com.eyup.prism.service.notificationAccessIntent
import com.eyup.prism.ui.theme.PrismGreen
import com.eyup.prism.ui.theme.PrismPurple
import com.eyup.prism.ui.theme.PrismPurpleLight
import com.eyup.prism.ui.theme.PrismRed
import com.eyup.prism.ui.theme.PrismSurface2
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint
import com.eyup.prism.ui.theme.PrismTextMuted
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * Banka bildirimlerinden otomatik harcama kaydı ayarları.
 *
 * İzin uygulama içinden istenemez — kullanıcı sistem ayarlarından verir. O yüzden
 * ekran, izin durumunu açıkça gösterir ve dönüşte yeniden kontrol eder.
 */
@Composable
fun ExpenseCaptureSection(store: SettingsStore, settings: PrismSettings) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var hasAccess by remember { mutableStateOf(hasNotificationAccess(context)) }
    var showPicker by remember { mutableStateOf(false) }
    var apps by remember { mutableStateOf<List<InstalledApp>>(emptyList()) }
    var search by remember { mutableStateOf("") }

    // Sistem ayarlarından dönünce izin durumunu tazele
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { hasAccess = hasNotificationAccess(context) }

    LaunchedEffect(showPicker) {
        if (showPicker && apps.isEmpty()) apps = loadInstalledApps(context)
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrismSurface2, RoundedCornerShape(16.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "Otomatik Harcama Yakalama",
            color = PrismText,
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "Seçtiğin bankacılık uygulamalarının bildirimleri okunur, harcama olanlar " +
                "otomatik kaydedilir ve Telegram'a bildirilir. Şifre ve doğrulama kodu " +
                "içeren bildirimler telefondan hiç çıkmaz.",
            color = PrismTextFaint,
            fontSize = 12.sp,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Bildirimlerden harcama kaydet", color = PrismText, fontSize = 14.sp)
            Switch(
                checked = settings.captureEnabled,
                onCheckedChange = { scope.launch { store.setCaptureEnabled(it) } },
                colors = SwitchDefaults.colors(
                    checkedThumbColor = PrismPurpleLight,
                    checkedTrackColor = PrismPurple,
                ),
            )
        }

        if (settings.captureEnabled) {
            // ── 1. adım: izin ────────────────────────────────────────────────
            if (hasAccess) {
                Text("✅ Bildirim erişimi verildi", color = PrismGreen, fontSize = 13.sp)
            } else {
                Text(
                    "⚠️ Bildirim erişimi yok — bu izin olmadan hiçbir şey yakalanamaz.",
                    color = PrismRed,
                    fontSize = 13.sp,
                )
                OutlinedButton(
                    onClick = { permissionLauncher.launch(notificationAccessIntent()) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Bildirim erişimi ver", color = PrismPurpleLight)
                }
                Text(
                    "Açılan listede PRISM'i bul ve aç. Telefon üreticisine göre ekran " +
                        "biraz farklı görünebilir.",
                    color = PrismTextFaint,
                    fontSize = 11.sp,
                )
            }

            // ── 2. adım: hangi uygulamalar ───────────────────────────────────
            val watchedCount = settings.watchedPackages.size
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    if (watchedCount == 0) "Hiç uygulama seçilmedi"
                    else "$watchedCount uygulama dinleniyor",
                    color = if (watchedCount == 0) PrismRed else PrismTextMuted,
                    fontSize = 13.sp,
                )
                TextButton(onClick = { showPicker = !showPicker }) {
                    Text(if (showPicker) "Kapat" else "Uygulama seç", color = PrismPurpleLight)
                }
            }

            if (showPicker) {
                AppPicker(
                    apps = apps,
                    search = search,
                    onSearchChange = { search = it },
                    watched = settings.watchedPackages,
                    onToggle = { pkg, on -> scope.launch { store.setPackageWatched(pkg, on) } },
                )
            }

            if (settings.captureReady && hasAccess) {
                Text(
                    "Hazır. Bir alışveriş yaptığında Telegram'a bildirim düşecek.",
                    color = PrismGreen,
                    fontSize = 12.sp,
                )
            }
        }
    }
}

@Composable
private fun AppPicker(
    apps: List<InstalledApp>,
    search: String,
    onSearchChange: (String) -> Unit,
    watched: Set<String>,
    onToggle: (String, Boolean) -> Unit,
) {
    OutlinedTextField(
        value = search,
        onValueChange = onSearchChange,
        label = { Text("Uygulama ara") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )

    if (apps.isEmpty()) {
        Text("Uygulamalar yükleniyor...", color = PrismTextFaint, fontSize = 12.sp)
        return
    }

    // Arama boşken sadece bankaya benzeyenleri ve zaten seçilmiş olanları göster —
    // yüzlerce uygulamayı alt alta dizmek listeyi kullanılmaz hâle getiriyor.
    val query = search.trim().lowercase(Locale.ROOT)
    val visible = if (query.isEmpty()) {
        apps.filter { it.likelyBank || it.packageName in watched }
    } else {
        apps.filter {
            it.label.lowercase(Locale.ROOT).contains(query) ||
                it.packageName.lowercase(Locale.ROOT).contains(query)
        }
    }

    if (visible.isEmpty()) {
        Text(
            if (query.isEmpty()) "Bankacılık uygulaması bulunamadı — adını yazarak ara."
            else "Eşleşen uygulama yok.",
            color = PrismTextFaint,
            fontSize = 12.sp,
        )
        return
    }

    visible.take(40).forEach { app ->
        val checked = app.packageName in watched
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onToggle(app.packageName, !checked) }
                .padding(vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(
                checked = checked,
                onCheckedChange = { onToggle(app.packageName, it) },
                colors = CheckboxDefaults.colors(checkedColor = PrismPurple),
            )
            Column(modifier = Modifier.padding(start = 4.dp)) {
                Text(app.label, color = PrismText, fontSize = 14.sp)
                Text(app.packageName, color = PrismTextFaint, fontSize = 11.sp)
            }
        }
    }

    if (query.isEmpty()) {
        Text(
            "Listede göremediğin uygulamayı yukarıdan arayabilirsin.",
            color = PrismTextFaint,
            fontSize = 11.sp,
        )
    }
}
