package com.muon.telescope

import android.os.SystemClock
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

    private data class S(val t1: Long, val t2: Long, val t3: Long, val t4: Long) {
        val offset get() = ((t2 - t1) + (t3 - t4)) / 2.0
        val rtt get() = ((t4 - t1) - (t3 - t2)).toDouble()
    }

    /** Server clock is wall time (UTC); client clock is elapsedRealtimeNanos. */
    fun sync(samples: Int = 60, keepFrac: Double = 0.2): Boolean {
        val all = ArrayList<S>()
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
                all += S(t1, j.getLong("t2"), j.getLong("t3"), t4)
            } catch (_: Exception) { }
            Thread.sleep(50)
        }
        if (all.size < 5) return false
        val best = all.sortedBy { it.rtt }.take(maxOf(3, (all.size * keepFrac).toInt()))
        val ref = best.map { it.t1 }.average()
        val x = best.map { it.t1 - ref }; val y = best.map { it.offset }
        val mx = x.average(); val my = y.average()
        val sxx = x.sumOf { (it - mx) * (it - mx) }
        val slope = if (sxx > 0) x.indices.sumOf { (x[it] - mx) * (y[it] - my) } / sxx else 0.0
        offsetNs = my - slope * mx; driftPpm = slope * 1e6; refNs = ref.toLong()
        sigmaNs = Math.sqrt(x.indices.sumOf { val r = y[it] - (offsetNs + slope * x[it]); r * r } / maxOf(best.size - 2, 1))
        synced = true
        return true
    }

    fun toUtcNs(elapsedNs: Long): Long =
        (elapsedNs + offsetNs + driftPpm * 1e-6 * (elapsedNs - refNs)).toLong()
}
