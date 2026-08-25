package com.eyup.prism.ui.screens

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.data.api.Reminder
import com.eyup.prism.data.api.ReminderCreate
import com.eyup.prism.data.api.describeError
import com.eyup.prism.ui.components.ChipLabel
import com.eyup.prism.ui.components.DotBadge
import com.eyup.prism.ui.components.EmptyState
import com.eyup.prism.ui.components.ErrorBanner
import com.eyup.prism.ui.components.ScreenHeader
import com.eyup.prism.ui.theme.PriorityColors
import com.eyup.prism.ui.theme.PrismAmber
import com.eyup.prism.ui.theme.PrismGreen
import com.eyup.prism.ui.theme.PrismPurple
import com.eyup.prism.ui.theme.PrismPurpleLight
import com.eyup.prism.ui.theme.PrismRed
import com.eyup.prism.ui.theme.PrismSurface2
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint
import com.eyup.prism.ui.theme.PrismTextMuted
import com.eyup.prism.util.formatDt
import com.eyup.prism.util.parseDt
import com.eyup.prism.util.timeLeftLabel
import com.eyup.prism.util.toIsoString
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime

private val PRIORITY_LABELS = mapOf(1 to "Kritik", 2 to "Önemli", 3 to "Normal", 4 to "Sessiz")
private val RECURRENCE_LABELS = mapOf("daily" to "Günlük", "weekly" to "Haftalık", "monthly" to "Aylık")

class RemindersViewModel : ViewModel() {
    var items by mutableStateOf<List<Reminder>>(emptyList())
        private set
    var loading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var showCompleted by mutableStateOf(false)

    fun load() {
        viewModelScope.launch {
            loading = true
            error = null
            try {
                items = ApiClient.api().getReminders(includeCompleted = true)
            } catch (e: Exception) {
                error = describeError(e)
            }
            loading = false
        }
    }

    private fun action(block: suspend () -> Unit) {
        viewModelScope.launch {
            error = null
            try {
                block()
                items = ApiClient.api().getReminders(includeCompleted = true)
            } catch (e: Exception) {
                error = describeError(e)
            }
        }
    }

    fun complete(id: Int) = action { ApiClient.api().completeReminder(id) }
    fun snooze(id: Int, minutes: Int) = action { ApiClient.api().snoozeReminder(id, minutes) }
    fun delete(id: Int) = action { ApiClient.api().deleteReminder(id) }
    fun create(body: ReminderCreate) = action { ApiClient.api().createReminder(body) }
}

@Composable
fun RemindersScreen(vm: RemindersViewModel = viewModel()) {
    var showCreate by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        if (vm.items.isEmpty()) vm.load()
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                val activeCount = vm.items.count { it.isCompleted == 0 }
                ScreenHeader("Hatırlatıcılar", "$activeCount aktif")
                IconButton(onClick = { vm.load() }) {
                    Icon(Icons.Filled.Refresh, contentDescription = "Yenile", tint = PrismTextMuted)
                }
            }

            vm.error?.let {
                ErrorBanner(it)
                androidx.compose.foundation.layout.Spacer(Modifier.padding(4.dp))
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = !vm.showCompleted,
                    onClick = { vm.showCompleted = false },
                    label = { Text("Aktif") },
                    colors = prismChipColors(),
                )
                FilterChip(
                    selected = vm.showCompleted,
                    onClick = { vm.showCompleted = true },
                    label = { Text("Tamamlanan") },
                    colors = prismChipColors(),
                )
            }

            val filtered = vm.items.filter { (it.isCompleted == 1) == vm.showCompleted }

            if (vm.loading) {
                Box(Modifier.fillMaxWidth().padding(vertical = 48.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = PrismPurple)
                }
            } else if (filtered.isEmpty()) {
                EmptyState(Icons.Filled.Notifications, "Hatırlatıcı yok")
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(filtered, key = { it.id }) { reminder ->
                        ReminderCard(
                            reminder = reminder,
                            onComplete = { vm.complete(reminder.id) },
                            onSnooze = { vm.snooze(reminder.id, 15) },
                            onDelete = { vm.delete(reminder.id) },
                        )
                    }
                }
            }
        }

        FloatingActionButton(
            onClick = { showCreate = true },
            containerColor = PrismPurple,
            contentColor = Color.White,
            modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp),
        ) {
            Icon(Icons.Filled.Add, contentDescription = "Yeni hatırlatıcı")
        }
    }

    if (showCreate) {
        CreateReminderDialog(
            onDismiss = { showCreate = false },
            onCreate = { body ->
                vm.create(body)
                showCreate = false
            },
        )
    }
}

@Composable
private fun ReminderCard(
    reminder: Reminder,
    onComplete: () -> Unit,
    onSnooze: () -> Unit,
    onDelete: () -> Unit,
) {
    val due = parseDt(reminder.dueDatetime)
    val isDone = reminder.isCompleted == 1
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrismSurface2, RoundedCornerShape(16.dp))
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        DotBadge(PriorityColors[reminder.priority] ?: PrismGreen)
        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    reminder.title,
                    color = if (isDone) PrismTextFaint else PrismText,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium,
                    textDecoration = if (isDone) TextDecoration.LineThrough else null,
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(formatDt(due), color = PrismTextFaint, fontSize = 12.sp)
                if (!isDone) {
                    val label = timeLeftLabel(due)
                    Text(
                        label,
                        color = if (label == "Geçti") PrismRed else PrismAmber,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                RECURRENCE_LABELS[reminder.recurrence]?.let {
                    ChipLabel("🔁 $it", PrismPurpleLight)
                }
            }
        }
        if (!isDone) {
            IconButton(onClick = onSnooze) {
                Icon(Icons.Filled.Schedule, contentDescription = "15 dk ertele", tint = PrismAmber)
            }
            IconButton(onClick = onComplete) {
                Icon(Icons.Filled.Check, contentDescription = "Tamamla", tint = PrismGreen)
            }
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Filled.Delete, contentDescription = "Sil", tint = PrismTextFaint)
        }
    }
}

@Composable
private fun CreateReminderDialog(onDismiss: () -> Unit, onCreate: (ReminderCreate) -> Unit) {
    val context = LocalContext.current
    var title by remember { mutableStateOf("") }
    var date by remember { mutableStateOf(LocalDate.now()) }
    var time by remember { mutableStateOf(LocalTime.of(9, 0)) }
    var priority by remember { mutableStateOf(4) }
    var recurrence by remember { mutableStateOf("none") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = PrismSurface2,
        title = { Text("Yeni Hatırlatıcı", color = PrismText) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Başlık") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        DatePickerDialog(
                            context,
                            { _, y, m, d -> date = LocalDate.of(y, m + 1, d) },
                            date.year, date.monthValue - 1, date.dayOfMonth,
                        ).show()
                    }) {
                        Text("📅 ${date.dayOfMonth}.${date.monthValue}.${date.year}", color = PrismText)
                    }
                    OutlinedButton(onClick = {
                        TimePickerDialog(
                            context,
                            { _, h, min -> time = LocalTime.of(h, min) },
                            time.hour, time.minute, true,
                        ).show()
                    }) {
                        Text("🕒 %02d:%02d".format(time.hour, time.minute), color = PrismText)
                    }
                }
                Text("Öncelik", color = PrismTextMuted, fontSize = 12.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf(4 to "🔇 Sessiz", 3 to "🟢 Normal", 2 to "🟡 Önemli", 1 to "🔴 Kritik").forEach { (value, label) ->
                        FilterChip(
                            selected = priority == value,
                            onClick = { priority = value },
                            label = { Text(label, fontSize = 12.sp) },
                            colors = prismChipColors(),
                        )
                    }
                }
                Text("Tekrar", color = PrismTextMuted, fontSize = 12.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("none" to "Yok", "daily" to "Gün", "weekly" to "Hafta", "monthly" to "Ay").forEach { (value, label) ->
                        FilterChip(
                            selected = recurrence == value,
                            onClick = { recurrence = value },
                            label = { Text(label, fontSize = 12.sp) },
                            colors = prismChipColors(),
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onCreate(
                        ReminderCreate(
                            title = title.trim(),
                            dueDatetime = toIsoString(LocalDateTime.of(date, time)),
                            priority = priority,
                            recurrence = recurrence,
                        )
                    )
                },
                enabled = title.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = PrismPurple),
            ) { Text("Ekle") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("İptal", color = PrismTextMuted) }
        },
    )
}

@Composable
fun prismChipColors() = FilterChipDefaults.filterChipColors(
    selectedContainerColor = PrismPurple.copy(alpha = 0.25f),
    selectedLabelColor = PrismPurpleLight,
    labelColor = PrismTextMuted,
)
