package com.muon.telescope.core

import java.util.Random
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class SyncMathTest {
    @Test fun recoversOffsetAndDriftUnderAsymmetricDelays() {
        val rng = Random(1)
        val trueOff = 12e6; val drift = 20e-6
        val samples = (0 until 400).map { k ->
            val t1 = k * 1_000_000_000L
            val o = trueOff + drift * t1
            val up = -2e6 * Math.log(1 - rng.nextDouble()) + 1e6; val dn = -2e6 * Math.log(1 - rng.nextDouble()) + 1e6
            val t2 = (t1 + up + o).toLong(); val t3 = t2 + 100_000; val t4 = (t3 - o + dn).toLong()
            NtpSample(t1, t2, t3, t4)
        }
        val f = assertNotNull(OffsetEstimator.fit(samples))
        val t = 200e9
        val est = f.offsetNs + f.driftPpm * 1e-6 * (t - f.refNs)
        assertTrue(abs(est - (trueOff + drift * t)) < 2e6, "err ${est - (trueOff + drift * t)}")
        assertTrue(abs(f.driftPpm - 20) < 5, "drift ${f.driftPpm}")
    }

    @Test fun tooFewSamplesGiveNull() { assertTrue(OffsetEstimator.fit(emptyList()) == null) }

    @Test fun impulseDetectorFindsTapsAndHonoursRefractory() {
        val d = ImpulseDetector()
        var hits = 0
        var t = 0L
        val rng = Random(2)
        repeat(3000) {                                 // 3 s of 1 kHz noise around gravity
            t += 1_000_000
            val tap = it == 500 || it == 520 || it == 2000      // 500/520 are one tap (ringing), 2000 is another
            val z = 9.81 + rng.nextGaussian() * 0.05 + if (tap) 30.0 else 0.0
            if (d.onSample(t, 0.0, 0.0, z)) hits++
        }
        assertEquals(2, hits)
    }
}
