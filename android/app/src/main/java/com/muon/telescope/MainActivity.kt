package com.muon.telescope

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.io.File

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val json = try { CapabilityProbe.run(this).toString(2) } catch (e: Exception) { "{\"error\":\"$e\"}" }
        val file = File(getExternalFilesDir(null), "capabilities_${android.os.Build.MODEL.replace(' ', '_')}.json")
        file.writeText(json)
        setContent {
            MaterialTheme {
                Column(Modifier.fillMaxSize().statusBarsPadding().padding(12.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = {
                            (getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager)
                                .setPrimaryClip(ClipData.newPlainText("caps", json))
                            Toast.makeText(this@MainActivity, "Kopyalandı", Toast.LENGTH_SHORT).show()
                        }) { Text("Kopyala") }
                        Button(onClick = {
                            startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"; putExtra(Intent.EXTRA_TEXT, json) }, "Paylaş"))
                        }) { Text("Paylaş") }
                    }
                    Text("Kaydedildi: ${file.absolutePath}", fontSize = 10.sp)
                    SelectionContainer {
                        Text(json, fontSize = 10.sp, modifier = Modifier.verticalScroll(rememberScrollState()))
                    }
                }
            }
        }
    }
}
