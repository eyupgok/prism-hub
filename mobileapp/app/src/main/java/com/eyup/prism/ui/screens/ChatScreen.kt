package com.eyup.prism.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.compose.runtime.mutableStateListOf
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.data.api.ChatRequest
import com.eyup.prism.data.api.describeError
import com.eyup.prism.ui.components.ErrorBanner
import com.eyup.prism.ui.components.HtmlText
import com.eyup.prism.ui.components.ScreenHeader
import com.eyup.prism.ui.theme.PrismPurple
import com.eyup.prism.ui.theme.PrismSurface2
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint
import com.eyup.prism.ui.theme.PrismTextMuted
import kotlinx.coroutines.launch

data class ChatMessage(val role: String, val text: String)

class ChatViewModel : ViewModel() {
    val messages = mutableStateListOf<ChatMessage>()
    var sending by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    fun send(text: String) {
        if (text.isBlank() || sending) return
        messages.add(ChatMessage("user", text))
        sending = true
        error = null
        viewModelScope.launch {
            try {
                val resp = ApiClient.api().chat(ChatRequest(text))
                messages.add(ChatMessage("assistant", resp.response))
            } catch (e: Exception) {
                error = describeError(e)
            }
            sending = false
        }
    }
}

@Composable
fun ChatScreen(vm: ChatViewModel = viewModel()) {
    var input by rememberSaveable { mutableStateOf("") }
    val listState = rememberLazyListState()

    LaunchedEffect(vm.messages.size, vm.sending) {
        if (vm.messages.isNotEmpty()) {
            val lastIndex = vm.messages.size - 1 + (if (vm.sending) 1 else 0)
            listState.animateScrollToItem(lastIndex.coerceAtLeast(0))
        }
    }

    Column(Modifier.fillMaxSize().imePadding()) {
        Box(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            ScreenHeader("PRISM", "Kişisel AI asistanın")
        }

        vm.error?.let {
            Box(Modifier.padding(horizontal = 16.dp)) { ErrorBanner(it) }
        }

        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (vm.messages.isEmpty()) {
                item { ChatIntro() }
            }
            items(vm.messages) { msg -> MessageBubble(msg) }
            if (vm.sending) {
                item { TypingIndicator() }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Mesaj yaz...", color = PrismTextFaint) },
                shape = RoundedCornerShape(24.dp),
                maxLines = 4,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = PrismPurple,
                    unfocusedBorderColor = PrismSurface2,
                    focusedTextColor = PrismText,
                    unfocusedTextColor = PrismText,
                ),
            )
            IconButton(
                onClick = {
                    vm.send(input.trim())
                    input = ""
                },
                enabled = input.isNotBlank() && !vm.sending,
                modifier = Modifier
                    .padding(start = 8.dp)
                    .background(PrismPurple, RoundedCornerShape(50)),
            ) {
                Icon(
                    Icons.AutoMirrored.Filled.Send,
                    contentDescription = "Gönder",
                    tint = androidx.compose.ui.graphics.Color.White,
                )
            }
        }
    }
}

@Composable
private fun MessageBubble(msg: ChatMessage) {
    val isUser = msg.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Box(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .background(
                    color = if (isUser) PrismPurple else PrismSurface2,
                    shape = RoundedCornerShape(
                        topStart = 16.dp,
                        topEnd = 16.dp,
                        bottomStart = if (isUser) 16.dp else 4.dp,
                        bottomEnd = if (isUser) 4.dp else 16.dp,
                    ),
                )
                .padding(horizontal = 14.dp, vertical = 10.dp),
        ) {
            if (isUser) {
                Text(msg.text, color = androidx.compose.ui.graphics.Color.White, fontSize = 15.sp)
            } else {
                HtmlText(msg.text)
            }
        }
    }
}

@Composable
private fun TypingIndicator() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(
            modifier = Modifier.size(18.dp),
            strokeWidth = 2.dp,
            color = PrismPurple,
        )
        Text("  PRISM düşünüyor...", color = PrismTextFaint, fontSize = 13.sp)
    }
}

@Composable
private fun ChatIntro() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrismSurface2, RoundedCornerShape(16.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text("👋 Merhaba! Ben PRISM.", color = PrismText, fontSize = 15.sp)
        Text(
            "Doğal dille yazabilirsin. Örnekler:",
            color = PrismTextMuted,
            fontSize = 13.sp,
        )
        listOf(
            "• Yarın saat 10'da toplantı hatırlat",
            "• Bugün 150 TL yemek harcadım",
            "• İş notlarıma bak",
            "• Hava nasıl?",
            "• Sabah özetini ver",
        ).forEach { Text(it, color = PrismTextFaint, fontSize = 13.sp) }
    }
}
