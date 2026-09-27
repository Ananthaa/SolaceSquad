package com.ssq2_and.solacesquad.core.compliance

import android.content.Context
import android.webkit.CookieManager
import android.webkit.WebView
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.ssq2_and.solacesquad.core.security.SecurityHelper

object ConsentManager {
    private const val PREFS_COMPLIANCE = "solacesquad_compliance_prefs"
    private const val KEY_BIOMETRIC_CONSENT = "biometric_data_consent_granted"

    fun setBiometricConsent(context: Context, granted: Boolean) {
        val prefs = context.getSharedPreferences(PREFS_COMPLIANCE, Context.MODE_PRIVATE)
        prefs.edit().putBoolean(KEY_BIOMETRIC_CONSENT, granted).apply()
    }

    fun hasBiometricConsent(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS_COMPLIANCE, Context.MODE_PRIVATE)
        return prefs.getBoolean(KEY_BIOMETRIC_CONSENT, false)
    }

    /**
     * DPDP-Compliant Biometric & Face Scan Consent Dialog.
     * Implements Section 6 of the DPDP Act 2023 (India) and HIPAA privacy notices.
     */
    @Composable
    fun ConsentPrompt(
        onConsentGranted: () -> Unit,
        onConsentDenied: () -> Unit
    ) {
        Dialog(onDismissRequest = onConsentDenied) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 8.dp,
                modifier = Modifier.padding(16.dp)
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "Consent for Biometric Face Processing",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(bottom = 12.dp)
                    )

                    Text(
                        text = "In compliance with the India DPDP Act 2023 and HIPAA standards, we require your explicit consent to process your camera feed for wellbeing scans.\n\n" +
                               "• Your face scan is processed entirely in-memory to estimate heart vitals.\n" +
                               "• Zero biometric datasets or images are stored locally or shared with external parties.\n" +
                               "• You can withdraw this consent at any time from Settings.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(bottom = 24.dp)
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        OutlinedButton(
                            onClick = onConsentDenied,
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("Decline")
                        }

                        Button(
                            onClick = onConsentGranted,
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("I Consent")
                        }
                    }
                }
            }
        }
    }

    /**
     * DPDP Right to Erasure / Right to be Forgotten.
     * Wipes local sessions, stored authentication tokens, WebView cache, and cookies.
     */
    fun performRightToErasure(context: Context, webView: WebView?) {
        // 1. Clear secure preference tokens
        SecurityHelper.clearAuthToken(context)
        setBiometricConsent(context, false)

        // 2. Clear Cookie Manager instance
        val cookieManager = CookieManager.getInstance()
        cookieManager.removeAllCookies(null)
        cookieManager.flush()

        // 3. Clear WebView Cache, storage, and databases
        webView?.let {
            it.clearCache(true)
            it.clearHistory()
            it.clearFormData()
        }
    }
}
