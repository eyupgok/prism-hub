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
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.SimpleDateFormat
import java.util.Date
import com.eyup.prism.data.CaptureLog
import com.eyup.prism.data.CaptureLogEntry
import com.eyup.prism.data.InstalledApp
import com.eyup.prism.data.ListenerState
import com.eyup.prism.data.Outcome
import com.eyup.prism.data.PendingQueue
import com.eyup.prism.data.PrismSettings
import com.eyup.prism.data.SettingsStore
import com.eyup.prism.data.loadInstalledApps
import com.eyup.prism.service.CaptureSyncWorker
import com.eyup.prism.service.canPostNotifications
import com.eyup.prism.service.hasNotificationAccess
import com.eyup.prism.service.notificationAccessIntent
import com.eyup.prism.service.reconcileListenerState
import com.eyup.prism.service.requestListenerRebind
import com.eyup.prism.service.sendSelfTestNotification
import kotlinx.coroutines.delay
import com.eyup.prism.ui.theme.PrismAmber
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
    var pending by remember { mutableIntStateOf(0) }
    var logEntries by remember { mutableStateOf<List<CaptureLogEntry>>(emptyList()) }
    var listener by remember { mutableStateOf(ListenerState.read(context)) }
    var testNote by remember { mutableStateOf<String?>(null) }

    fun refresh() {
        pending = PendingQueue.size(context)
        logEntries = CaptureLog.read(context).reversed()
        // Diskteki kayıt süreç öldürüldükten sonra "bağlı" kalmış olabilir —
        // okumadan önce süreç içindeki gerçekle eşitle, yoksa kart yeşil yalan söyler.
        reconcileListenerState(context)
        listener = ListenerState.read(context)
    }

    // Ekran her açıldığında tazelenir; arka planda eklenen kayıtlar için "Yenile" var
    LaunchedEffect(settings.captureEnabled) { refresh() }

    // Sistem ayarlarından dönünce izin durumunu tazele
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        hasAccess = hasNotificationAccess(context)
        // İzin yeni verildiyse servis hemen bağlanmayabiliyor
        if (hasAccess) requestListenerRebind(context)
    }

    /** Test bildirimini gönderip sonucun kayda düşmesini bekler */
    fun runSelfTest() {
        testNote = "Test bildirimi gönderildi, sonuç bekleniyor..."
        scope.launch {
            sendSelfTestNotification(context)
            delay(1500)
            refresh()
            testNote = if (logEntries.any { it.outcome == Outcome.SELF_TEST }) {
                "✅ Dinleyici bildirimi gördü — yakalama zinciri çalışıyor."
            } else {
                "❌ Dinleyici test bildirimini görmedi. Aşağıdaki \"Yeniden bağla\"yı " +
                    "dene; düzelmezse sistem ayarlarından bildirim erişimini kapatıp aç."
            }
        }
    }

    // Android 13+ bildirim göndermek için izin istiyor — test düğmesi bunu gerektiriyor
    val postPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) runSelfTest()
        else testNote = "Test için bildirim gönderme izni gerekiyor."
    }

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

            // ── Dinleyici gerçekten çalışıyor mu ─────────────────────────────
            // İzin verilmiş görünmesi yetmiyor: servis bağlı olmayabilir ya da bağlı
            // olup hiçbir bildirim görmüyor olabilir. İkisi ayrı sinyal, ayrı gösteriliyor.
            if (hasAccess) {
                ListenerStatusBlock(
                    status = listener,
                    testNote = testNote,
                    onTest = {
                        if (canPostNotifications(context)) runSelfTest()
                        else postPermissionLauncher.launch(
                            android.Manifest.permission.POST_NOTIFICATIONS
                        )
                    },
                    onRebind = {
                        testNote = "Yeniden bağlanma istendi..."
                        requestListenerRebind(context)
                        scope.launch {
                            delay(1500)
                            refresh()
                            testNote = if (listener.connected) {
                                "✅ Dinleyici bağlandı."
                            } else {
                                "❌ Sistem bağlantıyı reddetti. Xiaomi/Redmi/Poco " +
                                    "telefonlarda sebebi genelde \"Otomatik başlatma\" " +
                                    "iznidir: Ayarlar → Uygulamalar → PRISM → Otomatik " +
                                    "başlatma'yı aç, sonra tekrar dene."
                            }
                        }
                    },
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

            // ── Çevrimdışıyken biriken bildirimler ───────────────────────────
            if (pending > 0) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "📦 $pending bildirim gönderilmeyi bekliyor",
                        color = PrismTextMuted,
                        fontSize = 13.sp,
                    )
                    TextButton(onClick = {
                        CaptureSyncWorker.scheduleNow(context.applicationContext)
                        pending = PendingQueue.size(context)
                    }) {
                        Text("Şimdi gönder", color = PrismPurpleLight)
                    }
                }
                Text(
                    "İnternet gelince kendiliğinden gönderilir; harcamalar bildirimin " +
                        "düştüğü tarihe yazılır.",
                    color = PrismTextFaint,
                    fontSize = 11.sp,
                )
            }

            if (settings.captureReady && hasAccess) {
                Text(
                    "Hazır. Bir alışveriş yaptığında Telegram'a bildirim düşecek.",
                    color = PrismGreen,
                    fontSize = 12.sp,
                )
            }

            CaptureLogList(
                entries = logEntries,
                onRefresh = { refresh() },
                onClear = {
                    CaptureLog.clear(context)
                    logEntries = emptyList()
                },
            )
        }
    }
}

/**
 * Dinleyicinin canlılık kartı.
 *
 * "Son gördüğü bildirim" satırı teşhisin belkemiği: burası boşsa sorun banka
 * uygulamasında ya da paket seçiminde değil, dinleyicinin kendisindedir — çünkü
 * seçili olmayan uygulamaların bildirimleri de "dinlenmiyor" olarak kayda geçiyor.
 */
@Composable
private fun ListenerStatusBlock(
    status: ListenerState.Status,
    testNote: String?,
    onTest: () -> Unit,
    onRebind: () -> Unit,
) {
    val timeFormat = remember { SimpleDateFormat("d MMM HH:mm", Locale("tr")) }

    // Bağlı görünüp saatlerdir hiçbir şey görmemek de bir arıza: telefona günde
    // onlarca bildirim düşüyor, hiçbirini görmüyorsa servis fiilen ölüdür.
    val silentHours = if (status.lastSeenAt == 0L) 0L
    else (System.currentTimeMillis() - status.lastSeenAt) / (60 * 60 * 1000L)
    val looksAsleep = status.connected && silentHours >= SILENT_ALERT_HOURS

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0x14FFFFFF), RoundedCornerShape(12.dp))
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            if (status.connected) "🟢 Dinleyici bağlı" else "🔴 Dinleyici bağlı değil",
            color = if (status.connected) PrismGreen else PrismRed,
            fontSize = 13.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            if (status.lastSeenAt == 0L) {
                "Henüz hiçbir bildirim görmedi — hangi uygulamadan olursa olsun."
            } else {
                "Son gördüğü bildirim: ${timeFormat.format(Date(status.lastSeenAt))}"
            },
            color = PrismTextFaint,
            fontSize = 11.sp,
        )

        if (looksAsleep) {
            Text(
                "⚠️ Bağlı görünüyor ama $silentHours saattir hiçbir bildirim görmedi. " +
                    "Aşağıdan test bildirimi gönder — o da görülmezse servis uykuda demektir.",
                color = PrismAmber,
                fontSize = 11.sp,
            )
        }

        if (!status.connected) {
            Text(
                "İzin verilmiş görünse bile servis bağlanmamış olabilir. İki sık sebep: " +
                    "uygulama güncellendikten sonra sistem servisi geri bağlamaz, ya da " +
                    "telefonun \"Otomatik başlatma\" izni kapalıdır (Xiaomi/Redmi/Poco'da " +
                    "varsayılan kapalıdır ve bağlantıyı sessizce reddeder).",
                color = PrismTextFaint,
                fontSize = 11.sp,
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onTest) {
                Text("Test bildirimi gönder", color = PrismPurpleLight, fontSize = 13.sp)
            }
            TextButton(onClick = onRebind) {
                Text("Yeniden bağla", color = PrismTextMuted, fontSize = 13.sp)
            }
        }

        if (testNote != null) {
            Text(testNote, color = PrismTextMuted, fontSize = 12.sp)
        }

        Text(
            "💡 Son kullanılanlar ekranındaki \"hepsini kapat\" düğmesi PRISM'i tamamen " +
                "öldürür ve dinleme durur (Spotify'ın müziğini de aynı düğme susturuyor). " +
                "PRISM kartını basılı tutup kilitlersen 🔒 o düğme onu atlar. Uygulama " +
                "yarım saatte bir kendini geri bağlamayı dener, ama kilitlemek en temizi.",
            color = PrismTextFaint,
            fontSize = 11.sp,
        )
    }
}

/** Bağlı görünürken bu kadar süre sessiz kalmak arıza sayılır */
private const val SILENT_ALERT_HOURS = 12L

/** Sonuç koduna göre etiket ve renk */
private fun outcomeLabel(outcome: String): Pair<String, Color> = when (outcome) {
    Outcome.SAVED -> "kaydedildi" to PrismGreen
    Outcome.SKIPPED -> "harcama değil" to PrismTextMuted
    Outcome.QUEUED -> "kuyrukta" to PrismPurpleLight
    Outcome.IGNORED -> "dinlenmiyor" to PrismTextFaint
    Outcome.SECRET -> "şifre mesajı" to PrismTextFaint
    Outcome.SELF_TEST -> "test ✅" to PrismGreen
    else -> "hata" to PrismRed
}

@Composable
private fun CaptureLogList(
    entries: List<CaptureLogEntry>,
    onRefresh: () -> Unit,
    onClear: () -> Unit,
) {
    val timeFormat = remember { SimpleDateFormat("HH:mm", Locale("tr")) }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("Son Yakalananlar", color = PrismText, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
        Row {
            TextButton(onClick = onRefresh) { Text("Yenile", color = PrismPurpleLight) }
            if (entries.isNotEmpty()) {
                TextButton(onClick = onClear) { Text("Temizle", color = PrismTextMuted) }
            }
        }
    }

    if (entries.isEmpty()) {
        Text(
            "Henüz bildirim yakalanmadı. Bir bildirim geldiğinde burada görünecek — " +
                "yakalanmadıysa sebebi de yazar.",
            color = PrismTextFaint,
            fontSize = 12.sp,
        )
        return
    }

    entries.take(20).forEach { entry ->
        val (label, color) = outcomeLabel(entry.outcome)
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(entry.appLabel, color = PrismText, fontSize = 13.sp)
                if (entry.detail.isNotBlank()) {
                    Text(entry.detail, color = PrismTextFaint, fontSize = 11.sp)
                }
            }
            Text(
                timeFormat.format(Date(entry.at)),
                color = PrismTextFaint,
                fontSize = 11.sp,
                modifier = Modifier.padding(end = 8.dp),
            )
            Text(label, color = color, fontSize = 11.sp)
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
