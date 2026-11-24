package com.muon.telescope

import android.app.*
import android.content.*
import android.graphics.ImageFormat
import android.hardware.camera2.*
import android.os.SystemClock
import android.media.ImageReader
import android.os.*
import com.muon.telescope.core.DarkCalibration
import com.muon.telescope.core.FrameTrigger
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Foreground capture: manual-sensor Camera2 stream (all post-processing OFF), 60 s dark calibration,
 * cluster trigger, JSONL + 64x64 .npy crops, offline-first upload. Pauses above 42 C battery temperature.
 *
 * Camera, size and ISO come from intent extras (decided from the Phase 0 report / config/devices.yaml).
 * YUV Y-plane is 8-bit; RAW16 is preferred once Phase 0 reports confirm support (NOT yet implemented here).
 * NOT yet validated on hardware: Phase 1 acceptance (8 h run) is pending.
 */
class CaptureService : Service() {
    private lateinit var thread: HandlerThread
    private lateinit var handler: Handler
    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var reader: ImageReader? = null
    private var cal: DarkCalibration? = null
    private var trigger: FrameTrigger? = null
    private var frameIdx = 0L
    private var calFrames = 0
    private val calTarget get() = calSeconds * fps
    private var calSeconds = 60; private var fps = 5
    private var width = 0; private var height = 0
    private lateinit var deviceId: String; private lateinit var runId: String
    private lateinit var timeSync: TimeSync
    private lateinit var uploader: Uploader
    private lateinit var outDir: File
    private var exposureNs = 150_000_000L; private var frameNs = 200_000_000L; private var iso = 0
    @Volatile private var paused = false
    private var overflowFrames = 0L
    private var sim = false; private var simEventProb = 0.05
    private val pending = HashMap<Long, Long>()   // sensor ts -> exposure from CaptureResult

    override fun onBind(i: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "stop") { stopSelf(); return START_NOT_STICKY }
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("cap", "Capture", NotificationManager.IMPORTANCE_LOW))
        startForeground(1, Notification.Builder(this, "cap").setContentTitle("Muon capture").setSmallIcon(android.R.drawable.ic_menu_camera).build())
        (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "muon:cap").acquire()
        val e = intent!!
        deviceId = e.getStringExtra("device_id") ?: "dev"; runId = e.getStringExtra("run_id") ?: "run"
        val server = e.getStringExtra("server") ?: "http://192.168.1.2:8000"
        val camId = e.getStringExtra("camera_id") ?: "0"
        width = e.getIntExtra("width", 1280); height = e.getIntExtra("height", 960)
        fps = e.getIntExtra("fps", 5); iso = e.getIntExtra("iso", 0)
        sim = e.getBooleanExtra("sim", false); calSeconds = e.getIntExtra("cal_seconds", 60)
        simEventProb = e.getDoubleExtra("sim_event_prob", 0.05)
        frameNs = 1_000_000_000L / fps; exposureNs = (frameNs * 0.75).toLong()
        outDir = File(getExternalFilesDir(null), "runs/$runId").also { File(it, "crops").mkdirs() }
        timeSync = TimeSync(server); uploader = Uploader(outDir, server)
        thread = HandlerThread("cap").also { it.start() }; handler = Handler(thread.looper)
        handler.post {
            timeSync.sync()
            if (sim) startSimulation() else open(camId)
        }
        handler.postDelayed(object : Runnable { override fun run() { housekeeping(); handler.postDelayed(this, 10_000) } }, 10_000)
        return START_STICKY
    }

    private fun open(camId: String) {
        val mgr = getSystemService(CAMERA_SERVICE) as CameraManager
        val ch = mgr.getCameraCharacteristics(camId)
        if (iso == 0) iso = ch.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY)
            ?: ch.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)!!.upper
        cal = DarkCalibration(width, height)
        reader = ImageReader.newInstance(width, height, ImageFormat.YUV_420_888, 4).apply {
            setOnImageAvailableListener({ r -> r.acquireLatestImage()?.use { onImage(it) } }, handler)
        }
        mgr.openCamera(camId, object : CameraDevice.StateCallback() {
            override fun onOpened(c: CameraDevice) {
                camera = c
                c.createCaptureSession(listOf(reader!!.surface), object : CameraCaptureSession.StateCallback() {
                    override fun onConfigured(s: CameraCaptureSession) { session = s; repeat(s, c, ch) }
                    override fun onConfigureFailed(s: CameraCaptureSession) { stopSelf() }
                }, handler)
            }
            override fun onDisconnected(c: CameraDevice) { c.close() }
            override fun onError(c: CameraDevice, error: Int) { c.close(); stopSelf() }
        }, handler)
    }

    private fun repeat(s: CameraCaptureSession, c: CameraDevice, ch: CameraCharacteristics) {
        fun <T> has(key: CameraCharacteristics.Key<IntArray>, v: Int) = ch.get(key)?.contains(v) == true
        val b = c.createCaptureRequest(CameraDevice.TEMPLATE_MANUAL)
        b.addTarget(reader!!.surface)
        b.set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_OFF)
        b.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF)
        b.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF)
        b.set(CaptureRequest.SENSOR_SENSITIVITY, iso)
        b.set(CaptureRequest.SENSOR_EXPOSURE_TIME, exposureNs)
        b.set(CaptureRequest.SENSOR_FRAME_DURATION, frameNs)
        if (has<Int>(CameraCharacteristics.NOISE_REDUCTION_AVAILABLE_NOISE_REDUCTION_MODES, 0))
            b.set(CaptureRequest.NOISE_REDUCTION_MODE, CaptureRequest.NOISE_REDUCTION_MODE_OFF)
        if (has<Int>(CameraCharacteristics.EDGE_AVAILABLE_EDGE_MODES, 0)) b.set(CaptureRequest.EDGE_MODE, CaptureRequest.EDGE_MODE_OFF)
        if (has<Int>(CameraCharacteristics.HOT_PIXEL_AVAILABLE_HOT_PIXEL_MODES, 0))
            b.set(CaptureRequest.HOT_PIXEL_MODE, CaptureRequest.HOT_PIXEL_MODE_OFF)
        if (has<Int>(CameraCharacteristics.SHADING_AVAILABLE_MODES, 0)) b.set(CaptureRequest.SHADING_MODE, CaptureRequest.SHADING_MODE_OFF)
        s.setRepeatingRequest(b.build(), object : CameraCaptureSession.CaptureCallback() {
            override fun onCaptureCompleted(se: CameraCaptureSession, rq: CaptureRequest, r: TotalCaptureResult) {
                val ts = r.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
                synchronized(pending) { pending[ts] = r.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: exposureNs
                    if (pending.size > 64) pending.keys.minOrNull()?.let { pending.remove(it) } }
            }
        }, handler)
    }

    private fun onImage(img: android.media.Image) {
        if (paused) return
        val plane = img.planes[0]; val buf = plane.buffer; val rs = plane.rowStride
        val frame = IntArray(width * height)
        for (y in 0 until height) for (x in 0 until width) frame[y * width + x] = buf.get(y * rs + x).toInt() and 0xFF
        processFrame(frame, img.timestamp)
    }

    /** Simulation mode: synthetic dark frames (Gaussian noise + hot pixels) with injected tracks/dots, no camera. */
    private fun startSimulation() {
        cal = DarkCalibration(width, height)
        val rng = java.util.Random(deviceId.hashCode().toLong())
        val hot = IntArray(5) { rng.nextInt(width * height) }
        val tick = object : Runnable {
            override fun run() {
                val f = IntArray(width * height) { (64 + rng.nextGaussian() * 3).toInt() }
                hot.forEach { f[it] += 300 }
                if (trigger != null && rng.nextDouble() < simEventProb) {      // injected after calibration
                    val x0 = 10 + rng.nextInt(width - 30); val y0 = 10 + rng.nextInt(height - 30)
                    val len = 1 + rng.nextInt(12); val dy = rng.nextInt(3) - 1
                    for (i in 0 until len) f[(y0 + dy * i / 4) * width + x0 + i] += 150
                }
                processFrame(f, SystemClock.elapsedRealtimeNanos())
                handler.postDelayed(this, frameNs / 1_000_000)
            }
        }
        handler.post(tick)
    }

    private fun processFrame(frame: IntArray, ts: Long) {
        val c = cal!!
        if (trigger == null) {
            c.add(frame); calFrames++
            if (calFrames >= calTarget) { c.finish(); trigger = FrameTrigger(c) }
            return
        }
        val idx = frameIdx++
        when (val r = trigger!!.process(frame)) {
            is FrameTrigger.Result.Overflow -> overflowFrames++   // light leak / noise: nothing stored
            is FrameTrigger.Result.Clusters -> r.clusters.forEachIndexed { ci, cl ->
                val exp = synchronized(pending) { pending[ts] } ?: exposureNs
                val crop = File(outDir, "crops/${idx}_$ci.npy").also { writeCrop(it, frame, cl) }
                val j = JSONObject().put("device_id", deviceId).put("run_id", runId).put("frame_idx", idx).put("cluster_idx", ci)
                    .put("sensor_ts_ns", ts).put("exposure_ns", exp).put("frame_duration_ns", frameNs)
                    // sensor timestamp = end-of-readout start convention varies; exposure START assumed = ts (validate by tap test)
                    .put("utc_ns", timeSync.toUtcNs(ts)).put("utc_uncertainty_ns", timeSync.sigmaNs.takeIf { !it.isNaN() } ?: 1e9)
                    .put("iso", iso).put("battery_temp_c", batteryTemp())
                    .put("cluster", JSONObject().put("x_px", cl.xPx).put("y_px", cl.yPx).put("n_pix", cl.nPix)
                        .put("sum_adu", cl.sumAdu).put("max_adu", cl.maxAdu).put("length_px", cl.lengthPx)
                        .put("width_px", cl.widthPx).put("angle_rad", cl.angleRad).put("eccentricity", cl.eccentricity))
                    .put("crop_file", "crops/${crop.name}")
                uploader.enqueue(j.toString())
            }
        }
    }

    private fun writeCrop(f: File, frame: IntArray, cl: com.muon.telescope.core.Cluster) {
        val n = 64; val x0 = (cl.xPx.toInt() - n / 2).coerceIn(0, width - n); val y0 = (cl.yPx.toInt() - n / 2).coerceIn(0, height - n)
        val hdr = "{'descr': '<i2', 'fortran_order': False, 'shape': ($n, $n), }".let { it + " ".repeat((63 - (10 + it.length) % 64 + 64) % 64) + "\n" }
        val bb = ByteBuffer.allocate(10 + hdr.length + n * n * 2).order(ByteOrder.LITTLE_ENDIAN)
        bb.put(0x93.toByte()).put("NUMPY".toByteArray()).put(1).put(0).putShort(hdr.length.toShort()).put(hdr.toByteArray())
        for (y in 0 until n) for (x in 0 until n) bb.putShort(frame[(y0 + y) * width + x0 + x].toShort())
        f.writeBytes(bb.array())
    }

    private fun batteryTemp(): Double =
        (registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0) / 10.0

    private fun housekeeping() {
        android.util.Log.i("MuonCap", "frames=${frameIdx} cal=$calFrames/$calTarget trigger=${trigger != null} overflow=$overflowFrames sync=${timeSync.synced} offset_ms=${timeSync.offsetNs / 1e6} temp=${batteryTemp()}")
        val t = batteryTemp()
        paused = if (paused) t > 40.0 else t > 42.0          // hysteresis: pause >42 C, resume <=40 C
        Thread { uploader.flush() }.start()
    }

    override fun onDestroy() {
        session?.close(); camera?.close(); reader?.close(); thread.quitSafely(); super.onDestroy()
    }
}
