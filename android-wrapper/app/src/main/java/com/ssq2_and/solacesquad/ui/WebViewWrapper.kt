package com.ssq2_and.solacesquad.ui

import android.annotation.SuppressLint
import android.net.Uri
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView

class FileCallbackHolder {
    var callback: ValueCallback<Array<Uri>>? = null
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun WebViewWrapper(
    url: String,
    tokenBridge: TokenBridge,
    modifier: Modifier = Modifier,
    onWebViewCreated: (WebView) -> Unit = {}
) {
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

    AndroidView(
        modifier = modifier.fillMaxSize(),
        factory = { context ->
            WebView(context).apply {
                // Clear WebView cache once on app version upgrade to force load fresh styles
                try {
                    val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
                    @Suppress("DEPRECATION")
                    val currentVersion = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
                        packageInfo.longVersionCode
                    } else {
                        packageInfo.versionCode.toLong()
                    }
                    val sharedPref = context.getSharedPreferences("ssq_app_prefs", android.content.Context.MODE_PRIVATE)
                    val savedVersion = sharedPref.getLong("ssq_app_version", -1)
                    if (savedVersion < currentVersion) {
                        clearCache(true)
                        sharedPref.edit().putLong("ssq_app_version", currentVersion).apply()
                    }
                } catch (e: Exception) {
                    // Ignore package manager failure
                }

                // Configure Cookie Manager
                val cookieManager = CookieManager.getInstance()
                cookieManager.setAcceptCookie(true)
                cookieManager.setAcceptThirdPartyCookies(this, true)

                // Configure WebView Client
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                        // Keep navigation inside the WebView
                        if (url != null) {
                            view?.loadUrl(url)
                        }
                        return true
                    }
                }

                // Configure WebChrome Client for WebRTC permissions and file chooser
                webChromeClient = object : WebChromeClient() {
                    override fun onPermissionRequest(request: PermissionRequest?) {
                        // Grant runtime camera/microphone permissions requested by WebRTC inside WebView
                        request?.grant(request.resources)
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

                // Apply WebView settings
                settings.apply {
                    javaScriptEnabled = true
                    domStorageEnabled = true
                    databaseEnabled = true
                    allowFileAccess = true
                    allowContentAccess = true
                    mediaPlaybackRequiresUserGesture = false // Crucial for WebRTC auto-play
                    mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                    useWideViewPort = true
                    loadWithOverviewMode = true
                    javaScriptCanOpenWindowsAutomatically = true
                }

                // Register Javascript bridge interface
                addJavascriptInterface(tokenBridge, "AndroidBridge")

                onWebViewCreated(this)
                loadUrl(url)
            }
        },
        update = { webView ->
            // Let the WebView self-manage internal navigation
        }
    )
}
