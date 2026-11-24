package com.muon.telescope.core

import kotlin.math.abs
import kotlin.math.sqrt

/** NTP-style sample: client t1/t4 (client clock), server t2/t3 (server clock). */
data class NtpSample(val t1: Long, val t2: Long, val t3: Long, val t4: Long) {
    val offset get() = ((t2 - t1) + (t3 - t4)) / 2.0
    val rtt get() = ((t4 - t1) - (t3 - t2)).toDouble()
}

data class OffsetFit(val offsetNs: Double, val driftPpm: Double, val refNs: Long, val sigmaNs: Double)

object OffsetEstimator {
    /** Keep the lowest-RTT fraction, least-squares fit offset(t) = o0 + drift*(t - tRef). Mirrors server/muon/timesync.py. */
    fun fit(all: List<NtpSample>, keepFrac: Double = 0.2): OffsetFit? {
        if (all.size < 5) return null
        val best = all.sortedBy { it.rtt }.take(maxOf(3, (all.size * keepFrac).toInt()))
        val ref = best.map { it.t1 }.average()
        val x = best.map { it.t1 - ref }; val y = best.map { it.offset }
        val mx = x.average(); val my = y.average()
        val sxx = x.sumOf { (it - mx) * (it - mx) }
        val slope = if (sxx > 0) x.indices.sumOf { (x[it] - mx) * (y[it] - my) } / sxx else 0.0
        val o0 = my - slope * mx
        val sigma = sqrt(x.indices.sumOf { val r = y[it] - (o0 + slope * x[it]); r * r } / maxOf(best.size - 2, 1))
        return OffsetFit(o0, slope * 1e6, ref.toLong(), sigma)
    }
}

/** Detects sharp accelerometer impulses (taps on the phone stack) with a refractory period. */
class ImpulseDetector(private val thresholdMs2: Double = 12.0, private val refractoryNs: Long = 1_000_000_000L,
                      private val gravity: Double = 9.81) {
    private var last = Long.MIN_VALUE
    /** Returns true if this sample (timestamp ns, acceleration xyz in m/s2) is a new impulse. */
    fun onSample(tsNs: Long, x: Double, y: Double, z: Double): Boolean {
        val dev = abs(sqrt(x * x + y * y + z * z) - gravity)
        if (dev > thresholdMs2 && (last == Long.MIN_VALUE || tsNs - last > refractoryNs)) { last = tsNs; return true }
        return false
    }
}
