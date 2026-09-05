package com.ssq2_and.solacesquad.ui

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Message
import android.webkit.*
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.ssq2_and.solacesquad.ui.TokenBridge

class FileCallbackHolder {
    var callback: ValueCallback<Array<Uri>>? = null
}

fun isNetworkAvailable(context: Context): Boolean {
    val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    val network = connectivityManager.activeNetwork ?: return false
    val activeNetwork = connectivityManager.getNetworkCapabilities(network) ?: return false
    return activeNetwork.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
           activeNetwork.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ||
           activeNetwork.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
}

@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun WebViewWrapper(
    url: String,
    tokenBridge: TokenBridge,
    modifier: Modifier = Modifier,
    onUrlChanged: (String) -> Unit = {},
    onWebViewCreated: (WebView) -> Unit = {}
) {
    val context = LocalContext.current
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }
    var isOffline by remember { mutableStateOf(!isNetworkAvailable(context)) }
    var isRefreshing by remember { mutableStateOf(false) }
    var loadingProgress by remember { mutableStateOf(0f) }

    val callbackHolder = remember { FileCallbackHolder() }
    val fileChooserLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents()
    ) { uris ->
        if (uris.isEmpty()) {
            callbackHolder.callback?.onReceiveValue(null)
        } else {
            callbackHolder.callback?.onReceiveValue(uris.toTypedArray())
        }
        callbackHolder.callback = null
    }

    Box(modifier = modifier.fillMaxSize()) {
        if (isOffline) {
            // Branded Material 3 Offline Fallback Screen
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Connection Offline",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(bottom = 12.dp)
                )

                Text(
                    text = "SolaceSquad requires an active internet connection to synchronize your wellbeing data. Please check your data connection and try again.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(bottom = 24.dp)
                )

                Button(
                    onClick = {
                        if (isNetworkAvailable(context)) {
                            isOffline = false
                            webViewInstance?.reload()
                        } else {
                            Toast.makeText(context, "Device is still offline.", Toast.LENGTH_SHORT).show()
                        }
                    }
                ) {
                    Text("Retry Connection")
                }
            }
        } else {
            PullToRefreshBox(
                isRefreshing = isRefreshing,
                onRefresh = {
                    isRefreshing = true
                    if (isNetworkAvailable(context)) {
                        webViewInstance?.reload()
                    } else {
                        isOffline = true
                        isRefreshing = false
                    }
                },
                modifier = Modifier.fillMaxSize()
            ) {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { ctx ->
                        WebView(ctx).apply {
                            // Enable Remote Chrome DevTools Debugging
                            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.KITKAT) {
                                WebView.setWebContentsDebuggingEnabled(true)
                            }

                            // Version-based cache clearing
                            try {
                                val packageInfo = ctx.packageManager.getPackageInfo(ctx.packageName, 0)
                                @Suppress("DEPRECATION")
                                val currentVersion = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
                                    packageInfo.longVersionCode
                                } else {
                                    packageInfo.versionCode.toLong()
                                }
                                val sharedPref = ctx.getSharedPreferences("ssq_app_prefs", Context.MODE_PRIVATE)
                                val savedVersion = sharedPref.getLong("ssq_app_version", -1)
                                if (savedVersion < currentVersion) {
                                    clearCache(true)
                                    sharedPref.edit().putLong("ssq_app_version", currentVersion).apply()
                                }
                            } catch (e: Exception) {
                                // Ignore
                            }

                            // Setup Cookies
                            val cookieManager = CookieManager.getInstance()
                            cookieManager.setAcceptCookie(true)
                            cookieManager.setAcceptThirdPartyCookies(this, true)

                            // WebView Client
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(
                                    view: WebView?,
                                    request: WebResourceRequest?
                                ): Boolean {
                                    val uri = request?.url ?: return false
                                    val urlString = uri.toString()
                                    val isMainFrame = request.isForMainFrame

                                    android.util.Log.e(
                                        "WebViewClientFlow",
                                        "shouldOverrideUrlLoading: url=$urlString, isMainFrame=$isMainFrame"
                                    )

                                    // Let standard HTTP/HTTPS page loads and iframes load naturally
                                    if (urlString.startsWith("http://") || urlString.startsWith("https://")) {
                                        return false
                                    }

                                    // Handle deep links (Razorpay UPI, GPay, PhonePe, Paytm, WhatsApp, Phone calls)
                                    try {
                                        android.util.Log.e("WebViewClientFlow", "Launching deep link: $urlString")
                                        val intent = if (urlString.startsWith("intent://")) {
                                            Intent.parseUri(urlString, Intent.URI_INTENT_SCHEME)
                                        } else {
                                            Intent(Intent.ACTION_VIEW, uri)
                                        }
                                        ctx.startActivity(intent)
                                        return true
                                    } catch (e: Exception) {
                                        android.util.Log.e("WebViewClientFlow", "Failed to launch deep link: $urlString", e)
                                        return true
                                    }
                                }

                                override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                                    super.onPageStarted(view, url, favicon)
                                    android.util.Log.e("WebViewClientFlow", "onPageStarted: $url")
                                    isRefreshing = true
                                }

                                override fun onPageFinished(view: WebView?, url: String?) {
                                    super.onPageFinished(view, url)
                                    android.util.Log.e("WebViewClientFlow", "onPageFinished: $url")
                                    isRefreshing = false
                                    loadingProgress = 0f
                                    // Flush cookies on load complete to ensure session persistence
                                    CookieManager.getInstance().flush()
                                    url?.let { onUrlChanged(it) }
                                }

                                override fun onReceivedError(
                                    view: WebView?,
                                    request: WebResourceRequest?,
                                    error: WebResourceError?
                                ) {
                                    super.onReceivedError(view, request, error)
                                    android.util.Log.e(
                                        "WebViewClientFlow",
                                        "onReceivedError: url=${request?.url}, code=${error?.errorCode}, desc=${error?.description}"
                                    )
                                    // Check if the primary URL load failed
                                    if (request?.isForMainFrame == true) {
                                        isOffline = true
                                        isRefreshing = false
                                    }
                                }

                                override fun onReceivedHttpError(
                                    view: WebView?,
                                    request: WebResourceRequest?,
                                    errorResponse: WebResourceResponse?
                                ) {
                                    super.onReceivedHttpError(view, request, errorResponse)
                                    android.util.Log.e(
                                        "WebViewClientFlow",
                                        "onReceivedHttpError: url=${request?.url}, statusCode=${errorResponse?.statusCode}"
                                    )
                                }

                                override fun onReceivedSslError(
                                    view: WebView?,
                                    handler: SslErrorHandler?,
                                    error: android.net.http.SslError?
                                ) {
                                    android.util.Log.e(
                                        "WebViewClientFlow",
                                        "onReceivedSslError: error=$error"
                                    )
                                    super.onReceivedSslError(view, handler, error)
                                }
                            }

                            // WebChrome Client (Permissions & File Chooser)
                            webChromeClient = object : WebChromeClient() {
                                override fun onProgressChanged(view: WebView?, newProgress: Int) {
                                    super.onProgressChanged(view, newProgress)
                                    loadingProgress = newProgress / 100f
                                }

                                override fun onPermissionRequest(request: PermissionRequest?) {
                                    request?.grant(request.resources)
                                }

                                override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                                    android.util.Log.e(
                                        "WebViewConsole",
                                        "${consoleMessage?.message()} -- From line ${consoleMessage?.lineNumber()} of ${consoleMessage?.sourceId()}"
                                    )
                                    return true
                                }

                                override fun onShowFileChooser(
                                    webView: WebView?,
                                    filePathCallback: ValueCallback<Array<Uri>>?,
                                    fileChooserParams: FileChooserParams?
                                ): Boolean {
                                    callbackHolder.callback?.onReceiveValue(null)
                                    callbackHolder.callback = filePathCallback
                                    try {
                                        fileChooserLauncher.launch("*/*")
                                    } catch (e: Exception) {
                                        callbackHolder.callback?.onReceiveValue(null)
                                        callbackHolder.callback = null
                                        return false
                                    }
                                    return true
                                }
                            }

                            // Settings
                            settings.apply {
                                javaScriptEnabled = true
                                domStorageEnabled = true
                                databaseEnabled = true
                                allowFileAccess = true
                                allowContentAccess = true
                                mediaPlaybackRequiresUserGesture = false // WebRTC Auto-play
                                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                                useWideViewPort = true
                                loadWithOverviewMode = true
                                javaScriptCanOpenWindowsAutomatically = true
                                setSupportMultipleWindows(false)
                                cacheMode = WebSettings.LOAD_NO_CACHE

                                // Mask WebView User Agent to standard Mobile Chrome to enable Razorpay Web/Google OAuth fallback
                                val defaultUa = userAgentString
                                val cleanedUa = defaultUa.replace("; wv", "").replace("Version/4.0 ", "")
                                userAgentString = "$cleanedUa SolaceSquadApp/Android"
                            }

                            addJavascriptInterface(tokenBridge, "AndroidBridge")
                            onWebViewCreated(this)
                            loadUrl(url)
                            webViewInstance = this
                        }
                    }
                )
            }
        }

        // Top Horizontal Progress Indicator for navigation loads
        if (loadingProgress > 0f && loadingProgress < 1f) {
            LinearProgressIndicator(
                progress = { loadingProgress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .align(Alignment.TopCenter),
                color = MaterialTheme.colorScheme.primary,
                trackColor = MaterialTheme.colorScheme.primaryContainer
            )
        }
    }
}
