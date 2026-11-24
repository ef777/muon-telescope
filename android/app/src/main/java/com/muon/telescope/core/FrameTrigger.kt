package com.muon.telescope.core

import kotlin.math.max
import kotlin.math.sqrt

/** Pure Kotlin (no Android deps) so it can be unit-tested on the JVM. Frames are 16-bit samples in a ShortArray/IntArray. */

data class Cluster(
    val xPx: Double, val yPx: Double, val nPix: Int, val sumAdu: Double, val maxAdu: Double,
    val lengthPx: Double, val widthPx: Double, val angleRad: Double, val eccentricity: Double,
    val pixels: List<Int>, // flat indices
)

/** Per-pixel running mean/std (Welford) over the dark-calibration frames; persistently hot pixels are masked. */
class DarkCalibration(val width: Int, val height: Int) {
    private val n = width * height
    private val mean = DoubleArray(n)
    private val m2 = DoubleArray(n)
    var frames = 0; private set
    lateinit var sigma: DoubleArray; private set
    lateinit var mu: DoubleArray; private set
    lateinit var mask: BooleanArray; private set   // true = masked (hot / unusable)

    fun add(frame: IntArray) {
        frames++
        for (i in 0 until n) {
            val d = frame[i] - mean[i]
            mean[i] += d / frames
            m2[i] += d * (frame[i] - mean[i])
        }
    }

    /** hotSigma: a pixel whose mean sits this many global sigmas above the median mean is hot. */
    fun finish(hotSigma: Double = 8.0, minSigma: Double = 0.5) {
        require(frames >= 2)
        mu = mean.copyOf()
        sigma = DoubleArray(n) { max(sqrt(m2[it] / (frames - 1)), minSigma) }
        val sortedMu = mu.sorted()
        val med = sortedMu[n / 2]
        val globalSigma = sigma.sorted()[n / 2]
        mask = BooleanArray(n) { mu[it] > med + hotSigma * globalSigma || sigma[it] > 5 * globalSigma }
    }
}

class FrameTrigger(
    private val cal: DarkCalibration,
    private val k: Double = 6.0,
    private val maxClusters: Int = 10,
) {
    sealed class Result {
        data class Clusters(val clusters: List<Cluster>) : Result()
        /** Too many clusters: light leak / noise. Frame is flagged and nothing is stored. */
        data class Overflow(val count: Int) : Result()
    }

    fun process(frame: IntArray): Result {
        val w = cal.width; val h = cal.height
        val hit = BooleanArray(w * h)
        for (i in hit.indices) hit[i] = !cal.mask[i] && frame[i] > cal.mu[i] + k * cal.sigma[i]
        val seen = BooleanArray(w * h)
        val out = ArrayList<Cluster>()
        var found = 0
        val stack = ArrayDeque<Int>()
        for (start in hit.indices) {
            if (!hit[start] || seen[start]) continue
            val pix = ArrayList<Int>()
            stack.add(start); seen[start] = true
            while (stack.isNotEmpty()) {          // 8-connectivity flood fill
                val p = stack.removeLast(); pix.add(p)
                val px = p % w; val py = p / w
                for (dy in -1..1) for (dx in -1..1) {
                    if (dx == 0 && dy == 0) continue
                    val nx = px + dx; val ny = py + dy
                    if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue
                    val q = ny * w + nx
                    if (hit[q] && !seen[q]) { seen[q] = true; stack.add(q) }
                }
            }
            found++
            if (found > maxClusters) return Result.Overflow(found)
            out.add(describe(pix, frame, cal, w))
        }
        return Result.Clusters(out)
    }

    companion object {
        /** Second-moment shape: length = 2*sqrt(2*lambda1)+1 (pixel extent), width likewise from lambda2. */
        fun describe(pix: List<Int>, frame: IntArray, cal: DarkCalibration, w: Int): Cluster {
            var sw = 0.0; var sx = 0.0; var sy = 0.0; var mx = 0.0
            for (p in pix) {
                val v = max(frame[p] - cal.mu[p], 1e-3)
                sw += v; sx += v * (p % w); sy += v * (p / w); mx = max(mx, frame[p].toDouble())
            }
            val cx = sx / sw; val cy = sy / sw
            var sxx = 0.0; var syy = 0.0; var sxy = 0.0
            for (p in pix) {
                val v = max(frame[p] - cal.mu[p], 1e-3)
                val dx = p % w - cx; val dy = p / w - cy
                sxx += v * dx * dx; syy += v * dy * dy; sxy += v * dx * dy
            }
            sxx = sxx / sw + 1.0 / 12; syy = syy / sw + 1.0 / 12; sxy /= sw      // pixel-size variance
            val tr = sxx + syy; val det = sxx * syy - sxy * sxy
            val disc = sqrt(max(tr * tr / 4 - det, 0.0))
            val l1 = tr / 2 + disc; val l2 = max(tr / 2 - disc, 1e-9)
            val angle = 0.5 * Math.atan2(2 * sxy, sxx - syy)
            val ang = if (angle < 0) angle + Math.PI else angle
            val length = 2 * sqrt(3 * l1); val width = 2 * sqrt(3 * l2)   // uniform-rod equivalent extents
            return Cluster(cx, cy, pix.size, pix.sumOf { frame[it].toDouble() }, mx, length, width, ang,
                sqrt(max(1 - l2 / l1, 0.0)), pix)
        }
    }
}
