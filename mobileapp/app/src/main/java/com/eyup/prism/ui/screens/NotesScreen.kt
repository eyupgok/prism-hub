package com.eyup.prism.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.data.api.Note
import com.eyup.prism.data.api.NoteCreate
import com.eyup.prism.data.api.describeError
import com.eyup.prism.ui.components.ChipLabel
import com.eyup.prism.ui.components.EmptyState
import com.eyup.prism.ui.components.ErrorBanner
import com.eyup.prism.ui.components.ScreenHeader
import com.eyup.prism.ui.theme.PrismPurple
import com.eyup.prism.ui.theme.PrismPurpleLight
import com.eyup.prism.ui.theme.PrismSurface2
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint
import com.eyup.prism.ui.theme.PrismTextMuted
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val NOTE_CATEGORIES = listOf("iş", "kişisel", "genel", "ders", "fikir")

class NotesViewModel : ViewModel() {
    var notes by mutableStateOf<List<Note>>(emptyList())
        private set
    var loading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var search by mutableStateOf("")
    var category by mutableStateOf<String?>(null)
    var loadedOnce by mutableStateOf(false)
        private set

    fun load() {
        viewModelScope.launch {
            loading = true
            error = null
            try {
                val q = search.trim()
                notes = if (q.isNotEmpty()) {
                    ApiClient.api().searchNotes(q, category)
                } else {
                    ApiClient.api().getNotes(category)
                }
                loadedOnce = true
            } catch (e: Exception) {
                error = describeError(e)
            }
            loading = false
        }
    }

    fun create(body: NoteCreate) {
        viewModelScope.launch {
            error = null
            try {
                ApiClient.api().createNote(body)
                load()
            } catch (e: Exception) {
                error = describeError(e)
            }
        }
    }

    fun delete(id: Int) {
        viewModelScope.launch {
            error = null
            try {
                ApiClient.api().deleteNote(id)
                load()
            } catch (e: Exception) {
                error = describeError(e)
            }
        }
    }
}

@Composable
fun NotesScreen(vm: NotesViewModel = viewModel()) {
    var showCreate by remember { mutableStateOf(false) }

    // Arama yazarken 300 ms bekleyip yükle (debounce); kategori değişiminde hemen
    LaunchedEffect(vm.search, vm.category) {
        if (vm.loadedOnce && vm.search.isNotEmpty()) delay(300)
        vm.load()
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
            Box(Modifier.padding(vertical = 12.dp)) {
                ScreenHeader("Notlar", "${vm.notes.size} not")
            }

            vm.error?.let {
                ErrorBanner(it)
                Spacer(Modifier.height(8.dp))
            }

            OutlinedTextField(
                value = vm.search,
                onValueChange = { vm.search = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Notlarda ara...", color = PrismTextFaint) },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null, tint = PrismTextFaint) },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = PrismPurple,
                    unfocusedBorderColor = PrismSurface2,
                    focusedTextColor = PrismText,
                    unfocusedTextColor = PrismText,
                ),
            )

            Spacer(Modifier.height(8.dp))

            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                item {
                    FilterChip(
                        selected = vm.category == null,
                        onClick = { vm.category = null },
                        label = { Text("Tümü", fontSize = 12.sp) },
                        colors = prismChipColors(),
                    )
                }
                items(NOTE_CATEGORIES) { cat ->
                    FilterChip(
                        selected = vm.category == cat,
                        onClick = { vm.category = if (vm.category == cat) null else cat },
                        label = { Text(cat, fontSize = 12.sp) },
                        colors = prismChipColors(),
                    )
                }
            }

            if (vm.loading && vm.notes.isEmpty()) {
                Box(Modifier.fillMaxWidth().padding(vertical = 48.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = PrismPurple)
                }
            } else if (vm.notes.isEmpty()) {
                EmptyState(Icons.Filled.Description, "Not bulunamadı")
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(vm.notes, key = { it.id }) { note ->
                        NoteCard(note, onDelete = { vm.delete(note.id) })
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
            Icon(Icons.Filled.Add, contentDescription = "Yeni not")
        }
    }

    if (showCreate) {
        CreateNoteDialog(
            onDismiss = { showCreate = false },
            onCreate = { body ->
                vm.create(body)
                showCreate = false
            },
        )
    }
}

@Composable
private fun NoteCard(note: Note, onDelete: () -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrismSurface2, RoundedCornerShape(16.dp))
            .clickable { expanded = !expanded }
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                note.title,
                color = PrismText,
                fontSize = 15.sp,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.weight(1f),
            )
            IconButton(onClick = onDelete) {
                Icon(Icons.Filled.Delete, contentDescription = "Sil", tint = PrismTextFaint)
            }
        }
        Text(
            note.content,
            color = PrismTextMuted,
            fontSize = 13.sp,
            maxLines = if (expanded) Int.MAX_VALUE else 3,
        )
        ChipLabel(note.category, PrismPurpleLight)
    }
}

@Composable
private fun CreateNoteDialog(onDismiss: () -> Unit, onCreate: (NoteCreate) -> Unit) {
    var title by remember { mutableStateOf("") }
    var content by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("genel") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = PrismSurface2,
        title = { Text("Yeni Not", color = PrismText) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Başlık") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = content,
                    onValueChange = { content = it },
                    label = { Text("İçerik") },
                    minLines = 3,
                    maxLines = 6,
                    modifier = Modifier.fillMaxWidth(),
                )
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(NOTE_CATEGORIES) { cat ->
                        FilterChip(
                            selected = category == cat,
                            onClick = { category = cat },
                            label = { Text(cat, fontSize = 12.sp) },
                            colors = prismChipColors(),
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onCreate(NoteCreate(title.trim(), content.trim(), category)) },
                enabled = title.isNotBlank() && content.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = PrismPurple),
            ) { Text("Kaydet") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("İptal", color = PrismTextMuted) }
        },
    )
}
