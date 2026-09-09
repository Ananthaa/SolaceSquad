package com.ssq2_and.solacesquad

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.WebView
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
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
import kotlinx.coroutines.delay

class MainActivity : FragmentActivity(), PaymentResultWithDataListener {
    private val initialPath = mutableStateOf<String?>(null)
    var currentWebView: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
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

    // Secure authentication flow status
    var isAuthenticated by remember { mutableStateOf(!SecurityHelper.isBiometricsAvailable(context)) }
    var authErrorMsg by remember { mutableStateOf<String?>(null) }

    // Token bridge definition with activity reference for native Razorpay Checkout
    val tokenBridge = remember { TokenBridge(context, activityProvider = { activity }) }

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

    // Biometric Security Lock activation
    if (!isAuthenticated) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = "SolaceSquad Secure Lock",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
                
                authErrorMsg?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(bottom = 16.dp)
                    )
                }

                Button(
                    onClick = {
                        SecurityHelper.authenticate(
                            activity = activity,
                            onSuccess = { isAuthenticated = true },
                            onFailure = { err -> authErrorMsg = err }
                        )
                    }
                ) {
                    Text("Unlock App")
                }
            }
        }

        LaunchedEffect(Unit) {
            SecurityHelper.authenticate(
                activity = activity,
                onSuccess = { isAuthenticated = true },
                onFailure = { err -> authErrorMsg = err }
            )
        }
        return
    }

    // Base URL definition
    val baseUrl = context.getString(R.string.app_base_url)
    var currentUrl by remember { mutableStateOf("$baseUrl/login") }

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

    val startUrl = if (!initialPath.isNullOrEmpty()) baseUrl + initialPath else "$baseUrl/login"

    WebViewWrapper(
        url = startUrl,
        tokenBridge = tokenBridge,
        modifier = Modifier.fillMaxSize(),
        onUrlChanged = { newUrl ->
            currentUrl = newUrl
        },
        onWebViewCreated = { webView ->
            webViewInstance = webView
            (activity as? MainActivity)?.currentWebView = webView
        }
    )
}
