package com.ssq2_and.solacesquad.ui

import android.app.Activity
import android.content.Context
import android.util.Log
import android.webkit.JavascriptInterface
import com.razorpay.Checkout
import org.json.JSONObject

class TokenBridge(
    private val context: Context,
    private val activityProvider: () -> Activity? = { null }
) {
    @Volatile
    private var token: String = ""

    @JavascriptInterface
    fun getFcmToken(): String {
        return token
    }

    fun setFcmToken(value: String) {
        token = value
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
