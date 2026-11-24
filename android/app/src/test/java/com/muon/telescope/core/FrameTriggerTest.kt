package com.muon.telescope.core

import java.util.Random
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class FrameTriggerTest {
    private val w = 128; private val h = 96
    private val rng = Random(42)

    private fun noise(sigma: Double = 3.0, base: Double = 64.0) =
        IntArray(w * h) { (base + rng.nextGaussian() * sigma).toInt() }

    private fun calibrated(hot: List<Int> = emptyList()): DarkCalibration {
        val cal = DarkCalibration(w, h)
        repeat(60) { val f = noise(); hot.forEach { f[it] += 400 }; cal.add(f) }
        cal.finish()
        return cal
    }

    @Test fun calibrationMasksHotPixels() {
        val cal = calibrated(listOf(10 * w + 10, 50 * w + 70))
        assertTrue(cal.mask[10 * w + 10] && cal.mask[50 * w + 70])
        assertTrue(cal.mask.count { it } < 10)
    }

    @Test fun findsInjectedTrackAndIgnoresHot() {
        val hot = listOf(10 * w + 10)
        val cal = calibrated(hot)
        val trigger = FrameTrigger(cal, k = 6.0)
        var found = 0
        val trials = 200
        repeat(trials) {
            val f = noise(); hot.forEach { f[it] += 400 }
            val x0 = 30 + rng.nextInt(60); val y0 = 20 + rng.nextInt(50)
            for (i in 0 until 8) f[(y0 + i / 2) * w + x0 + i] += 120     // diagonal-ish 8 px track
            val r = trigger.process(f) as FrameTrigger.Result.Clusters
            if (r.clusters.size == 1 && r.clusters[0].nPix >= 7 && r.clusters[0].lengthPx > 5) found++
        }
        assertTrue(found > 0.95 * trials, "efficiency $found/$trials")
    }

    @Test fun pureNoiseFalseAlarmsAreRare() {
        val cal = calibrated()
        val trigger = FrameTrigger(cal, k = 6.0)
        var alarms = 0
        val frames = 2000
        repeat(frames) { if ((trigger.process(noise()) as FrameTrigger.Result.Clusters).clusters.isNotEmpty()) alarms++ }
        // Gaussian tail at 6 sigma ~1e-9/pixel * 12288 px = ~1e-5/frame; at 5 fps that is < 1/hour
        assertTrue(alarms <= 1, "alarms $alarms/$frames")
    }

    @Test fun overflowFlagsLightLeak() {
        val cal = calibrated()
        val f = noise()
        for (i in 0 until 15) f[(5 + 5 * (i / 5)) * w + 10 + 20 * (i % 5)] += 300  // 15 isolated dots
        assertTrue(FrameTrigger(cal, maxClusters = 10).process(f) is FrameTrigger.Result.Overflow)
    }

    @Test fun clusterGeometry() {
        val cal = calibrated()
        val f = noise()
        for (i in 0 until 10) f[40 * w + 20 + i] += 150          // horizontal 10-px line
        val c = (FrameTrigger(cal).process(f) as FrameTrigger.Result.Clusters).clusters.single()
        assertEquals(10, c.nPix)
        assertTrue(abs(c.lengthPx - 10) < 1.5, "length ${c.lengthPx}")
        assertTrue(c.angleRad < 0.1 || c.angleRad > Math.PI - 0.1)
        assertTrue(c.eccentricity > 0.95)
    }
}
