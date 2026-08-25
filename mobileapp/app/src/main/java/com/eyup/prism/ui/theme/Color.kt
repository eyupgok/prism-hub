package com.eyup.prism.ui.theme

import androidx.compose.ui.graphics.Color

// Web panelle (frontend/) uyumlu mor koyu palet
val PrismBg = Color(0xFF0A0A0F)
val PrismSurface = Color(0xFF14121F)
val PrismSurface2 = Color(0xFF1C1929)
val PrismPurple = Color(0xFF7C3AED)
val PrismPurpleLight = Color(0xFFA78BFA)
val PrismText = Color(0xFFE2E8F0)
val PrismTextMuted = Color(0xFF94A3B8)
val PrismTextFaint = Color(0xFF64748B)
val PrismRed = Color(0xFFF87171)
val PrismAmber = Color(0xFFFBBF24)
val PrismGreen = Color(0xFF4ADE80)

val PrismSlate = Color(0xFF64748B)

// Öncelik: 1=Kritik 2=Önemli 3=Normal 4=Sessiz (varsayılan)
val PriorityColors = mapOf(1 to PrismRed, 2 to PrismAmber, 3 to PrismGreen, 4 to PrismSlate)

// Harcama kategorileri (web panel Expenses.jsx ile aynı renkler)
val CategoryColors = mapOf(
    "yemek" to Color(0xFFF59E0B),
    "ulaşım" to Color(0xFF3B82F6),
    "eğlence" to Color(0xFFEC4899),
    "fatura" to Color(0xFF8B5CF6),
    "alışveriş" to Color(0xFF10B981),
    "diğer" to Color(0xFF6B7280),
)
