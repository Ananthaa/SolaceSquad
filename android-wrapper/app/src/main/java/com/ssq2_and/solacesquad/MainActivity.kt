package com.ssq2_and.solacesquad

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.webkit.WebView
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.ssq2_and.solacesquad.theme.SolaceSquadTheme
import com.ssq2_and.solacesquad.ui.WebViewWrapper
import com.ssq2_and.solacesquad.ui.TokenBridge
import com.google.firebase.messaging.FirebaseMessaging

class MainActivity : ComponentActivity() {
    private var initialPath = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Read path from notification click intent
        val path = intent?.getStringExtra("path")
        if (!path.isNullOrEmpty()) {
            initialPath.value = path
        }
        
        enableEdgeToEdge()
        setContent {
            SolaceSquadTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    AppScreen(initialPath = initialPath.value)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        val path = intent.getStringExtra("path")
        if (!path.isNullOrEmpty()) {
            initialPath.value = path
        }
    }
}

@Composable
fun AppScreen(initialPath: String? = null) {
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }
    val context = androidx.compose.ui.platform.LocalContext.current
    
    // Bridge to expose FCM token
    val tokenBridge = remember { TokenBridge(context) }
    
    // Retrieve FCM token on startup
    LaunchedEffect(Unit) {
        try {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    tokenBridge.setFcmToken(task.result ?: "")
                }
            }
        } catch (e: Exception) {
            // Firebase might not be initialized if google-services.json is missing
        }
    }

    // Intercept back button presses to navigate back in WebView history
    BackHandler(enabled = webViewInstance?.canGoBack() == true) {
        webViewInstance?.goBack()
    }

    // Dynamic Permission Requester on startup
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        // Permissions granted
    }

    LaunchedEffect(Unit) {
        val permissions = mutableListOf(
            Manifest.permission.CAMERA,
            Manifest.permission.RECORD_AUDIO
        )
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        permissionLauncher.launch(permissions.toTypedArray())
    }

    // Handle deep link path from notifications
    LaunchedEffect(initialPath) {
        if (!initialPath.isNullOrEmpty() && webViewInstance != null) {
            val baseUrl = "https://www.solacesquad.com"
            webViewInstance?.loadUrl(baseUrl + initialPath)
        }
    }

    Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
        val baseUrl = "https://www.solacesquad.com/login"
        val startUrl = if (!initialPath.isNullOrEmpty()) "https://www.solacesquad.com" + initialPath else baseUrl

        WebViewWrapper(
            url = startUrl,
            tokenBridge = tokenBridge,
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            onWebViewCreated = { webView ->
                webViewInstance = webView
            }
        )
    }
}
