package com.eyup.prism.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Payments
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.data.api.Expense
import com.eyup.prism.data.api.ExpenseCreate
import com.eyup.prism.data.api.ExpenseSummary
import com.eyup.prism.data.api.describeError
import com.eyup.prism.ui.components.DotBadge
import com.eyup.prism.ui.components.EmptyState
import com.eyup.prism.ui.components.ErrorBanner
import com.eyup.prism.ui.components.ScreenHeader
import com.eyup.prism.ui.theme.CategoryColors
import com.eyup.prism.ui.theme.PrismGreen
import com.eyup.prism.ui.theme.PrismPurple
import com.eyup.prism.ui.theme.PrismSurface2
import com.eyup.prism.ui.theme.PrismText
import com.eyup.prism.ui.theme.PrismTextFaint
import com.eyup.prism.ui.theme.PrismTextMuted
import com.eyup.prism.util.TURKISH_MONTHS
import kotlinx.coroutines.launch
import java.time.YearMonth
import java.util.Locale

private val EXPENSE_CATEGORIES = listOf("yemek", "ulaşım", "eğlence", "fatura", "alışveriş", "diğer")
private val CATEGORY_EMOJIS = mapOf(
    "yemek" to "🍔", "ulaşım" to "🚗", "eğlence" to "🎮",
    "fatura" to "💡", "alışveriş" to "🛒", "diğer" to "📦",
)

private fun formatAmount(value: Double): String =
    String.format(Locale.forLanguageTag("tr-TR"), "%,.0f ₺", value)

class ExpensesViewModel : ViewModel() {
    var month by mutableStateOf(YearMonth.now())
    var expenses by mutableStateOf<List<Expense>>(emptyList())
        private set
    var summary by mutableStateOf<ExpenseSummary?>(null)
        private set
    var loading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    private fun monthParam(): String = "%04d-%02d".format(month.year, month.monthValue)

    fun load() {
        viewModelScope.launch {
            loading = true
            error = null
            try {
                expenses = ApiClient.api().getExpenses(monthParam())
                summary = ApiClient.api().getExpenseSummary(monthParam())
            } catch (e: Exception) {
                error = describeError(e)
            }
            loading = false
        }
    }

    fun shiftMonth(delta: Long) {
        month = month.plusMonths(delta)
        load()
    }

    fun create(body: ExpenseCreate) {
        viewModelScope.launch {
            error = null
            try {
                ApiClient.api().createExpense(body)
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
                ApiClient.api().deleteExpense(id)
                load()
            } catch (e: Exception) {
                error = describeError(e)
            }
        }
    }
}

@Composable
fun ExpensesScreen(vm: ExpensesViewModel = viewModel()) {
    var showCreate by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        if (vm.expenses.isEmpty() && vm.summary == null) vm.load()
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ScreenHeader(
                    "Harcamalar",
                    "${TURKISH_MONTHS[vm.month.monthValue - 1]} ${vm.month.year}",
                )
                Row {
                    IconButton(onClick = { vm.shiftMonth(-1) }) {
                        Icon(
                            Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                            contentDescription = "Önceki ay",
                            tint = PrismTextMuted,
                        )
                    }
                    IconButton(onClick = { vm.shiftMonth(1) }) {
                        Icon(
                            Icons.AutoMirrored.Filled.KeyboardArrowRight,
                            contentDescription = "Sonraki ay",
                            tint = PrismTextMuted,
                        )
                    }
                }
            }

            vm.error?.let {
                ErrorBanner(it)
                Spacer(Modifier.height(8.dp))
            }

            if (vm.loading && vm.summary == null) {
                Box(Modifier.fillMaxWidth().padding(vertical = 48.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = PrismPurple)
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(bottom = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    vm.summary?.let { s ->
                        item { SummaryCard(s) }
                    }
                    if (vm.expenses.isEmpty()) {
                        item { EmptyState(Icons.Filled.Payments, "Bu ay harcama kaydı yok") }
                    } else {
                        items(vm.expenses, key = { it.id }) { expense ->
                            ExpenseRow(expense, onDelete = { vm.delete(expense.id) })
                        }
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
            Icon(Icons.Filled.Add, contentDescription = "Yeni harcama")
        }
    }

    if (showCreate) {
        CreateExpenseDialog(
            onDismiss = { showCreate = false },
            onCreate = { body ->
                vm.create(body)
                showCreate = false
            },
        )
    }
}

@Composable
private fun SummaryCard(summary: ExpenseSummary) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrismSurface2, RoundedCornerShape(16.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("Toplam", color = PrismTextFaint, fontSize = 12.sp)
        Text(
            formatAmount(summary.total),
            color = PrismText,
            fontSize = 26.sp,
            fontWeight = FontWeight.Bold,
        )
        summary.byCategory.entries.sortedByDescending { it.value }.forEach { (cat, total) ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                DotBadge(CategoryColors[cat] ?: Color.Gray, 8.dp)
                Text(
                    "  ${CATEGORY_EMOJIS[cat] ?: ""} $cat",
                    color = PrismTextMuted,
                    fontSize = 13.sp,
                    modifier = Modifier.weight(1f),
                )
                Text(formatAmount(total), color = PrismText, fontSize = 13.sp)
            }
        }
    }
}

@Composable
private fun ExpenseRow(expense: Expense, onDelete: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrismSurface2, RoundedCornerShape(14.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(CATEGORY_EMOJIS[expense.category] ?: "📦", fontSize = 20.sp)
        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            Text(
                expense.description.ifBlank { expense.category },
                color = PrismText,
                fontSize = 14.sp,
            )
            Text(expense.expenseDate, color = PrismTextFaint, fontSize = 12.sp)
        }
        // Negatif tutar iade demek — yeşil ve artı işaretiyle gösterilir,
        // böylece listede harcamadan ayırt edilir (panelde de aynı gösterim var)
        val refund = expense.amount < 0
        Text(
            if (refund) "+ ${formatAmount(-expense.amount)}" else formatAmount(expense.amount),
            color = if (refund) PrismGreen else PrismText,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
        )
        IconButton(onClick = onDelete) {
            Icon(Icons.Filled.Delete, contentDescription = "Sil", tint = PrismTextFaint)
        }
    }
}

@Composable
private fun CreateExpenseDialog(onDismiss: () -> Unit, onCreate: (ExpenseCreate) -> Unit) {
    var amount by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("yemek") }
    var description by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = PrismSurface2,
        title = { Text("Yeni Harcama", color = PrismText) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it.replace(',', '.') },
                    label = { Text("Tutar (TL)") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("Açıklama (opsiyonel)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(EXPENSE_CATEGORIES) { cat ->
                        FilterChip(
                            selected = category == cat,
                            onClick = { category = cat },
                            label = { Text("${CATEGORY_EMOJIS[cat]} $cat", fontSize = 12.sp) },
                            colors = prismChipColors(),
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val value = amount.toDoubleOrNull() ?: return@Button
                    onCreate(ExpenseCreate(value, category, description.trim()))
                },
                // Negatif tutar geçerlidir (iade); sadece sıfır ve boş engellenir
                enabled = (amount.toDoubleOrNull() ?: 0.0) != 0.0,
                colors = ButtonDefaults.buttonColors(containerColor = PrismPurple),
            ) { Text("Ekle") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("İptal", color = PrismTextMuted) }
        },
    )
}
