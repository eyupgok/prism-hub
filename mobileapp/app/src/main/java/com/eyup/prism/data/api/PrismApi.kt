package com.eyup.prism.data.api

import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/** PRISM backend REST API — web paneldeki client.js'in Kotlin karşılığı */
interface PrismApi {

    @GET("health")
    suspend fun health(): HealthResponse

    // ── Chat ─────────────────────────────────────────────────────────────
    @POST("api/chat/")
    suspend fun chat(@Body body: ChatRequest): ChatResponse

    // ── Hatırlatıcılar ───────────────────────────────────────────────────
    @GET("api/reminders/")
    suspend fun getReminders(
        @Query("include_completed") includeCompleted: Boolean = false,
    ): List<Reminder>

    @POST("api/reminders/")
    suspend fun createReminder(@Body body: ReminderCreate): Reminder

    @PUT("api/reminders/{id}/complete")
    suspend fun completeReminder(@Path("id") id: Int): Reminder

    @PUT("api/reminders/{id}/snooze/{minutes}")
    suspend fun snoozeReminder(@Path("id") id: Int, @Path("minutes") minutes: Int): Reminder

    @DELETE("api/reminders/{id}")
    suspend fun deleteReminder(@Path("id") id: Int): MessageResponse

    // ── Notlar ───────────────────────────────────────────────────────────
    @GET("api/notes/")
    suspend fun getNotes(@Query("category") category: String? = null): List<Note>

    @GET("api/notes/search")
    suspend fun searchNotes(
        @Query("q") query: String,
        @Query("category") category: String? = null,
    ): List<Note>

    @POST("api/notes/")
    suspend fun createNote(@Body body: NoteCreate): Note

    @DELETE("api/notes/{id}")
    suspend fun deleteNote(@Path("id") id: Int): MessageResponse

    // ── Harcamalar ───────────────────────────────────────────────────────
    @GET("api/expenses/")
    suspend fun getExpenses(
        @Query("month") month: String? = null,
        @Query("category") category: String? = null,
    ): List<Expense>

    @GET("api/expenses/summary")
    suspend fun getExpenseSummary(@Query("month") month: String? = null): ExpenseSummary

    @POST("api/expenses/")
    suspend fun createExpense(@Body body: ExpenseCreate): Expense

    @DELETE("api/expenses/{id}")
    suspend fun deleteExpense(@Path("id") id: Int): MessageResponse

    /** Banka bildirimini sunucuya yollar; sunucu harcamaysa kaydeder */
    @POST("api/expenses/ingest")
    suspend fun ingestNotification(@Body body: NotificationIngest): IngestResult
}
