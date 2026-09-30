package com.ssq2_and.solacesquad.core.security

import android.content.Context
import android.content.SharedPreferences
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object SecurityHelper {
    private const val PREFS_FILE = "solacesquad_secure_prefs"
    private const val KEY_AUTH_TOKEN = "session_auth_token"

    private fun getEncryptedPrefs(context: Context): SharedPreferences {
        return try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            EncryptedSharedPreferences.create(
                context,
                PREFS_FILE,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            android.util.Log.e("SecurityHelper", "EncryptedSharedPreferences init failed, resetting corrupted keystore prefs", e)
            try {
                context.deleteSharedPreferences(PREFS_FILE)
                val masterKey = MasterKey.Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build()
                EncryptedSharedPreferences.create(
                    context,
                    PREFS_FILE,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                )
            } catch (e2: Exception) {
                android.util.Log.e("SecurityHelper", "Falling back to standard private SharedPreferences", e2)
                context.getSharedPreferences("solacesquad_fallback_prefs", Context.MODE_PRIVATE)
            }
        }
    }

    fun saveAuthToken(context: Context, token: String) {
        try {
            getEncryptedPrefs(context).edit().putString(KEY_AUTH_TOKEN, token).apply()
        } catch (e: Exception) {
            android.util.Log.e("SecurityHelper", "Error saving auth token", e)
        }
    }

    fun saveUserDetails(context: Context, email: String, name: String) {
        try {
            getEncryptedPrefs(context).edit()
                .putString("user_email", email)
                .putString("user_name", name)
                .apply()
        } catch (e: Exception) {
            android.util.Log.e("SecurityHelper", "Error saving user details", e)
        }
    }

    fun getUserEmail(context: Context): String? {
        return try {
            getEncryptedPrefs(context).getString("user_email", null)
        } catch (e: Exception) {
            null
        }
    }

    fun getUserName(context: Context): String? {
        return try {
            getEncryptedPrefs(context).getString("user_name", null)
        } catch (e: Exception) {
            null
        }
    }

    fun getAuthToken(context: Context): String? {
        return try {
            getEncryptedPrefs(context).getString(KEY_AUTH_TOKEN, null)
        } catch (e: Exception) {
            null
        }
    }

    fun clearAuthToken(context: Context) {
        try {
            getEncryptedPrefs(context).edit()
                .remove(KEY_AUTH_TOKEN)
                .remove("user_email")
                .remove("user_name")
                .apply()
        } catch (e: Exception) {
            android.util.Log.e("SecurityHelper", "Error clearing auth token", e)
        }
    }

    fun isBiometricsAvailable(context: Context): Boolean {
        return try {
            val biometricManager = BiometricManager.from(context)
            biometricManager.canAuthenticate(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
            ) == BiometricManager.BIOMETRIC_SUCCESS
        } catch (e: Throwable) {
            false
        }
    }

    fun authenticate(
        activity: FragmentActivity,
        title: String = "SolaceSquad Security Lock",
        subtitle: String = "Authenticate to access your dashboard",
        onSuccess: () -> Unit,
        onFailure: (String) -> Unit
    ) {
        try {
            if (!isBiometricsAvailable(activity)) {
                onSuccess()
                return
            }

            val executor = ContextCompat.getMainExecutor(activity)
            val biometricPrompt = BiometricPrompt(
                activity,
                executor,
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                        super.onAuthenticationError(errorCode, errString)
                        onFailure(errString.toString())
                    }

                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        super.onAuthenticationSucceeded(result)
                        onSuccess()
                    }

                    override fun onAuthenticationFailed() {
                        super.onAuthenticationFailed()
                        onFailure("Authentication failed. Please try again.")
                    }
                }
            )

            val promptInfo = BiometricPrompt.PromptInfo.Builder()
                .setTitle(title)
                .setSubtitle(subtitle)
                .setAllowedAuthenticators(
                    BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
                )
                .build()

            biometricPrompt.authenticate(promptInfo)
        } catch (e: Throwable) {
            android.util.Log.e("SecurityHelper", "Biometric authentication failed to initialize", e)
            onSuccess() // Fallback gracefully if prompt crashes
        }
    }
}
