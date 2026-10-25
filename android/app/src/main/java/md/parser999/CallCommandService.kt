package md.parser999

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class CallCommandService : Service() {
    private val job = Job()
    private val scope = CoroutineScope(Dispatchers.IO + job)
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(1001, NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.sym_action_call)
            .setContentTitle("999 Call Companion")
            .setContentText("Ожидает одноразовую команду звонка")
            .setOngoing(true)
            .build())
        scope.launch { pollLoop() }
    }

    override fun onBind(intent: Intent?): IBinder? = null
    override fun onDestroy() { job.cancel(); client.dispatcher.executorService.shutdown(); super.onDestroy() }

    private suspend fun pollLoop() {
        while (scope.isActive) {
            try { pollOnce() } catch (_: Exception) { /* network failures are retried */ }
            delay(5_000)
        }
    }

    private fun pollOnce() {
        val prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE)
        val baseUrl = prefs.getString("server_url", "") ?: return
        val token = prefs.getString("api_token", "") ?: return
        val request = Request.Builder()
            .url("$baseUrl/api/android/commands/next")
            .header("Authorization", "Bearer $token")
            .get().build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return
            val raw = response.body?.string() ?: return
            if (raw == "null" || raw.isBlank()) return
            val json = JSONObject(raw)
            val requestId = json.getString("request_id")
            val phone = json.getString("phone")
            val handled = prefs.getStringSet("handled_ids", emptySet()) ?: emptySet()
            if (handled.contains(requestId)) {
                report(baseUrl, token, requestId, "rejected", "Duplicate command")
                return
            }
            val nextHandled = handled.toMutableSet().apply {
                add(requestId)
                while (size > 200) remove(first())
            }
            prefs.edit().putStringSet("handled_ids", nextHandled).apply()
            placeCall(baseUrl, token, requestId, phone)
        }
    }

    private fun placeCall(baseUrl: String, token: String, requestId: String, phone: String) {
        if (!Regex("^\\+373\\d{8}$").matches(phone)) {
            report(baseUrl, token, requestId, "rejected", "Invalid phone")
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            report(baseUrl, token, requestId, "failed", "CALL_PHONE permission missing")
            return
        }
        try {
            report(baseUrl, token, requestId, "dialing", null)
            val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$phone")).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
            report(baseUrl, token, requestId, "completed", "Call UI started via SIM")
        } catch (error: Exception) {
            report(baseUrl, token, requestId, "failed", error.message)
        }
    }

    private fun report(baseUrl: String, token: String, requestId: String, status: String, message: String?) {
        val body = JSONObject().put("status", status).put("message", message).toString()
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("$baseUrl/api/android/commands/$requestId/status")
            .header("Authorization", "Bearer $token")
            .post(body).build()
        client.newCall(request).execute().close()
    }

    private fun createChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Call commands", NotificationManager.IMPORTANCE_LOW))
    }

    companion object { const val CHANNEL = "call_commands" }
}
