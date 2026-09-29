package com.ssq2_and.solacesquad.core.health

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.OxygenSaturationRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit

class HealthConnectManager(private val context: Context) {

    val healthConnectClient: HealthConnectClient? by lazy {
        if (HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE) {
            HealthConnectClient.getOrCreate(context)
        } else {
            null
        }
    }

    val permissions = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(HeartRateRecord::class),
        HealthPermission.getReadPermission(OxygenSaturationRecord::class)
    )

    fun isAvailable(): Boolean {
        return HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE
    }

    suspend fun hasPermissions(): Boolean {
        val client = healthConnectClient ?: return false
        val granted = client.permissionController.getGrantedPermissions()
        return granted.containsAll(permissions)
    }

    suspend fun readTodaySteps(): Long {
        val client = healthConnectClient ?: return 0
        try {
            val startOfDay = LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant()
            val now = Instant.now()
            val response = client.aggregate(
                AggregateRequest(
                    metrics = setOf(StepsRecord.COUNT_TOTAL),
                    timeRangeFilter = TimeRangeFilter.between(startOfDay, now)
                )
            )
            return response[StepsRecord.COUNT_TOTAL] ?: 0L
        } catch (e: Exception) {
            android.util.Log.e("HealthConnect", "Error reading steps", e)
            return 0L
        }
    }

    suspend fun readLatestHeartRate(): Double? {
        val client = healthConnectClient ?: return null
        try {
            val endTime = Instant.now()
            val startTime = endTime.minus(24, ChronoUnit.HOURS)
            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = HeartRateRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startTime, endTime),
                    ascendingOrder = false,
                    pageSize = 1
                )
            )
            val record = response.records.firstOrNull() ?: return null
            return record.samples.lastOrNull()?.beatsPerMinute?.toDouble()
        } catch (e: Exception) {
            android.util.Log.e("HealthConnect", "Error reading heart rate", e)
            return null
        }
    }

    suspend fun readLatestSpO2(): Double? {
        val client = healthConnectClient ?: return null
        try {
            val endTime = Instant.now()
            val startTime = endTime.minus(24, ChronoUnit.HOURS)
            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = OxygenSaturationRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startTime, endTime),
                    ascendingOrder = false,
                    pageSize = 1
                )
            )
            val record = response.records.firstOrNull() ?: return null
            return record.percentage.value
        } catch (e: Exception) {
            android.util.Log.e("HealthConnect", "Error reading SpO2", e)
            return null
        }
    }

    suspend fun getVitalsSummaryJson(): String {
        val steps = readTodaySteps()
        val hr = readLatestHeartRate()
        val spo2 = readLatestSpO2()

        val json = JSONObject()
        json.put("steps", steps)
        if (hr != null) json.put("heart_rate", hr.toInt())
        if (spo2 != null) json.put("spo2", spo2)
        json.put("source", "HealthConnect")
        return json.toString()
    }
}
