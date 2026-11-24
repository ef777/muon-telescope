package com.muon.telescope

import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Offline-first: events are appended to JSONL spool files first; a batch is deleted only after the server
 * acknowledged it. The server ingest is idempotent (device_id + frame_idx + cluster_idx), so retries are safe.
 */
class Uploader(private val dir: File, private val serverUrl: String, private val batchSize: Int = 200) {
    private val spool = File(dir, "spool.jsonl").also { dir.mkdirs() }

    @Synchronized fun enqueue(jsonLine: String) { spool.appendText(jsonLine + "\n") }

    @Synchronized fun flush(): Int {
        if (!spool.exists()) return 0
        val lines = spool.readLines().filter { it.isNotBlank() }
        var sent = 0
        var i = 0
        while (i < lines.size) {
            val chunk = lines.subList(i, minOf(i + batchSize, lines.size))
            if (!post("[" + chunk.joinToString(",") + "]")) break
            sent += chunk.size; i += chunk.size
        }
        spool.writeText(lines.drop(sent).joinToString("\n") + if (sent < lines.size) "\n" else "")
        return sent
    }

    private fun post(body: String): Boolean = try {
        val c = URL("$serverUrl/ingest").openConnection() as HttpURLConnection
        c.requestMethod = "POST"; c.doOutput = true; c.connectTimeout = 3000; c.readTimeout = 10000
        c.setRequestProperty("Content-Type", "application/json")
        c.outputStream.use { it.write(body.toByteArray()) }
        c.responseCode in 200..299
    } catch (_: Exception) { false }
}
