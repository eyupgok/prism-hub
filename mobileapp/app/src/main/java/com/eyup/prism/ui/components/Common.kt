package com.eyup.prism.ui.components

import android.widget.TextView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.text.HtmlCompat
import com.eyup.prism.ui.theme.PrismRed
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint

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
fun ErrorBanner(message: String) {
    Text(
        text = message,
        color = PrismRed,
        fontSize = 13.sp,
        modifier = Modifier
            .fillMaxWidth()
            .background(PrismRed.copy(alpha = 0.1f), RoundedCornerShape(12.dp))
            .padding(12.dp),
    )
}

@Composable
fun EmptyState(icon: ImageVector, text: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth().padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(icon, contentDescription = null, tint = PrismTextFaint.copy(alpha = 0.4f))
        Text(text, color = PrismTextFaint, fontSize = 14.sp)
    }
}

/**
 * Backend yanıtları basit HTML etiketleri içerebilir (<b>, <i>, <s>) —
 * TextView + HtmlCompat ile render edilir.
 */
@Composable
fun HtmlText(html: String, modifier: Modifier = Modifier, color: Color = PrismText) {
    val argb = color.toArgb()
    AndroidView(
        modifier = modifier,
        factory = { context ->
            TextView(context).apply {
                textSize = 15f
                setTextColor(argb)
            }
        },
        update = { view ->
            view.setTextColor(argb)
            view.text = HtmlCompat.fromHtml(
                html.replace("\n", "<br>"),
                HtmlCompat.FROM_HTML_MODE_COMPACT,
            )
        },
    )
}

@Composable
fun DotBadge(color: Color, size: Dp = 10.dp) {
    Box(modifier = Modifier.size(size).background(color, CircleShape))
}

@Composable
fun ChipLabel(text: String, color: Color) {
    Text(
        text = text,
        fontSize = 11.sp,
        color = color,
        modifier = Modifier
            .background(color.copy(alpha = 0.12f), RoundedCornerShape(50))
            .padding(horizontal = 8.dp, vertical = 2.dp),
    )
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
