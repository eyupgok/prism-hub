package com.eyup.prism.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint

// Uygulama sensöre indirgenirken buradaki bileşenlerin çoğu (ErrorBanner,
// EmptyState, HtmlText, DotBadge, ChipLabel) tek kullanıcıları olan liste
// ekranlarıyla birlikte silindi. Kalan ikisini Ayarlar kullanıyor.

@Composable
fun ScreenHeader(title: String, subtitle: String? = null) {
    Column {
        Text(title, fontSize = 24.sp, fontWeight = FontWeight.Bold, color = PrismText)
        if (subtitle != null) {
            Text(subtitle, fontSize = 13.sp, color = PrismTextFaint)
        }
    }
}

@Composable
fun LabeledRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, color = PrismTextFaint, fontSize = 13.sp)
        Text(value, color = PrismText, fontSize = 13.sp)
    }
}
