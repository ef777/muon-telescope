package com.muon.telescope

import android.os.SystemClock
import com.muon.telescope.core.NtpSample
import com.muon.telescope.core.OffsetEstimator
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Maps the camera clock (SENSOR_TIMESTAMP, elapsedRealtime base when TIMESTAMP_SOURCE == REALTIME) to UTC.
 * utc_ns = elapsed_ns + offsetNs + driftPpm*1e-6*(elapsed_ns - refNs).
 * Method 3 of CLAUDE.md 4.3 (LAN NTP-like). GNSS and tap-sync are validation paths (see server/muon/timesync.py).
 */
class TimeSync(private val serverUrl: String) {
    @Volatile var offsetNs = 0.0; private set
    @Volatile var driftPpm = 0.0; private set
    @Volatile var refNs = 0L; private set
    @Volatile var sigmaNs = Double.NaN; private set
    @Volatile var synced = false; private set

    /** Server clock is wall time (UTC); client clock is elapsedRealtimeNanos. */
    fun sync(samples: Int = 60, keepFrac: Double = 0.2): Boolean {
        val all = ArrayList<NtpSample>()
        repeat(samples) {
            try {
                val t1 = SystemClock.elapsedRealtimeNanos()
                val c = URL("$serverUrl/sync").openConnection() as HttpURLConnection
                c.requestMethod = "POST"; c.doOutput = true; c.connectTimeout = 2000; c.readTimeout = 2000
                c.setRequestProperty("Content-Type", "application/json")
                c.outputStream.use { it.write("{\"t1\":$t1}".toByteArray()) }
                val body = c.inputStream.bufferedReader().readText()
                val t4 = SystemClock.elapsedRealtimeNanos()
                val j = JSONObject(body)
                all += NtpSample(t1, j.getLong("t2"), j.getLong("t3"), t4)
            } catch (_: Exception) { }
            Thread.sleep(50)
        }
        val f = OffsetEstimator.fit(all, keepFrac) ?: return false
        offsetNs = f.offsetNs; driftPpm = f.driftPpm; refNs = f.refNs; sigmaNs = f.sigmaNs
        synced = true
        return true
    }

    fun toUtcNs(elapsedNs: Long): Long =
        (elapsedNs + offsetNs + driftPpm * 1e-6 * (elapsedNs - refNs)).toLong()
}
