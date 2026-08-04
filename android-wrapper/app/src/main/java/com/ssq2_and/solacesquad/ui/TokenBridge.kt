package com.ssq2_and.solacesquad.ui

import android.content.Context
import android.webkit.JavascriptInterface

class TokenBridge(private val context: Context) {
    @Volatile
    private var token: String = ""

    @JavascriptInterface
    fun getFcmToken(): String {
        return token
    }

    fun setFcmToken(value: String) {
        token = value
    }
}
