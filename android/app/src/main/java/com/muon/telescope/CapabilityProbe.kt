package com.muon.telescope

import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCharacteristics as CC
import android.hardware.camera2.CameraManager
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject

/** Phase 0: dump every camera's capabilities relevant to the muon telescope as JSON. */
object CapabilityProbe {

    fun run(ctx: Context): JSONObject {
        val mgr = ctx.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val root = JSONObject()
        root.put("device", JSONObject().apply {
            put("manufacturer", Build.MANUFACTURER); put("model", Build.MODEL)
            put("device", Build.DEVICE); put("android_sdk", Build.VERSION.SDK_INT)
            put("release", Build.VERSION.RELEASE)
        })
        val cams = JSONArray()
        val seen = HashSet<String>()
        for (id in mgr.cameraIdList) {
            seen += id
            cams.put(probeOne(mgr, id, null))
        }
        // Physical sub-cameras of logical multi-camera devices (may be absent from cameraIdList).
        if (Build.VERSION.SDK_INT >= 28) {
            for (id in mgr.cameraIdList.toList()) {
                val phys = runCatching { mgr.getCameraCharacteristics(id).physicalCameraIds }.getOrNull() ?: continue
                for (p in phys) if (seen.add(p)) cams.put(probeOne(mgr, p, id))
            }
        }
        root.put("cameras", cams)
        return root
    }

    private fun probeOne(mgr: CameraManager, id: String, logicalParent: String?): JSONObject {
        val o = JSONObject()
        o.put("id", id)
        logicalParent?.let { o.put("physical_of_logical", it) }
        val c = try { mgr.getCameraCharacteristics(id) } catch (e: Exception) {
            return o.put("error", e.toString())
        }
        if (Build.VERSION.SDK_INT >= 28) o.put("physical_ids", JSONArray(c.physicalCameraIds.toList()))
        o.put("lens_facing", when (c.get(CC.LENS_FACING)) { 0 -> "FRONT"; 1 -> "BACK"; 2 -> "EXTERNAL"; else -> "?" })
        o.put("hardware_level", when (c.get(CC.INFO_SUPPORTED_HARDWARE_LEVEL)) {
            0 -> "LIMITED"; 1 -> "FULL"; 2 -> "LEGACY"; 3 -> "LEVEL_3"; 4 -> "EXTERNAL"; else -> "?" })
        val size = c.get(CC.SENSOR_INFO_PHYSICAL_SIZE)
        val pix = c.get(CC.SENSOR_INFO_PIXEL_ARRAY_SIZE)
        size?.let { o.put("physical_size_mm", JSONArray(listOf(it.width.toDouble(), it.height.toDouble()))) }
        pix?.let { o.put("pixel_array", JSONArray(listOf(it.width, it.height))) }
        c.get(CC.SENSOR_INFO_ACTIVE_ARRAY_SIZE)?.let {
            o.put("active_array", JSONArray(listOf(it.left, it.top, it.right, it.bottom))) }
        if (size != null && pix != null)
            o.put("pixel_pitch_um", JSONArray(listOf(size.width / pix.width * 1000.0, size.height / pix.height * 1000.0)))
        o.put("timestamp_source", when (c.get(CC.SENSOR_INFO_TIMESTAMP_SOURCE)) {
            0 -> "UNKNOWN"; 1 -> "REALTIME"; else -> "?" })
        c.get(CC.SENSOR_INFO_SENSITIVITY_RANGE)?.let { o.put("iso_range", JSONArray(listOf(it.lower, it.upper))) }
        c.get(CC.SENSOR_MAX_ANALOG_SENSITIVITY)?.let { o.put("max_analog_iso", it) }
        c.get(CC.SENSOR_INFO_EXPOSURE_TIME_RANGE)?.let { o.put("exposure_range_ns", JSONArray(listOf(it.lower, it.upper))) }
        c.get(CC.SENSOR_INFO_MAX_FRAME_DURATION)?.let { o.put("max_frame_duration_ns", it) }
        c.get(CC.SENSOR_INFO_WHITE_LEVEL)?.let { o.put("white_level", it) }
        c.get(CC.SENSOR_BLACK_LEVEL_PATTERN)?.let { b ->
            o.put("black_level_pattern", JSONArray((0..3).map { i -> b.getOffsetForIndex(i % 2, i / 2) })) }
        c.get(CC.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT)?.let { o.put("cfa", it) }
        o.put("hot_pixel_modes", ints(c.get(CC.HOT_PIXEL_AVAILABLE_HOT_PIXEL_MODES)))
        o.put("hot_pixel_modes_legend", "0=OFF 1=FAST 2=HIGH_QUALITY")
        o.put("noise_reduction_modes", ints(c.get(CC.NOISE_REDUCTION_AVAILABLE_NOISE_REDUCTION_MODES)))
        o.put("noise_reduction_legend", "0=OFF 1=FAST 2=HIGH_QUALITY 3=MINIMAL 4=ZERO_SHUTTER_LAG")
        o.put("edge_modes", ints(c.get(CC.EDGE_AVAILABLE_EDGE_MODES)))
        o.put("shading_modes", ints(c.get(CC.SHADING_AVAILABLE_MODES)))
        o.put("hot_pixel_map_modes", JSONArray((c.get(CC.STATISTICS_INFO_AVAILABLE_HOT_PIXEL_MAP_MODES) ?: BooleanArray(0)).toList()))
        o.put("ae_modes", ints(c.get(CC.CONTROL_AE_AVAILABLE_MODES)))
        o.put("af_modes", ints(c.get(CC.CONTROL_AF_AVAILABLE_MODES)))
        val caps = c.get(CC.REQUEST_AVAILABLE_CAPABILITIES) ?: IntArray(0)
        o.put("capabilities", JSONArray(caps.toList()))
        o.put("capabilities_legend",
            "1=MANUAL_SENSOR 2=MANUAL_POST_PROCESSING 3=RAW 4=PRIVATE_REPROC 5=READ_SENSOR_SETTINGS 6=BURST 7=YUV_REPROC 8=DEPTH 9=HIGH_SPEED 11=LOGICAL_MULTI_CAMERA 14=ULTRA_HIGH_RES_SENSOR")
        o.put("raw_supported", 3 in caps)
        o.put("manual_sensor", 1 in caps)

        val map = c.get(CC.SCALER_STREAM_CONFIGURATION_MAP)
        val fmts = JSONObject()
        if (map != null) {
            for ((name, f) in listOf("RAW_SENSOR" to ImageFormat.RAW_SENSOR, "YUV_420_888" to ImageFormat.YUV_420_888,
                                     "RAW10" to ImageFormat.RAW10)) {
                val sizes = map.getOutputSizes(f) ?: continue
                val arr = JSONArray()
                for (s in sizes.sortedByDescending { it.width.toLong() * it.height }) {
                    arr.put(JSONObject().apply {
                        put("size", "${s.width}x${s.height}")
                        put("min_frame_duration_ns", map.getOutputMinFrameDuration(f, s))
                        put("stall_duration_ns", map.getOutputStallDuration(f, s))
                    })
                }
                fmts.put(name, arr)
            }
        }
        o.put("output_formats", fmts)
        return o
    }

    private fun ints(a: IntArray?): JSONArray = JSONArray((a ?: IntArray(0)).toList())
}
