package md.parser999

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import md.parser999.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) startCompanion()
        else binding.statusText.text = "Нужно разрешение на телефонные вызовы"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        binding.serverUrl.setText(prefs.getString("server_url", ""))
        binding.apiToken.setText(prefs.getString("api_token", ""))
        binding.startButton.setOnClickListener { validateAndRequestPermissions() }
        binding.stopButton.setOnClickListener {
            stopService(Intent(this, CallCommandService::class.java))
            binding.statusText.text = "Сервис остановлен"
        }
    }

    private fun validateAndRequestPermissions() {
        val url = binding.serverUrl.text.toString().trim().trimEnd('/')
        val token = binding.apiToken.text.toString().trim()
        if (!url.startsWith("https://") || token.length < 32) {
            binding.statusText.text = "Нужны HTTPS URL и токен длиной не менее 32 символов"
            return
        }
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
            .putString("server_url", url)
            .putString("api_token", token)
            .apply()
        val needed = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.CALL_PHONE)
        }
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (needed.isEmpty()) startCompanion() else permissionLauncher.launch(needed.toTypedArray())
    }

    private fun startCompanion() {
        ContextCompat.startForegroundService(this, Intent(this, CallCommandService::class.java))
        binding.statusText.text = "Сервис запущен"
    }

    companion object { const val PREFS = "companion_settings" }
}
