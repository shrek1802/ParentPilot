package uk.familycontrol.remote

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.net.Inet4Address
import java.util.concurrent.ConcurrentHashMap

/**
 * Simple parent app: mDNS discovery on a local LAN and a saved private HTTPS URL
 * for remote (Tailscale) access. The browser owns TLS and PIN authentication.
 * This app never accepts untrusted TLS certificates or stores a parent PIN.
 */
class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var foundList: LinearLayout
    private lateinit var remoteInput: EditText
    private lateinit var localInput: EditText
    private lateinit var localStatus: TextView
    private val handler = Handler(Looper.getMainLooper())
    private var scanSequence = 0
    private lateinit var manager: NsdManager
    private var multicast: WifiManager.MulticastLock? = null
    private var discovery: NsdManager.DiscoveryListener? = null
    private val found = ConcurrentHashMap<String, Pair<String, String>>()
    private val pref by lazy { getSharedPreferences("parentpilot_parent", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        manager = getSystemService(NSD_SERVICE) as NsdManager
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }
        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)
        root.addView(ImageView(this).apply {
            setImageResource(R.drawable.parentpilot_icon)
            layoutParams = LinearLayout.LayoutParams(112.dp(), 112.dp()).apply { bottomMargin = 12.dp() }
            contentDescription = "ParentPilot app logo"
        })
        root.addView(text("ParentPilot", 26f))
        root.addView(text("Find your child's laptop on the same Wi-Fi, or use a saved private remote address.", 15f))
        status = text("Tap Find nearby laptop to scan your Wi-Fi.", 15f).also { root.addView(it) }
        button(root, "Find nearby laptop") { scanWithPermission() }
        foundList = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(foundList)
        root.addView(text("Connect directly on your Wi-Fi", 20f))
        root.addView(text("If discovery finds nothing, enter the local IP address shown by the laptop (for example 192.168.1.249).", 14f))
        localInput = EditText(this).apply {
            hint = "192.168.1.249"
            setSingleLine(true)
            setText(pref.getString("local_ip", ""))
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
        }
        root.addView(localInput, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        localStatus = text("A discovered laptop will appear here automatically.", 14f).also { root.addView(it) }
        button(root, "Save and open local laptop") {
            val input = localInput.text.toString().trim()
            val fallback = if (input.isEmpty() && found.size == 1) found.values.firstOrNull()?.second else null
            val url = privateWifiUrl(input.ifEmpty { fallback.orEmpty() })
            if (url == null) {
                showLocalMessage("Enter a laptop IP address, or tap its discovered result above.")
            } else {
                saveLocalAddress(url)
                openBrowser(url)
            }
        }
        button(root, "Open saved local laptop") {
            val url = privateWifiUrl(pref.getString("local_ip", "") ?: "")
            if (url != null) openBrowser(url) else showLocalMessage("No saved address yet. Scan or enter the laptop IP first.")
        }
        root.addView(text("Away from home", 20f))
        root.addView(text("Connect both devices to Tailscale. Paste the private HTTPS .ts.net address once, then open it with one tap.", 14f))
        remoteInput = EditText(this).apply {
            hint = "https://laptop.tailnet-name.ts.net"
            setSingleLine(false)
            setText(pref.getString("remote_url", ""))
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
        }
        root.addView(remoteInput, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        button(root, "Save and open remote controls") {
            val url = remoteInput.text.toString().trim()
            if (!isSafeHttpsUrl(url)) {
                status.text = "Enter a valid https:// address from your private Tailscale setup."
            } else {
                pref.edit().putString("remote_url", url).apply()
                openBrowser(url)
            }
        }
        button(root, "Open saved controls") {
            val url = pref.getString("remote_url", "") ?: ""
            if (isSafeHttpsUrl(url)) openBrowser(url) else status.text = "Save your Tailscale address first."
        }
        root.addView(text("Your 6-digit parental PIN is entered only in the laptop's HTTPS dashboard. It isn't saved by this app.", 13f))
        scanWithPermission()
    }

    private fun Int.dp(): Int = (this * resources.displayMetrics.density).toInt()

    private fun text(message: String, size: Float) = TextView(this).apply {
        text = message
        textSize = size
        setPadding(0, 12, 0, 12)
    }

    private fun button(parent: LinearLayout, title: String, action: () -> Unit) {
        parent.addView(Button(this).apply { text = title; setOnClickListener { action() } })
    }

    private fun scanWithPermission() {
        status.text = "Starting Wi-Fi search…"
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED) {
            status.text = "Please allow Nearby devices permission to scan."
            requestPermissions(arrayOf(Manifest.permission.NEARBY_WIFI_DEVICES), 91)
        } else startDiscovery()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        if (requestCode == 91) {
            if (results.isNotEmpty() && results[0] == PackageManager.PERMISSION_GRANTED) startDiscovery()
            else status.text = "Nearby-device permission denied. Enable it in Android settings to discover laptops."
        }
    }

    @Suppress("DEPRECATION")
    private fun startDiscovery() {
        stopDiscovery()
        val currentScan = ++scanSequence
        found.clear()
        foundList.removeAllViews()
        try {
            val wifi = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
            multicast = wifi.createMulticastLock("parentpilot-mdns").apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (_: Exception) {
            status.text = "Cannot start Wi-Fi discovery. Check app permissions, or use direct connection below."
            return
        }
        status.text = "Looking for ParentPilot on the same Wi-Fi…"
        discovery = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) { runOnUiThread { status.text = "Scanning local Wi-Fi…" } }
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                runOnUiThread { status.text = "Discovery couldn't start (code $errorCode). Check the Wi-Fi connection." }
                stopDiscovery()
            }
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                found.remove(serviceInfo.serviceName)
                runOnUiThread { refreshList() }
            }
            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                if (!serviceInfo.serviceType.contains("_maxfamily._tcp")) return
                runOnUiThread { status.text = "Found a laptop announcement; getting its address…" }
                // Deprecated resolveService is used for compatibility with Android 8–14.
                try {
                    manager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {
                            runOnUiThread { status.text = "Laptop found; resolving address failed. Try scanning again." }
                        }
                        override fun onServiceResolved(info: NsdServiceInfo) {
                            val address = info.host?.let { host ->
                                if (host is Inet4Address) host.hostAddress else null
                            }
                            if (address == null) {
                                runOnUiThread { status.text = "Laptop found but no IPv4 address returned. Use the direct Wi-Fi address." }
                                return
                            }
                            if (info.port !in 1..65535) return
                            // Host IP supplied by mDNS; login happens in the device's browser.
                            found[info.serviceName] = info.serviceName to "https://$address:${info.port}/"
                            runOnUiThread { refreshList() }
                        }
                    })
                } catch (_: Exception) {
                    runOnUiThread { status.text = "Couldn't resolve discovered service; try again." }
                }
            }
        }
        try {
            manager.discoverServices("_maxfamily._tcp.", NsdManager.PROTOCOL_DNS_SD, discovery)
        } catch (_: Exception) {
            status.text = "Wi-Fi discovery unavailable. Enter the laptop IP address below."
            stopDiscovery()
            return
        }
        handler.postDelayed({
            if (scanSequence == currentScan && found.isEmpty()) {
                status.text = "No laptop found after 12 seconds. Check that the laptop's Avahi discovery service is enabled and both devices are on the same Wi-Fi. You can use direct connection below."
            }
        }, 12_000L)
    }

    private fun privateWifiUrl(raw: String): String? {
        val input = raw.trim().removePrefix("https://")
        val host = input.substringBefore("/").substringBefore(":")
        val port = input.substringBefore("/").substringAfter(":", "8743")
        if (port != "8743") return null
        val parts = host.split(".")
        if (parts.size != 4) return null
        val values = parts.map { it.toIntOrNull() ?: return null }
        if (values.any { it !in 0..255 }) return null
        val allowed = values[0] == 10 ||
            (values[0] == 172 && values[1] in 16..31) ||
            (values[0] == 192 && values[1] == 168)
        if (!allowed) return null
        return "https://$host:8743/"
    }

    private fun refreshList() {
        foundList.removeAllViews()
        status.text = if (found.isEmpty()) "Looking for ParentPilot…" else "Found ${found.size} laptop(s)"
        val results = found.values.sortedBy { it.first }
        if (results.size == 1) {
            val url = privateWifiUrl(results[0].second)
            if (url != null) {
                val host = Uri.parse(url).host.orEmpty()
                localInput.setText(host)
                localStatus.text = "Found ${results[0].first} at $host. Tap Open below or Save and open local laptop."
            }
        }
        results.forEach { (label, rawUrl) ->
            val url = privateWifiUrl(rawUrl)
            if (url != null) {
                val host = Uri.parse(url).host.orEmpty()
                button(foundList, "Open $label ($host)") {
                    localInput.setText(host)
                    saveLocalAddress(url)
                    openBrowser(url)
                }
            }
        }
    }

    private fun showLocalMessage(message: String) {
        status.text = message
        localStatus.text = message
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    private fun saveLocalAddress(url: String) {
        val ip = Uri.parse(url).host.orEmpty()
        pref.edit().putString("local_ip", ip).apply()
        localStatus.text = "Saved $ip. Opening parental dashboard in your browser…"
    }

    private fun isSafeHttpsUrl(value: String): Boolean = try {
        val uri = Uri.parse(value)
        uri.scheme == "https" && uri.host?.lowercase()?.endsWith(".ts.net") == true &&
            !uri.encodedAuthority.orEmpty().contains("@") && uri.port in listOf(-1, 443)
    } catch (_: Exception) { false }

    private fun openBrowser(url: String) {
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                addCategory(Intent.CATEGORY_BROWSABLE)
            }
            startActivity(intent)
            status.text = "Opening parental dashboard in your browser…"
        } catch (e: ActivityNotFoundException) {
            copyFailedLink(url)
        } catch (e: SecurityException) {
            copyFailedLink(url)
        } catch (e: Exception) {
            copyFailedLink(url)
        }
    }

    private fun copyFailedLink(url: String) {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("ParentPilot dashboard", url))
        showLocalMessage("Couldn't open a browser. Address copied — paste it into Chrome.")
    }

    @Suppress("DEPRECATION")
    private fun stopDiscovery() {
        scanSequence++
        discovery?.let { listener -> try { manager.stopServiceDiscovery(listener) } catch (_: Exception) {} }
        discovery = null
        try { multicast?.release() } catch (_: Exception) {}
        multicast = null
    }
    override fun onDestroy() { stopDiscovery(); handler.removeCallbacksAndMessages(null); super.onDestroy() }
}
