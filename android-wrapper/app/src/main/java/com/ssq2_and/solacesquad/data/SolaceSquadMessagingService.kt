package com.ssq2_and.solacesquad.data

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.ssq2_and.solacesquad.MainActivity

class SolaceSquadMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d("FCM_SERVICE", "Refreshed FCM Token: $token")
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)

        // Get notification content from message
        val title = remoteMessage.notification?.title ?: remoteMessage.data["title"] ?: "SolaceSquad"
        val body = remoteMessage.notification?.body ?: remoteMessage.data["body"] ?: ""
        val clickAction = remoteMessage.data["click_action"] ?: remoteMessage.data["path"] ?: ""

        sendNotification(title, body, clickAction)
    }

    private fun sendNotification(title: String, messageBody: String, clickAction: String) {
        val channelId = "solacesquad_reminders"
        val notificationId = System.currentTimeMillis().toInt()

        // Create notification click intent
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("path", clickAction) // E.g., "/vitals" or "/mood"
        }

        val pendingIntent = PendingIntent.getActivity(
            this,
            notificationId,
            intent,
            PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
        )

        val notificationBuilder = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_info) // System default icon for fallback
            .setContentTitle(title)
            .setContentText(messageBody)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setDefaults(NotificationCompat.DEFAULT_ALL)

        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // Create Notification Channel for Android 8.0+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "SolaceSquad Reminders",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Reminders for Mood, Vitals, and Appointments"
            }
            notificationManager.createNotificationChannel(channel)
        }

        notificationManager.notify(notificationId, notificationBuilder.build())
    }
}
