package com.eyup.prism

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Payments
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.sp
import com.eyup.prism.data.SettingsStore
import com.eyup.prism.data.api.ApiClient
import com.eyup.prism.ui.screens.ChatScreen
import com.eyup.prism.ui.screens.ExpensesScreen
import com.eyup.prism.ui.screens.NotesScreen
import com.eyup.prism.ui.screens.RemindersScreen
import com.eyup.prism.ui.screens.SettingsScreen
import com.eyup.prism.ui.theme.PRISMTheme
import com.eyup.prism.ui.theme.PrismPurple
import com.eyup.prism.ui.theme.PrismPurpleLight
import com.eyup.prism.ui.theme.PrismSurface
import com.eyup.prism.ui.theme.PrismTextFaint

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            PrismApp()
        }
    }
}

private data class TabItem(val label: String, val icon: ImageVector)

@Composable
fun PrismApp() {
    val context = LocalContext.current
    val store = remember { SettingsStore(context.applicationContext) }
    val settings by store.settings.collectAsState(initial = null)
    var tabIndex by rememberSaveable { mutableIntStateOf(0) }
    var autoRedirected by rememberSaveable { mutableStateOf(false) }

    // Ayarlar yüklenince API istemcisini kur; ilk kurulumda Ayarlar sekmesine yönlendir
    LaunchedEffect(settings) {
        val s = settings ?: return@LaunchedEffect
        ApiClient.configure(s.baseUrl, s.apiKey)
        if (!autoRedirected) {
            autoRedirected = true
            if (!s.isConfigured) tabIndex = 4
        }
    }

    val tabs = listOf(
        TabItem("Chat", Icons.AutoMirrored.Filled.Chat),
        TabItem("Görevler", Icons.Filled.Notifications),
        TabItem("Notlar", Icons.Filled.Description),
        TabItem("Harcama", Icons.Filled.Payments),
        TabItem("Ayarlar", Icons.Filled.Settings),
    )

    PRISMTheme {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            bottomBar = {
                NavigationBar(containerColor = PrismSurface) {
                    tabs.forEachIndexed { index, tab ->
                        NavigationBarItem(
                            selected = tabIndex == index,
                            onClick = { tabIndex = index },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label, fontSize = 11.sp) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = PrismPurpleLight,
                                selectedTextColor = PrismPurpleLight,
                                indicatorColor = PrismPurple.copy(alpha = 0.2f),
                                unselectedIconColor = PrismTextFaint,
                                unselectedTextColor = PrismTextFaint,
                            ),
                        )
                    }
                }
            },
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                when (tabIndex) {
                    0 -> ChatScreen()
                    1 -> RemindersScreen()
                    2 -> NotesScreen()
                    3 -> ExpensesScreen()
                    else -> SettingsScreen(store)
                }
            }
        }
    }
}
