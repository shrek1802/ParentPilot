package uk.familycontrol.remote

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.Dialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.net.Inet4Address
import java.net.URI
import java.util.concurrent.Executors

/**
 * ParentPilot fully native Android controls.
 * No WebView, browser intent or native PIN storage.
 * Supports existing parent HTML form API on installed Linux laptops.
 */
class MainActivity : Activity() {
    private val navy = Color.rgb(15, 23, 42)
    private val slate = Color.rgb(30, 41, 59)
    private val white = Color.rgb(248, 250, 252)
    private val muted = Color.rgb(184, 202, 222)
    private val teal = Color.rgb(37, 180, 178)
    private lateinit var container: LinearLayout
    private lateinit var scroll: ScrollView
    private val uiHandler = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val preferences by lazy { getSharedPreferences("parentpilot_parent", MODE_PRIVATE) }
    private lateinit var manager: NsdManager
    private var multicast: WifiManager.MulticastLock? = null
    private var discovery: NsdManager.DiscoveryListener? = null
    private var scanNumber = 0
    private var connectionStatus: TextView? = null
    private var deviceList: LinearLayout? = null
    private var addressInput: EditText? = null
    private var parentPinInput: EditText? = null
    private var client: ParentPilotClient? = null
    private var state: ParentState? = null
    private var timerLabel: TextView? = null
    private var modeLabel: TextView? = null
    private var presenceLabel: TextView? = null
    private var screenStatus: TextView? = null
    private var preview: ImageView? = null
    private var saveButton: Button? = null
    private var gallery: LinearLayout? = null
    private var latestBytes: ByteArray? = null
    private var lastGalleryKey = ""
    private var previousScreenStatus = ""
    private var pollActive = false
    private var busy = false
    private var pendingSaveBytes: ByteArray? = null

    private fun Int.dp(): Int = (this * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        manager = getSystemService(NSD_SERVICE) as NsdManager
        scroll = ScrollView(this)
        container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18.dp(), 16.dp(), 18.dp(), 30.dp())
            setBackgroundColor(navy)
        }
        scroll.addView(container)
        setContentView(scroll)
        showConnection()
    }

    private fun text(value: String, size: Float = 16f, color: Int = white): TextView =
        TextView(this).apply {
            text = value
            textSize = size
            setTextColor(color)
            setPadding(0, 5.dp(), 0, 8.dp())
        }

    private fun title(value: String) = text(value, 21f).apply {
        setTypeface(null, android.graphics.Typeface.BOLD)
    }

    private fun panel(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(15.dp(), 13.dp(), 15.dp(), 16.dp())
        background = GradientDrawable().apply { setColor(slate); cornerRadius = 16.dp().toFloat() }
        container.addView(this, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = 14.dp() })
    }

    private fun button(parent: LinearLayout, label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            isAllCaps = false
            minHeight = 50.dp()
            setTextColor(Color.WHITE)
            backgroundTintList = android.content.res.ColorStateList.valueOf(teal)
            setOnClickListener { action() }
            parent.addView(this, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = 7.dp() })
        }

    private fun field(parent: LinearLayout, hint: String, value: String = "", numbers: Boolean = false): EditText =
        EditText(this).apply {
            this.hint = hint
            setSingleLine(true)
            setText(value)
            setTextColor(white)
            setHintTextColor(muted)
            inputType = if (numbers) InputType.TYPE_CLASS_NUMBER else
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            parent.addView(this, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ))
        }

    private fun resetPage(subtitle: String) {
        container.removeAllViews()
        scroll.scrollTo(0, 0)
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        row.addView(ImageView(this).apply {
            setImageResource(R.drawable.parentpilot_icon)
            contentDescription = "ParentPilot logo"
        }, LinearLayout.LayoutParams(56.dp(), 56.dp()))
        row.addView(title("  ParentPilot"), LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        container.addView(row)
        container.addView(text(subtitle, 14f, muted))
    }

    private fun showConnection() {
        pollActive = false
        stopDiscovery()
        resetPage("Private family screen-time controls")
        val connection = panel()
        connection.addView(title("Connect to your child's laptop"))
        connection.addView(text("Use the same Wi-Fi, or a private Tailscale connection. All controls stay inside this app.", 14f, muted))
        val saved = preferences.getString("active_address", "")
            .orEmpty().ifBlank { preferences.getString("local_ip", "").orEmpty() }
        addressInput = field(connection, "192.168.1.100 or https://laptop.tailnet.ts.net", saved)
        connection.addView(text("Parent PIN (never saved)", 14f, muted))
        parentPinInput = field(connection, "Six-digit PIN", "", numbers = true).also {
            it.inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
        }
        connectionStatus = text("Enter the laptop address and parent PIN.", 14f, muted).also {
            connection.addView(it)
        }
        button(connection, "Connect to ParentPilot") { connectFromFields() }
        val wifi = panel()
        wifi.addView(title("Find laptop on Wi-Fi"))
        button(wifi, "Find nearby laptop") { scanWithPermission() }
        deviceList = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        wifi.addView(deviceList)
        wifi.addView(text("Discovery works when both devices can reach one another on a private network.", 13f, muted))
        val note = panel()
        note.addView(title("Local connection security"))
        note.addView(text(
            "For a local laptop's self-signed HTTPS certificate, check its SHA-256 fingerprint on the laptop the first time you connect. The app remembers the certificate fingerprint, not your PIN. If it changes, the connection is blocked until you verify it again.",
            13f, muted))
    }

    private fun normalizeAddress(raw: String): String? {
        return try {
            val value = raw.trim()
            if (value.isEmpty()) return null
            val url = if (value.startsWith("https://", true)) value else "https://" + value
            val uri = URI(url)
            if (uri.scheme != "https" || uri.userInfo != null || uri.query != null ||
                uri.fragment != null || !uri.path.orEmpty().let { it == "" || it == "/" }) return null
            val host = uri.host?.lowercase() ?: return null
            val ipParts = host.split(".")
            val local = ipParts.size == 4 && ipParts.all { it.toIntOrNull() in 0..255 } &&
                ((ipParts[0] == "10") || (ipParts[0] == "192" && ipParts[1] == "168") ||
                    (ipParts[0] == "172" && (ipParts[1].toIntOrNull() ?: 0) in 16..31))
            val remote = host.endsWith(".ts.net") && host.length > ".ts.net".length + 1 &&
                host.matches(Regex("[a-z0-9.-]+[.]ts[.]net"))
            if (!local && !remote) return null
            val port = if (uri.port < 0) { if (local) 8743 else 443 } else uri.port
            if ((local && port != 8743) || (remote && port != 443)) return null
            "https://" + host + (if (local) ":8743" else "") + "/"
        } catch (_: Exception) { null }
    }

    private fun connectFromFields() {
        val raw = addressInput?.text?.toString().orEmpty()
        val pin = parentPinInput?.text?.toString().orEmpty()
        val origin = normalizeAddress(raw)
        if (origin == null) { connectionStatus?.text = "Enter a private Wi-Fi IP or private .ts.net HTTPS address."; return }
        if (!Regex("[0-9]{6}").matches(pin)) {
            connectionStatus?.text = "Enter your six-digit parent PIN."; return
        }
        val local = origin.contains(":8743/")
        val savedFingerprint = preferences.getString("certificate:" + origin, null)
        if (local && savedFingerprint.isNullOrBlank()) {
            connectionStatus?.text = "Reading laptop certificate fingerprint…"
            background(
                { ParentPilotClient.certificateFingerprint(origin) },
                { result ->
                    result.onSuccess { fingerprint ->
                        showCertificateVerification(origin, fingerprint, pin)
                    }.onFailure { failure -> error("Could not inspect the laptop certificate: " + safeError(failure)) }
                }
            )
        } else login(origin, if (local) savedFingerprint else null, pin)
    }

    private fun showCertificateVerification(origin: String, fingerprint: String, pin: String) {
        val formatted = fingerprint.chunked(2).joinToString(":")
        AlertDialog.Builder(this)
            .setTitle("Verify your laptop certificate")
            .setMessage("On the laptop, sign into the adult administrator account and run:\n\n" +
                "sudo openssl x509 -in /etc/max-family-control/server.crt -noout -fingerprint -sha256\n\n" +
                "Compare the SHA256 fingerprint to:\n\n" + formatted + "\n\n" +
                "Only continue if every character matches. ParentPilot will refuse unexpected certificate changes.")
            .setNegativeButton("Cancel", null)
            .setPositiveButton("I verified it matches") { _, _ ->
                preferences.edit().putString("certificate:" + origin, fingerprint).apply()
                login(origin, fingerprint, pin)
            }.show()
    }

    private fun login(origin: String, fingerprint: String?, pin: String) {
        if (busy) return
        busy = true
        connectionStatus?.text = "Connecting securely…"
        val next = ParentPilotClient(origin, fingerprint)
        background(
            { next.login(pin) },
            { result ->
                busy = false
                result.onSuccess { info ->
                    client = next
                    state = info
                    parentPinInput?.text?.clear()
                    preferences.edit().putString("active_address", origin)
                        .putString(if (origin.contains(":8743/")) "local_ip" else "remote_url", origin)
                        .apply()
                    showDashboard(info)
                }.onFailure { failure -> error("Connection failed: " + safeError(failure)) }
            }
        )
    }

    private fun safeError(t: Throwable): String =
        t.message?.take(220) ?: "Check that the laptop is reachable and ParentPilot is running."

    private fun error(message: String) {
        connectionStatus?.text = message
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    private fun <T> background(task: () -> T, finish: (Result<T>) -> Unit) {
        worker.execute {
            val outcome = runCatching(task)
            runOnUiThread { if (!isFinishing && !isDestroyed) finish(outcome) }
        }
    }

    private fun showDashboard(info: ParentState) {
        stopDiscovery()
        resetPage("Connected securely · " + (client?.origin ?: ""))
        val summary = panel()
        summary.addView(title("Screen time"))
        modeLabel = title(info.mode).also { summary.addView(it) }
        timerLabel = text("Time left: " + info.remaining, 26f).also { summary.addView(it) }
        presenceLabel = text(info.presence + " · Used today: " + info.used, 13f, muted).also { summary.addView(it) }
        button(summary, "Refresh status") { refreshNow() }

        val clock = panel()
        clock.addView(title("Set or add time"))
        val input = field(clock, "Minutes (1–720)", "60", numbers = true)
        button(clock, "Set remaining time") {
            performMinutes("set", input.text.toString())
        }
        button(clock, "Add custom minutes") {
            performMinutes("add", input.text.toString())
        }
        for (minutes in listOf(15, 30, 60, 120)) {
            button(clock, "Add " + minutes + " minutes") { performAction("add", minutes) }
        }

        val access = panel()
        access.addView(title("Laptop access"))
        button(access, "Pause laptop") { performAction("pause") }
        button(access, "Resume laptop") { performAction("resume") }
        button(access, "Unlimited time today") { performAction("unlimited") }
        button(access, "Return to managed time") { performAction("managed") }
        button(access, "End time for today") {
            AlertDialog.Builder(this).setTitle("End screen time?")
                .setMessage("End this child's remaining time for today?")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("End time") { _, _ -> performAction("end") }.show()
        }

        val screenshot = panel()
        screenshot.addView(title("View child's screen"))
        screenshot.addView(text(
            "One parent-requested picture, not a video stream. The laptop shows a viewing notice.",
            13f, muted))
        screenStatus = text("", 14f).also { screenshot.addView(it) }
        button(screenshot, "Take one screen picture") { takePicture() }
        preview = ImageView(this).apply {
            adjustViewBounds = true
            scaleType = ImageView.ScaleType.FIT_CENTER
            visibility = View.GONE
            setOnClickListener {
                latestBytes?.let { bytes -> openPictureViewer(bytes, "Screen picture") }
            }
        }
        screenshot.addView(preview, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = 10.dp() })
        saveButton = button(screenshot, "Save current picture to laptop gallery") {
            performAction("save-screen")
        }

        val saved = panel()
        saved.addView(title("Saved screen pictures"))
        saved.addView(text("Screenshots are kept on the laptop only when you choose Save. Up to 20 pictures.", 13f, muted))
        gallery = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        saved.addView(gallery)
        val account = panel()
        button(account, "Sign out / Change laptop") {
            val old = client
            pollActive = false
            client = null
            state = null
            latestBytes = null
            lastGalleryKey = ""
            showConnection()
            if (old != null) worker.execute { old.logout() }
        }

        applyState(info)
        pollActive = true
        uiHandler.postDelayed({ refreshLoop() }, 1600)
    }

    private fun performMinutes(action: String, value: String) {
        val minutes = value.toIntOrNull()
        if (minutes == null || minutes !in 1..720) {
            Toast.makeText(this, "Enter 1–720 minutes.", Toast.LENGTH_LONG).show()
            return
        }
        performAction(action, minutes)
    }

    private fun performAction(action: String, minutes: Int? = null, pictureId: String? = null) {
        val api = client ?: return
        if (busy) return
        busy = true
        screenStatus?.text = if (action == "request-screen") "Waiting for child laptop…" else "Updating…"
        background(
            { api.action(action, minutes, pictureId) },
            { result ->
                busy = false
                result.onSuccess {
                    if (action == "request-screen") {
                        latestBytes = null
                        preview?.visibility = View.GONE
                        previousScreenStatus = ""
                    }
                    applyState(it)
                }.onFailure { failure ->
                    screenStatus?.text = safeError(failure)
                    Toast.makeText(this, safeError(failure), Toast.LENGTH_LONG).show()
                }
            }
        )
    }

    private fun takePicture() {
        if (state?.screenEnabled != true) {
            Toast.makeText(this, "Screen viewing is switched off on this laptop.", Toast.LENGTH_LONG).show()
            return
        }
        performAction("request-screen")
    }

    private fun applyState(info: ParentState) {
        if (client == null) return
        state = info
        modeLabel?.text = info.child + ": " + info.mode
        timerLabel?.text = "Time left: " + info.remaining
        presenceLabel?.text = info.presence + " · Used today: " + info.used
        screenStatus?.text = if (info.screenEnabled) "Picture status: " + info.screenStatus
            else "Screen pictures are off. Enable them during the laptop's administrator setup."
        saveButton?.isEnabled = info.screenEnabled && info.screenStatus == "ready"
        if (info.screenStatus != "ready") {
            latestBytes = null
            preview?.visibility = View.GONE
        } else if (latestBytes == null && previousScreenStatus != "ready") loadPreview()
        previousScreenStatus = info.screenStatus
        val galleryKey = info.pictures.joinToString("|") { it.id }
        if (galleryKey != lastGalleryKey) {
            lastGalleryKey = galleryKey
            renderGallery(info.pictures)
        }
    }

    private fun loadPreview() {
        val api = client ?: return
        background(
            { api.jpeg() },
            { result ->
                result.onSuccess { bytes ->
                    if (client !== api) return@onSuccess
                    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    if (bitmap != null) {
                        latestBytes = bytes
                        preview?.setImageBitmap(bitmap)
                        preview?.visibility = View.VISIBLE
                    }
                }.onFailure { /* Child has not uploaded a picture yet or it expired. */ }
            }
        )
    }

    private fun renderGallery(pictures: List<SavedPicture>) {
        val parent = gallery ?: return
        parent.removeAllViews()
        if (pictures.isEmpty()) {
            parent.addView(text("No pictures saved yet.", 14f, muted))
            return
        }
        for (pic in pictures) {
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(0, 8.dp(), 0, 12.dp())
            }
            row.addView(text(pic.time, 15f))
            button(row, "View / zoom saved picture") {
                val api = client ?: return@button
                background({ api.jpeg(pic.id) }) { result ->
                    result.onSuccess { openPictureViewer(it, pic.time) }
                        .onFailure { Toast.makeText(this, safeError(it), Toast.LENGTH_LONG).show() }
                }
            }
            button(row, "Download picture to phone") {
                val api = client ?: return@button
                background({ api.jpeg(pic.id) }) { result ->
                    result.onSuccess { saveWithSystemPicker(it, pic.id) }
                        .onFailure { Toast.makeText(this, safeError(it), Toast.LENGTH_LONG).show() }
                }
            }
            button(row, "Delete saved picture") {
                AlertDialog.Builder(this).setTitle("Delete screenshot?")
                    .setMessage("Permanently delete this saved screenshot from the laptop?")
                    .setNegativeButton("Cancel", null)
                    .setPositiveButton("Delete") { _, _ -> performAction("delete-saved-screen", pictureId = pic.id) }
                    .show()
            }
            parent.addView(row)
        }
    }

    private fun refreshNow() {
        val api = client ?: return
        background({ api.state() }) { result ->
            result.onSuccess { if (client === api) applyState(it) }
                .onFailure { Toast.makeText(this, safeError(it), Toast.LENGTH_LONG).show() }
        }
    }

    private fun refreshLoop() {
        if (!pollActive || client == null || isFinishing || isDestroyed) return
        val api = client ?: return
        if (!busy) {
            background({ api.state() }) { result ->
                if (client === api && pollActive) {
                    result.onSuccess { applyState(it) }
                        .onFailure {
                            screenStatus?.text = "Connection interrupted. Tap Refresh when the laptop is online."
                        }
                }
            }
        }
        uiHandler.postDelayed({ refreshLoop() }, 5000)
    }

    private fun openPictureViewer(bytes: ByteArray, title: String) {
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        if (bitmap == null) {
            Toast.makeText(this, "The image couldn't be displayed.", Toast.LENGTH_LONG).show()
            return
        }
        val dialog = Dialog(this)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(6.dp(), 6.dp(), 6.dp(), 8.dp())
            setBackgroundColor(navy)
        }
        layout.addView(text(title, 15f), LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        val zoom = ZoomPictureView(this).apply { setPicture(bitmap) }
        layout.addView(zoom, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        val toolbar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fun tool(label: String, job: () -> Unit) {
            toolbar.addView(Button(this).apply {
                text = label
                isAllCaps = false
                setOnClickListener { job() }
            }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        tool("−") { zoom.zoom(0.75f) }
        tool("+") { zoom.zoom(1.4f) }
        tool("Fit") { zoom.fit() }
        tool("Save") { saveWithSystemPicker(bytes, "parentpilot-screen.jpg") }
        tool("Close") { dialog.dismiss() }
        layout.addView(toolbar)
        dialog.setContentView(layout)
        dialog.window?.setLayout(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT)
        dialog.show()
        dialog.window?.setLayout(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT)
    }

    private fun saveWithSystemPicker(bytes: ByteArray, suggestedName: String) {
        pendingSaveBytes = bytes
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "image/jpeg"
            putExtra(Intent.EXTRA_TITLE, suggestedName)
        }
        startActivityForResult(intent, 882)
    }

    @Deprecated("Uses the platform document picker for Android 8+.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 882) {
            val bytes = pendingSaveBytes
            pendingSaveBytes = null
            if (resultCode == RESULT_OK && bytes != null && data?.data != null) {
                try {
                    contentResolver.openOutputStream(data.data!!)?.use { it.write(bytes) }
                        ?: throw IllegalStateException("Unable to open chosen destination.")
                    Toast.makeText(this, "Picture saved to your phone.", Toast.LENGTH_LONG).show()
                } catch (ex: Exception) {
                    Toast.makeText(this, safeError(ex), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun scanWithPermission() {
        connectionStatus?.text = "Looking for ParentPilot laptops…"
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.NEARBY_WIFI_DEVICES), 91)
        } else startDiscovery()
    }

    override fun onRequestPermissionsResult(code: Int, permissions: Array<out String>, grants: IntArray) {
        super.onRequestPermissionsResult(code, permissions, grants)
        if (code == 91) {
            if (grants.isNotEmpty() && grants[0] == PackageManager.PERMISSION_GRANTED) startDiscovery()
            else connectionStatus?.text = "Nearby device permission denied. Enter a local IP address instead."
        }
    }

    @Suppress("DEPRECATION")
    private fun startDiscovery() {
        stopDiscovery()
        val scan = ++scanNumber
        deviceList?.removeAllViews()
        try {
            val wifi = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
            multicast = wifi.createMulticastLock("parentpilot-native-mdns").apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (_: Exception) {
            connectionStatus?.text = "Wi-Fi discovery unavailable; enter a laptop address manually."
            return
        }
        discovery = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {
                runOnUiThread { connectionStatus?.text = "Scanning local Wi-Fi…" }
            }
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                runOnUiThread {
                    connectionStatus?.text = "Discovery failed (code " + errorCode + "). Enter laptop IP manually."
                    stopDiscovery()
                }
            }
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onServiceLost(info: NsdServiceInfo) {}
            override fun onServiceFound(info: NsdServiceInfo) {
                if (!info.serviceType.contains("_maxfamily._tcp")) return
                try {
                    manager.resolveService(info, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                            runOnUiThread { connectionStatus?.text = "Found laptop but could not resolve its IP." }
                        }
                        override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                            val address = (serviceInfo.host as? Inet4Address)?.hostAddress ?: return
                            if (serviceInfo.port != 8743) return
                            runOnUiThread {
                                val url = normalizeAddress(address) ?: return@runOnUiThread
                                connectionStatus?.text = "Found " + serviceInfo.serviceName + " at " + address
                                button(deviceList ?: return@runOnUiThread,
                                    "Use " + serviceInfo.serviceName + " (" + address + ")") {
                                    addressInput?.setText(url)
                                    connectionStatus?.text = "Address selected. Enter parent PIN and tap Connect."
                                    stopDiscovery()
                                }
                            }
                        }
                    })
                } catch (_: Exception) {
                    runOnUiThread { connectionStatus?.text = "Could not resolve laptop; use its IP address." }
                }
            }
        }
        try {
            manager.discoverServices("_maxfamily._tcp.", NsdManager.PROTOCOL_DNS_SD, discovery)
        } catch (_: Exception) {
            connectionStatus?.text = "Discovery unavailable; enter laptop IP manually."
            stopDiscovery()
            return
        }
        uiHandler.postDelayed({
            if (scan == scanNumber) connectionStatus?.text =
                "If no laptop appears, check Wi-Fi or enter its private IP directly."
        }, 12_000)
    }

    @Suppress("DEPRECATION")
    private fun stopDiscovery() {
        scanNumber++
        discovery?.let { listener -> try { manager.stopServiceDiscovery(listener) } catch (_: Exception) {} }
        discovery = null
        try { multicast?.release() } catch (_: Exception) {}
        multicast = null
    }

    override fun onDestroy() {
        pollActive = false
        stopDiscovery()
        uiHandler.removeCallbacksAndMessages(null)
        worker.shutdownNow()
        super.onDestroy()
    }
}
