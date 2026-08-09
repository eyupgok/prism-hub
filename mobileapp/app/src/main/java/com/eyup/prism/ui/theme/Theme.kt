package com.eyup.prism.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// PRISM her zaman koyu temadır (web panelle uyumlu), dynamic color kullanılmaz
private val PrismColorScheme = darkColorScheme(
    primary = PrismPurple,
    onPrimary = Color.White,
    secondary = PrismPurpleLight,
    onSecondary = Color.Black,
    tertiary = PrismGreen,
    background = PrismBg,
    onBackground = PrismText,
    surface = PrismSurface,
    onSurface = PrismText,
    surfaceVariant = PrismSurface2,
    onSurfaceVariant = PrismTextMuted,
    error = PrismRed,
    onError = Color.White,
    outline = Color(0x33FFFFFF),
)

@Composable
fun PRISMTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = PrismColorScheme,
        typography = Typography,
        content = content
    )
}
