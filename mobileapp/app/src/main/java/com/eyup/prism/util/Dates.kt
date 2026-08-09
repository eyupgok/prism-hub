package com.eyup.prism.util

import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

private val DISPLAY_FMT = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")
private val ISO_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")

val TURKISH_MONTHS = listOf(
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)

/** Backend'den gelen ISO string'i parse eder ("+03:00" offset'li veya offsetsiz) */
fun parseDt(value: String): LocalDateTime = try {
    OffsetDateTime.parse(value).toLocalDateTime()
} catch (_: Exception) {
    LocalDateTime.parse(value.take(19))
}

fun formatDt(dt: LocalDateTime): String = dt.format(DISPLAY_FMT)

fun toIsoString(dt: LocalDateTime): String = dt.format(ISO_FMT)

fun todayIso(): String = LocalDate.now().toString()

/** "45 dk", "3 sa 20 dk", "2 gün" ya da "Geçti" */
fun timeLeftLabel(due: LocalDateTime): String {
    val minutes = Duration.between(LocalDateTime.now(), due).toMinutes()
    return when {
        minutes < 0 -> "Geçti"
        minutes < 60 -> "$minutes dk"
        minutes < 1440 -> "${minutes / 60} sa ${minutes % 60} dk"
        else -> "${minutes / 1440} gün"
    }
}
