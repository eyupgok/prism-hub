package com.eyup.prism.data.api

import com.google.gson.annotations.SerializedName

// Backend JSON alanlarıyla birebir eşleşir (snake_case → @SerializedName)

data class Reminder(
    val id: Int,
    val title: String,
    @SerializedName("due_datetime") val dueDatetime: String,
    val priority: Int,
    @SerializedName("is_completed") val isCompleted: Int,
    @SerializedName("last_notified_at") val lastNotifiedAt: String? = null,
    @SerializedName("snooze_count") val snoozeCount: Int = 0,
    val recurrence: String = "none",
    @SerializedName("created_at") val createdAt: String = "",
    // complete_reminder tekrarlayanı ötelediğinde true döner
    val rescheduled: Boolean? = null,
)

data class ReminderCreate(
    val title: String,
    @SerializedName("due_datetime") val dueDatetime: String,
    val priority: Int = 4,   // Sessiz — sunucudaki DEFAULT_PRIORITY ile aynı
    val recurrence: String = "none",
)

data class Note(
    val id: Int,
    val title: String,
    val content: String,
    val category: String,
    @SerializedName("created_at") val createdAt: String = "",
)

data class NoteCreate(
    val title: String,
    val content: String,
    val category: String = "genel",
)

data class Expense(
    val id: Int,
    val amount: Double,
    val category: String,
    val description: String = "",
    @SerializedName("expense_date") val expenseDate: String,
    @SerializedName("created_at") val createdAt: String = "",
)

data class ExpenseCreate(
    val amount: Double,
    val category: String,
    val description: String = "",
    @SerializedName("expense_date") val expenseDate: String? = null,
)

data class ExpenseSummary(
    val month: String,
    val total: Double,
    @SerializedName("by_category") val byCategory: Map<String, Double> = emptyMap(),
)

/** Banka bildiriminin sunucuya gönderilen hâli */
data class NotificationIngest(
    @SerializedName("package_name") val packageName: String,
    val title: String = "",
    val text: String,
    @SerializedName("posted_at") val postedAt: String? = null,
    val source: String = "notification",
)

/** Sunucunun cevabı — harcama değilse recorded=false döner, bu hata değildir */
data class IngestResult(
    val recorded: Boolean,
    val reason: String = "",
    val expense: Expense? = null,
)

data class ChatRequest(
    val message: String,
    @SerializedName("chat_id") val chatId: String = "mobile",
)

data class ChatResponse(val response: String)

data class HealthResponse(val status: String, val service: String)

data class MessageResponse(val message: String)
