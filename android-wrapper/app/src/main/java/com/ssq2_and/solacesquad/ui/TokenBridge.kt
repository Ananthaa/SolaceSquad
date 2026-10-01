package com.ssq2_and.solacesquad.ui

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.razorpay.Checkout
import com.ssq2_and.solacesquad.core.health.HealthConnectManager
import com.ssq2_and.solacesquad.core.security.SecurityHelper
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject

class TokenBridge(
    private val context: Context,
    private val activityProvider: () -> Activity? = { null },
    private val webViewProvider: () -> WebView? = { null }
) {
    @Volatile
    private var fcmToken: String = ""
    private val healthManager = HealthConnectManager(context)

    @JavascriptInterface
    fun getFcmToken(): String {
        return fcmToken
    }

    fun setFcmToken(value: String) {
        fcmToken = value
    }

    @JavascriptInterface
    fun saveAuthToken(token: String, email: String = "", name: String = "") {
        Log.i("TokenBridge", "saveAuthToken called from web")
        if (token.isNotEmpty()) {
            SecurityHelper.saveAuthToken(context, token)
            if (email.isNotEmpty() || name.isNotEmpty()) {
                SecurityHelper.saveUserDetails(context, email, name)
            }
        }
    }

    @JavascriptInterface
    fun getAuthToken(): String {
        return SecurityHelper.getAuthToken(context) ?: ""
    }

    @JavascriptInterface
    fun clearAuthToken() {
        Log.i("TokenBridge", "clearAuthToken called from web")
        SecurityHelper.clearAuthToken(context)
    }

    @JavascriptInterface
    fun syncHealthData() {
        Log.i("TokenBridge", "syncHealthData requested from Web")
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val jsonSummary = healthManager.getVitalsSummaryJson()
                val webView = webViewProvider()
                activityProvider()?.runOnUiThread {
                    val safeJson = jsonSummary.replace("'", "\\'")
                    webView?.evaluateJavascript(
                        "if (typeof window.onHealthSyncComplete === 'function') { window.onHealthSyncComplete(JSON.parse('$safeJson')); }",
                        null
                    )
                }
            } catch (e: Exception) {
                Log.e("TokenBridge", "Error syncing health data", e)
            }
        }
    }

    @JavascriptInterface
    fun openExternalBrowser(url: String) {
        Log.i("TokenBridge", "openExternalBrowser invoked for URL: $url")
        val activity = activityProvider() ?: (context as? Activity)
        activity?.runOnUiThread {
            try {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(intent)
            } catch (e: Exception) {
                Log.e("TokenBridge", "Failed to open external browser", e)
            }
        }
    }

    @JavascriptInterface
    fun openRazorpay(optionsJson: String) {
        Log.i("RazorpayBridge", "openRazorpay invoked from Web: $optionsJson")
        val activity = activityProvider() ?: (context as? Activity)
        if (activity == null) {
            Log.e("RazorpayBridge", "Activity is null, cannot open Razorpay")
            return
        }

        activity.runOnUiThread {
            try {
                Checkout.preload(activity.applicationContext)
                val checkout = Checkout()
                val options = JSONObject(optionsJson)
                if (options.has("key")) {
                    checkout.setKeyID(options.getString("key"))
                }
                checkout.open(activity, options)
            } catch (e: Exception) {
                Log.e("RazorpayBridge", "Exception opening Razorpay", e)
            }
        }
    }
}
