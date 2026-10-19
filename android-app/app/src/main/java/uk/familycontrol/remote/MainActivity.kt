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
import android.view.WindowInsets
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
    // Restrained dark palette; colours convey purpose, not just decoration.
    private val navy = Color.rgb(10, 17, 30)
    private val slate = Color.rgb(22, 33, 52)
    private val elevated = Color.rgb(31, 46, 70)
    private val white = Color.rgb(246, 249, 255)
    private val muted = Color.rgb(159, 177, 201)
    private val teal = Color.rgb(46, 199, 181)
    private val green = Color.rgb(63, 210, 156)
    private val amber = Color.rgb(242, 170, 83)
    private val red = Color.rgb(246, 107, 120)
    private val blue = Color.rgb(104, 163, 252)
    private lateinit var shell: LinearLayout
    private lateinit var nav: LinearLayout
    private var selectedTab = 0
    private var childStatus: TextView? = null
    private var connectionBadge: TextView? = null
    private lateinit var container: LinearLayout
    private lateinit var scroll: ScrollView
    private val uiHandler = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val imageWorker = Executors.newFixedThreadPool(2)
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
        shell = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(navy)
        }
        scroll = ScrollView(this).apply {
            isFillViewport = true
            clipToPadding = false
            overScrollMode = View.OVER_SCROLL_IF_CONTENT_SCROLLS
        }
        container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20.dp(), 14.dp(), 20.dp(), 30.dp())
            setBackgroundColor(navy)
        }
        scroll.addView(container)
        shell.addView(scroll, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
        ))
        nav = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(12.dp(), 9.dp(), 12.dp(), 8.dp())
            background = roundShape(slate, 0)
            visibility = View.GONE
        }
        shell.addView(nav, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ))
        if (Build.VERSION.SDK_INT >= 35) {
            shell.setOnApplyWindowInsetsListener { _, insets ->
                val bars = insets.getInsets(WindowInsets.Type.systemBars())
                container.setPadding(20.dp(), 14.dp() + bars.top, 20.dp(), 30.dp())
                nav.setPadding(12.dp(), 8.dp(), 12.dp(), 8.dp() + bars.bottom)
                insets
            }
        }
        setContentView(shell)
        showConnection()
    }

    private fun roundShape(color: Int, radius: Int = 17, stroke: Int? = null): GradientDrawable =
        GradientDrawable().apply {
            setColor(color)
            cornerRadius = radius.dp().toFloat()
            stroke?.let { setStroke(1.dp(), it) }
        }

    private fun gradientCard(): GradientDrawable = GradientDrawable(
        GradientDrawable.Orientation.TL_BR,
        intArrayOf(Color.rgb(36, 64, 100), slate)
    ).apply { cornerRadius = 22.dp().toFloat() }

    private fun text(value: String, size: Float = 16f, color: Int = white): TextView =
        TextView(this).apply {
            text = value
            textSize = size
            setTextColor(color)
            includeFontPadding = true
            setPadding(0, 3.dp(), 0, 5.dp())
        }

    private fun title(value: String): TextView = text(value, 20f).apply {
        typeface = android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL)
    }

    private fun caption(value: String, color: Int = muted): TextView = text(value, 12f, color)

    private fun panel(gradient: Boolean = false): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(18.dp(), 16.dp(), 18.dp(), 18.dp())
        background = if (gradient) gradientCard() else roundShape(slate, 20)
        container.addView(this, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = 14.dp() })
    }

    /** Buttons are purpose-coloured; subdued secondary controls are never teal blocks. */
    private fun button(
        parent: LinearLayout, label: String,
        variant: String = "primary", action: () -> Unit
    ): Button = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 14f
        typeface = android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL)
        minHeight = 48.dp()
        minimumHeight = 48.dp()
        setPadding(11.dp(), 8.dp(), 11.dp(), 8.dp())
        backgroundTintList = null
        stateListAnimator = null
        val fill = when (variant) {
            "success" -> green
            "blue" -> blue
            "warning" -> amber
            "danger" -> red
            "secondary" -> elevated
            "outline" -> slate
            else -> teal
        }
        background = roundShape(fill, 13, if (variant == "outline") Color.rgb(72, 94, 122) else null)
        setTextColor(if (variant in setOf("success", "warning", "primary", "blue")) navy else white)
        setOnClickListener { action() }
        parent.addView(this, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = 7.dp() })
    }

    private fun chip(parent: LinearLayout, label: String, selected: Boolean = false, action: () -> Unit): TextView =
        text(label, 13f, if (selected) navy else white).apply {
            gravity = Gravity.CENTER
            setTypeface(null, android.graphics.Typeface.BOLD)
            background = roundShape(if (selected) teal else elevated, 12, if (selected) null else Color.rgb(57, 78, 108))
            setPadding(7.dp(), 13.dp(), 7.dp(), 13.dp())
            minHeight = 45.dp()
            setOnClickListener { action() }
            parent.addView(this, LinearLayout.LayoutParams(0, 46.dp(), 1f).apply {
                marginStart = 3.dp()
                marginEnd = 3.dp()
            })
        }

    private fun row(parent: LinearLayout): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        parent.addView(this, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ))
    }

    private fun field(parent: LinearLayout, hint: String, value: String = "", numbers: Boolean = false): EditText =
        EditText(this).apply {
            this.hint = hint
            setSingleLine(true)
            setText(value)
            setTextColor(white)
            setHintTextColor(muted)
            textSize = 16f
            setPadding(14.dp(), 13.dp(), 14.dp(), 13.dp())
            background = roundShape(Color.rgb(13, 23, 39), 12, Color.rgb(69, 89, 118))
            inputType = if (numbers) InputType.TYPE_CLASS_NUMBER else
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            parent.addView(this, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = 11.dp(); topMargin = 5.dp() })
        }

    private fun resetPage(subtitle: String) {
        nav.visibility = View.GONE
        container.removeAllViews()
        scroll.scrollTo(0, 0)
        val header = row(container)
        header.addView(ImageView(this).apply {
            setImageResource(R.drawable.parentpilot_icon)
            contentDescription = "ParentPilot app icon"
        }, LinearLayout.LayoutParams(50.dp(), 50.dp()))
        val details = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(10.dp(), 0, 0, 0) }
        details.addView(text("ParentPilot", 23f).apply {
            typeface = android.graphics.Typeface.create("sans-serif-medium", 0)
        })
        details.addView(caption(subtitle))
        header.addView(details)
        container.addView(View(this), LinearLayout.LayoutParams(1, 19.dp()))
    }

    private fun showConnection() {
        pollActive = false
        stopDiscovery()
        resetPage("FAMILY CONTROL")
        val connection = panel(gradient = true)
        connection.addView(title("Welcome back"))
        connection.addView(text("Connect securely to manage screen time and see your child's laptop.", 14f, muted))
        val saved = preferences.getString("active_address", "").orEmpty()
            .ifBlank { preferences.getString("local_ip", "").orEmpty() }
        connection.addView(caption("LAPTOP ADDRESS"))
        addressInput = field(connection, "192.168.1.100 or private Tailscale URL", saved)
        connection.addView(caption("PARENT PIN"))
        parentPinInput = field(connection, "Six-digit parent PIN", "", numbers = true).also {
            it.inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
        }
        connectionStatus = caption("Your parent PIN is never stored on this phone.").also { connection.addView(it) }
        button(connection, "Connect securely  →") { connectFromFields() }

        val wifi = panel()
        wifi.addView(title("Find a nearby laptop"))
        wifi.addView(caption("Both devices must be on the same trusted Wi-Fi network."))
        button(wifi, "Scan Wi-Fi", "outline") { scanWithPermission() }
        deviceList = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        wifi.addView(deviceList)

        val note = panel()
        note.addView(title("Secure by design"))
        note.addView(text(
            "ParentPilot verifies your laptop's HTTPS certificate before the first local connection. " +
            "If the certificate changes, you'll be asked to verify it again.",
            13f, muted
        ))
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

    private fun <T> backgroundImage(task: () -> T, finish: (Result<T>) -> Unit) {
        // Image downloads cannot queue in front of urgent parent Pause / Resume.
        imageWorker.execute {
            val outcome = runCatching(task)
            runOnUiThread { if (!isFinishing && !isDestroyed) finish(outcome) }
        }
    }

    private fun showDashboard(info: ParentState) {
        stopDiscovery()
        state = info
        selectedTab = 0
        pollActive = true
        lastGalleryKey = ""
        renderTab(info)
        uiHandler.postDelayed({ refreshLoop() }, 1600)
    }

    private fun navigateTo(tab: Int) {
        val current = state ?: return
        if (client == null || selectedTab == tab) return
        selectedTab = tab
        renderTab(current)
    }

    private fun renderTab(info: ParentState) {
        container.removeAllViews()
        scroll.scrollTo(0, 0)
        nav.visibility = View.VISIBLE
        timerLabel = null
        modeLabel = null
        presenceLabel = null
        screenStatus = null
        preview = null
        saveButton = null
        gallery = null
        childStatus = null
        connectionBadge = null
        val heading = when (selectedTab) {
            1 -> "Manage time"
            2 -> "Screen viewer"
            3 -> "Preferences"
            else -> "Dashboard"
        }
        drawHeader(heading)
        when (selectedTab) {
            1 -> drawTimePage(info)
            2 -> drawScreenPage(info)
            3 -> drawSettingsPage(info)
            else -> drawHomePage(info)
        }
        drawNav()
        applyState(info)
    }

    private fun drawHeader(heading: String) {
        val header = row(container)
        header.addView(ImageView(this).apply {
            setImageResource(R.drawable.parentpilot_icon)
            contentDescription = "ParentPilot"
        }, LinearLayout.LayoutParams(45.dp(), 45.dp()))
        val labels = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(12.dp(), 0, 6.dp(), 0)
        }
        labels.addView(text("ParentPilot", 20f).apply {
            typeface = android.graphics.Typeface.create("sans-serif-medium", 0)
        })
        labels.addView(caption(heading.uppercase()))
        header.addView(labels, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val online = text("●  Linked", 12f, green).apply {
            setPadding(10.dp(), 7.dp(), 10.dp(), 7.dp())
            gravity = Gravity.CENTER
            background = roundShape(Color.rgb(20, 65, 60), 30)
        }
        header.addView(online)
        connectionBadge = online
        container.addView(View(this), LinearLayout.LayoutParams(1, 20.dp()))
    }

    private fun drawNav() {
        nav.removeAllViews()
        val items = listOf("⌂\nHome", "◷\nTime", "▣\nScreen", "⚙\nMore")
        items.forEachIndexed { index, label ->
            val active = index == selectedTab
            val tab = text(label, 12f, if (active) teal else muted).apply {
                gravity = Gravity.CENTER
                setPadding(1.dp(), 6.dp(), 1.dp(), 5.dp())
                typeface = android.graphics.Typeface.create("sans-serif-medium", 0)
                background = roundShape(if (active) Color.rgb(25, 68, 74) else slate, 13)
                contentDescription = label.substringAfter("\n") + " tab"
                setOnClickListener { navigateTo(index) }
            }
            nav.addView(tab, LinearLayout.LayoutParams(0, 55.dp(), 1f).apply {
                marginStart = 3.dp()
                marginEnd = 3.dp()
            })
        }
    }

    private fun badge(value: String, style: String): TextView {
        val tint = when (style) {
            "warning" -> amber
            "success" -> green
            "danger" -> red
            else -> blue
        }
        val bg = when (style) {
            "warning" -> Color.rgb(68, 50, 35)
            "success" -> Color.rgb(25, 66, 55)
            "danger" -> Color.rgb(77, 37, 49)
            else -> Color.rgb(34, 53, 81)
        }
        return text("●  " + value, 13f, tint).apply {
            background = roundShape(bg, 13)
            setPadding(12.dp(), 8.dp(), 12.dp(), 8.dp())
            gravity = Gravity.CENTER
        }
    }

    private fun stateStyle(mode: String): String = when {
        mode.contains("pause", true) -> "warning"
        mode.contains("expire", true) || mode.contains("end", true) -> "danger"
        mode.contains("available", true) || mode.contains("unlimited", true) ||
            mode.contains("free", true) -> "success"
        else -> "info"
    }

    private fun quickButton(parent: LinearLayout, label: String, variant: String, action: () -> Unit): TextView {
        val tint = when (variant) {
            "success" -> green
            "warning" -> amber
            "danger" -> red
            "blue" -> blue
            else -> teal
        }
        val fill = if (variant == "outline") elevated else tint
        return text(label, 14f, if (variant == "outline") white else navy).apply {
            setTypeface(null, android.graphics.Typeface.BOLD)
            gravity = Gravity.CENTER
            setPadding(5.dp(), 11.dp(), 5.dp(), 11.dp())
            background = roundShape(fill, 13, if (variant == "outline") tint else null)
            minHeight = 48.dp()
            setOnClickListener { action() }
            parent.addView(this, LinearLayout.LayoutParams(0, 49.dp(), 1f).apply {
                marginStart = 4.dp()
                marginEnd = 4.dp()
            })
        }
    }

    private fun drawHero(info: ParentState) {
        val card = panel(gradient = true)
        card.addView(caption("CHILD DEVICE"))
        val top = row(card)
        top.addView(title(info.child + "'s laptop"), LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f
        ))
        childStatus = badge(info.mode, stateStyle(info.mode)).also { top.addView(it) }
        card.addView(View(this), LinearLayout.LayoutParams(1, 18.dp()))
        card.addView(caption("TIME REMAINING", Color.rgb(190, 215, 237)))
        timerLabel = text(info.remaining, 39f).apply {
            typeface = android.graphics.Typeface.create("sans-serif-light", 0)
            setPadding(0, 2.dp(), 0, 4.dp())
        }.also { card.addView(it) }
        card.addView(View(this).apply {
            setBackgroundColor(Color.rgb(67, 92, 120))
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1.dp()).apply {
            topMargin = 12.dp()
            bottomMargin = 12.dp()
        })
        presenceLabel = caption(info.presence + "    ·    Used today " + info.used).also { card.addView(it) }
    }

    private fun drawHomePage(info: ParentState) {
        drawHero(info)
        val controls = panel()
        controls.addView(title("Quick actions"))
        controls.addView(caption("The controls you'll use most often."))
        val actions = row(controls)
        if (info.mode.contains("pause", true) || info.mode.contains("expire", true)) {
            quickButton(actions, "＋ Add 30m", "blue") { performAction("add", 30) }
            quickButton(actions, "▶ Resume", "success") { performAction("resume") }
            if (info.remaining == "0:00") controls.addView(
                caption("If time is zero, add minutes and then press Resume."))
        } else {
            quickButton(actions, "Ⅱ Pause", "warning") { performAction("pause") }
            quickButton(actions, "＋ Add 30m", "blue") { performAction("add", 30) }
        }
        val details = panel()
        details.addView(title("Time adjustments"))
        details.addView(caption("QUICK ADD"))
        val presets = row(details)
        listOf(15, 30, 60).forEach { mins ->
            chip(presets, "+" + mins + "m") { performAction("add", mins) }
        }
        details.addView(View(this), LinearLayout.LayoutParams(1, 10.dp()))
        button(details, "Custom time settings    →", "outline") { navigateTo(1) }
        val screenCard = panel()
        screenCard.addView(title("Screen snapshots"))
        screenCard.addView(caption("Request a picture and review saved screenshots in ParentPilot."))
        button(screenCard, "Open screen viewer    →", "secondary") { navigateTo(2) }
    }

    private fun drawTimePage(info: ParentState) {
        drawHero(info)
        val manage = panel()
        manage.addView(title("Adjust screen time"))
        manage.addView(caption("QUICK ADD"))
        val presets = row(manage)
        listOf(15, 30, 60, 120).forEach { mins ->
            chip(presets, if (mins >= 60) "+" + mins / 60 + "h" else "+" + mins + "m") {
                performAction("add", mins)
            }
        }
        manage.addView(View(this), LinearLayout.LayoutParams(1, 15.dp()))
        manage.addView(caption("CUSTOM TIME (MINUTES)"))
        val input = field(manage, "Enter 1–720 minutes", "60", numbers = true)
        button(manage, "＋ Add minutes", "blue") { performMinutes("add", input.text.toString()) }
        button(manage, "Set remaining time", "outline") { performMinutes("set", input.text.toString()) }
        val access = panel()
        access.addView(title("Laptop access"))
        access.addView(caption("Pause or resume the child session"))
        val pair = row(access)
        quickButton(pair, "Ⅱ Pause", "warning") { performAction("pause") }
        quickButton(pair, "▶ Resume", "success") { performAction("resume") }
        access.addView(View(this), LinearLayout.LayoutParams(1, 13.dp()))
        button(access, "Unlimited time for today", "secondary") { performAction("unlimited") }
        button(access, "Return to managed time", "outline") { performAction("managed") }
        val limits = panel()
        limits.addView(title("End today's access"))
        limits.addView(caption("This ends today's available time. You can grant more later."))
        button(limits, "End screen time today", "danger") { confirmEndTime() }
    }

    private fun confirmEndTime() {
        AlertDialog.Builder(this).setTitle("End screen time?")
            .setMessage("End this child's remaining screen time for today?")
            .setNegativeButton("Cancel", null)
            .setPositiveButton("End time") { _, _ -> performAction("end") }.show()
    }

    private fun drawScreenPage(info: ParentState) {
        val screenshot = panel(gradient = true)
        screenshot.addView(title("View the child screen"))
        screenshot.addView(caption("One requested picture · visible notice on the child's laptop"))
        screenStatus = text("Picture status: " + info.screenStatus, 14f, muted)
            .also { screenshot.addView(it) }
        button(screenshot, "▣ Take a screen picture", "blue") { takePicture() }
        preview = ImageView(this).apply {
            adjustViewBounds = true
            scaleType = ImageView.ScaleType.FIT_CENTER
            visibility = View.GONE
            setOnClickListener {
                latestBytes?.let { bytes -> openPictureViewer(bytes, "Child screen") }
            }
            contentDescription = "Tap to enlarge the latest screenshot"
            background = roundShape(elevated, 12)
        }
        screenshot.addView(preview, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = 9.dp(); bottomMargin = 9.dp() })
        saveButton = button(screenshot, "Save picture to gallery", "outline") {
            performAction("save-screen")
        }
        if (!info.screenEnabled) screenshot.addView(
            caption("Screen pictures must first be enabled on the laptop."))
        val saved = panel()
        saved.addView(title("Saved pictures"))
        saved.addView(caption("Private laptop gallery · " + info.pictures.size + " of 20 saved"))
        gallery = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        saved.addView(gallery)
        lastGalleryKey = ""
    }

    private fun drawSettingsPage(info: ParentState) {
        val device = panel(gradient = true)
        device.addView(title("Connected laptop"))
        device.addView(caption(info.child + "'s laptop"))
        device.addView(text(client?.origin.orEmpty(), 13f))
        device.addView(badge("Secure connection", "success"))
        button(device, "Refresh connection", "outline") { refreshNow() }
        val privacy = panel()
        privacy.addView(title("Privacy & safety"))
        privacy.addView(text("Your parent PIN is not stored in the app. " +
            "Local connections use the laptop certificate you verified during setup.", 14f, muted))
        privacy.addView(text("Screen captures are requested individually. " +
            "Saved pictures stay on the laptop until a parent deletes them.", 14f, muted))
        val account = panel()
        account.addView(title("Account"))
        button(account, "Sign out / Change laptop", "danger") {
            val old = client
            pollActive = false
            client = null
            state = null
            latestBytes = null
            lastGalleryKey = ""
            showConnection()
            if (old != null) worker.execute { old.logout() }
        }
        account.addView(caption("ParentPilot · Native Android preview"))
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
        val previous = state
        state = info
        // A change between paused and active changes the main action buttons.
        // Rebuild only then, not every five-second poll (prevents page flicker).
        if (selectedTab == 0 && previous != null && previous.mode != info.mode) {
            renderTab(info)
            return
        }
        val pill = childStatus
        if (pill != null) {
            val style = stateStyle(info.mode)
            val updated = badge(info.mode, style)
            pill.text = updated.text
            pill.setTextColor(updated.currentTextColor)
            pill.background = updated.background
        }
        timerLabel?.text = info.remaining
        presenceLabel?.text = info.presence + "    ·    Used today " + info.used
        connectionBadge?.text = "●  Linked"
        connectionBadge?.setTextColor(green)
        screenStatus?.text = if (info.screenEnabled) "Picture status: " + info.screenStatus
            else "Screen pictures are off. Enable them in laptop administrator setup."
        saveButton?.isEnabled = info.screenEnabled && info.screenStatus == "ready"
        if (info.screenStatus != "ready") {
            latestBytes = null
            preview?.visibility = View.GONE
        } else if (latestBytes != null && preview != null) {
            // Reattach a previously loaded picture when switching to Screen tab.
            val bytes = latestBytes!!
            val picture = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            if (picture != null) {
                preview?.setImageBitmap(picture)
                preview?.visibility = View.VISIBLE
            }
        } else if (latestBytes == null && previousScreenStatus != "ready" && preview != null) {
            loadPreview()
        }
        previousScreenStatus = info.screenStatus
        val galleryKey = info.pictures.joinToString("|") { it.id }
        if (gallery != null && galleryKey != lastGalleryKey) {
            lastGalleryKey = galleryKey
            renderGallery(info.pictures)
        }
    }

    private fun loadPreview() {
        val api = client ?: return
        backgroundImage(
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
            val empty = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(16.dp(), 17.dp(), 16.dp(), 17.dp())
                background = roundShape(elevated, 14)
            }
            empty.addView(text("▣  No saved pictures yet", 15f))
            empty.addView(caption("Take a screen picture and tap Save to keep it here."))
            parent.addView(empty)
            return
        }
        for ((index, pic) in pictures.withIndex()) {
            val item = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(12.dp(), 13.dp(), 12.dp(), 13.dp())
                background = roundShape(elevated, 15)
            }
            parent.addView(item, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = 10.dp() })
            val heading = row(item)
            val thumbnail = ImageView(this).apply {
                scaleType = ImageView.ScaleType.CENTER_CROP
                background = roundShape(Color.rgb(12, 24, 41), 9)
                contentDescription = "View saved screen picture"
                setOnClickListener {
                    val api = client ?: return@setOnClickListener
                    backgroundImage({ api.jpeg(pic.id) }) { result ->
                        result.onSuccess { openPictureViewer(it, pic.time) }
                            .onFailure { Toast.makeText(this, safeError(it), Toast.LENGTH_LONG).show() }
                    }
                }
            }
            heading.addView(thumbnail, LinearLayout.LayoutParams(95.dp(), 76.dp()).apply {
                marginEnd = 13.dp()
            })
            val labels = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            labels.addView(text(pic.time, 14f))
            labels.addView(caption("Saved on laptop"))
            heading.addView(labels, LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f
            ))
            // Load only a few preview thumbnails to keep the UI responsive.
            if (index < 8) {
                val api = client
                if (api != null) backgroundImage({ api.jpeg(pic.id) }) { result ->
                    result.onSuccess { bytes ->
                        if (client === api && thumbnail.isAttachedToWindow) {
                            val options = BitmapFactory.Options().apply { inSampleSize = 4 }
                            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)?.let {
                                thumbnail.setImageBitmap(it)
                            }
                        }
                    }
                }
            }
            val actions = row(item)
            quickButton(actions, "View", "outline") {
                val api = client ?: return@quickButton
                backgroundImage({ api.jpeg(pic.id) }) { result ->
                    result.onSuccess { openPictureViewer(it, pic.time) }
                        .onFailure { Toast.makeText(this, safeError(it), Toast.LENGTH_LONG).show() }
                }
            }
            quickButton(actions, "Save to phone", "blue") {
                val api = client ?: return@quickButton
                backgroundImage({ api.jpeg(pic.id) }) { result ->
                    result.onSuccess { saveWithSystemPicker(it, pic.id) }
                        .onFailure { Toast.makeText(this, safeError(it), Toast.LENGTH_LONG).show() }
                }
            }
            val delete = text("Delete picture", 12f, red).apply {
                gravity = Gravity.END
                setPadding(5.dp(), 13.dp(), 5.dp(), 2.dp())
                setOnClickListener {
                    AlertDialog.Builder(this@MainActivity)
                        .setTitle("Delete saved picture?")
                        .setMessage("Permanently delete this picture from the laptop?")
                        .setNegativeButton("Cancel", null)
                        .setPositiveButton("Delete") { _, _ ->
                            performAction("delete-saved-screen", pictureId = pic.id)
                        }.show()
                }
            }
            item.addView(delete)
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
                            connectionBadge?.text = "●  Offline"
                            connectionBadge?.setTextColor(red)
                            screenStatus?.text = "Connection interrupted. Check Wi-Fi and try again."
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
        imageWorker.shutdownNow()
        super.onDestroy()
    }
}
