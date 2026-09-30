package com.ssq2_and.solacesquad

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import android.webkit.CookieManager
import android.webkit.WebView
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import com.google.firebase.messaging.FirebaseMessaging
import com.razorpay.PaymentData
import com.razorpay.PaymentResultWithDataListener
import com.ssq2_and.solacesquad.core.security.SecurityHelper
import com.ssq2_and.solacesquad.theme.SolaceSquadTheme
import com.ssq2_and.solacesquad.ui.TokenBridge
import com.ssq2_and.solacesquad.ui.WebViewWrapper
import com.ssq2_and.solacesquad.ui.navigation.NativeBottomBar
import com.ssq2_and.solacesquad.ui.navigation.TabItem
import kotlinx.coroutines.delay

class MainActivity : FragmentActivity(), PaymentResultWithDataListener {
    private val initialPath = mutableStateOf<String?>(null)
    var currentWebView: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Uncaught exception logger
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            android.util.Log.e("SolaceSquadCrash", "FATAL CRASH on ${thread.name}", throwable)
            defaultHandler?.uncaughtException(thread, throwable)
        }

        // Read path from notification click intent
        val path = intent?.getStringExtra("path")
        if (!path.isNullOrEmpty()) {
            initialPath.value = path
        }
        
        setContentLayout()
    }

    override fun onPaymentSuccess(razorpayPaymentID: String?, paymentData: PaymentData?) {
        val paymentId = razorpayPaymentID ?: (paymentData?.paymentId ?: "")
        val orderId = paymentData?.orderId ?: ""
        val signature = paymentData?.signature ?: ""
        
        val js = """
            if (typeof window.handleNativeRazorpaySuccess === 'function') {
                window.handleNativeRazorpaySuccess({
                    razorpay_payment_id: '$paymentId',
                    razorpay_order_id: '$orderId',
                    razorpay_signature: '$signature'
                });
            }
        """.trimIndent()
        
        currentWebView?.post {
            currentWebView?.evaluateJavascript(js, null)
        }
    }

    override fun onPaymentError(code: Int, response: String?, paymentData: PaymentData?) {
        val safeResponse = (response ?: "Payment cancelled").replace("'", "\\'")
        val js = """
            if (typeof window.handleNativeRazorpayError === 'function') {
                window.handleNativeRazorpayError($code, '$safeResponse');
            }
        """.trimIndent()
        
        currentWebView?.post {
            currentWebView?.evaluateJavascript(js, null)
        }
    }

    private fun setContentLayout() {
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

    override fun onPause() {
        super.onPause()
        // Force sync cookies when app goes to background
        CookieManager.getInstance().flush()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppScreen(initialPath: String? = null) {
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }
    val context = LocalContext.current
    val activity = context as FragmentActivity

    // Token bridge definition with activity and webView reference
    val tokenBridge = remember { 
        TokenBridge(
            context = context, 
            activityProvider = { activity },
            webViewProvider = { webViewInstance }
        ) 
    }

    // Double back press exit logic
    var backPressCount by remember { mutableStateOf(0) }
    LaunchedEffect(backPressCount) {
        if (backPressCount > 0) {
            delay(2000)
            backPressCount = 0
        }
    }

    // Retrieve FCM token on startup
    LaunchedEffect(Unit) {
        try {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    tokenBridge.setFcmToken(task.result ?: "")
                }
            }
        } catch (e: Exception) {
            // Firebase may not be configured locally
        }
    }

    // Base URL definition
    val baseUrl = context.getString(R.string.app_base_url)
    var currentUrl by remember { mutableStateOf("$baseUrl/app-start") }
    var selectedTab by remember { mutableStateOf(TabItem.HOME) }
    val showBottomBar = remember(currentUrl) { !TabItem.isAuthOrCallRoom(currentUrl) }

    // Call Room Wake Lock management
    LaunchedEffect(currentUrl) {
        val inCall = currentUrl.contains("call_room") ||
                     currentUrl.contains("call-room") ||
                     currentUrl.contains("quick-consult/room")
        if (inCall) {
            activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    // Intercept back button
    BackHandler(enabled = true) {
        if (webViewInstance?.canGoBack() == true) {
            webViewInstance?.goBack()
        } else {
            // Root path reached - prompt to exit app
            if (backPressCount == 0) {
                backPressCount++
                Toast.makeText(context, "Press back again to exit.", Toast.LENGTH_SHORT).show()
            } else {
                activity.finish()
            }
        }
    }

    // Request permissions dynamically
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

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

    // Handle initial paths or notification clicks
    LaunchedEffect(initialPath) {
        if (!initialPath.isNullOrEmpty() && webViewInstance != null) {
            webViewInstance?.loadUrl(baseUrl + initialPath)
        }
    }

    val startUrl = if (!initialPath.isNullOrEmpty()) baseUrl + initialPath else "$baseUrl/app-start"

    Scaffold(
        bottomBar = {
            NativeBottomBar(
                selectedTab = selectedTab,
                isVisible = showBottomBar,
                onTabSelected = { tab ->
                    selectedTab = tab
                    webViewInstance?.loadUrl(baseUrl + tab.path)
                }
            )
        }
    ) { paddingValues ->
        WebViewWrapper(
            url = startUrl,
            tokenBridge = tokenBridge,
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
            onUrlChanged = { newUrl ->
                currentUrl = newUrl
                selectedTab = TabItem.fromUrl(newUrl)
            },
            onWebViewCreated = { webView ->
                webViewInstance = webView
                (activity as? MainActivity)?.currentWebView = webView
            }
        )
    }
}
