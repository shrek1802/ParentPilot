package uk.familycontrol.remote

import android.Manifest
import android.app.Activity
import android.content.Intent
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
        button(root, "Save and open local laptop") {
            val input = localInput.text.toString().trim()
            val url = privateWifiUrl(input)
            if (url == null) status.text = "Enter a private Wi-Fi IPv4 address, such as 192.168.1.249."
            else {
                pref.edit().putString("local_ip", Uri.parse(url).host).apply()
                status.text = "Opening laptop in browser…"
                openBrowser(url)
            }
        }
        button(root, "Open saved local laptop") {
            val url = privateWifiUrl(pref.getString("local_ip", "") ?: "")
            if (url != null) openBrowser(url) else status.text = "Save your laptop's Wi-Fi address first."
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
        found.clear()
        foundList.removeAllViews()
        val wifi = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
        multicast = wifi.createMulticastLock("family-control-mdns").apply { setReferenceCounted(false); acquire() }
        status.text = "Looking for ParentPilot on your Wi-Fi…"
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
                // Deprecated resolveService is used for compatibility with Android 8–14.
                try {
                    manager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {
                            runOnUiThread { status.text = "Laptop found; resolving address failed. Try scanning again." }
                        }
                        override fun onServiceResolved(info: NsdServiceInfo) {
                            val address = info.host?.let { host ->
                                if (host is Inet4Address) host.hostAddress else null
                            } ?: return
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
            status.text = "Wi-Fi discovery unavailable. Use a saved private address instead."
            stopDiscovery()
        }
    }

    private fun refreshList() {
        foundList.removeAllViews()
        status.text = if (found.isEmpty()) "Looking for ParentPilot…" else "Found ${found.size} laptop(s)"
        found.values.sortedBy { it.first }.forEach { (label, url) ->
            button(foundList, "Open $label") { openBrowser(url) }
        }
    }

    private fun isSafeHttpsUrl(value: String): Boolean = try {
        val uri = Uri.parse(value)
        uri.scheme == "https" && uri.host?.lowercase()?.endsWith(".ts.net") == true &&
            !uri.encodedAuthority.orEmpty().contains("@") && uri.port in listOf(-1, 443)
    } catch (_: Exception) { false }

    private fun openBrowser(url: String) {
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply { addCategory(Intent.CATEGORY_BROWSABLE) })
    }

    @Suppress("DEPRECATION")
    private fun stopDiscovery() {
        discovery?.let { listener -> try { manager.stopServiceDiscovery(listener) } catch (_: Exception) {} }
        discovery = null
        try { multicast?.release() } catch (_: Exception) {}
        multicast = null
    }
    override fun onDestroy() { stopDiscovery(); super.onDestroy() }
}
