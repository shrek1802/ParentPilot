package uk.familycontrol.remote

import android.text.Html
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URLEncoder
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocket
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

data class SavedPicture(val id: String, val time: String)
data class ParentState(
    val child: String, val mode: String, val remaining: String, val used: String,
    val presence: String, val screenEnabled: Boolean, val screenStatus: String,
    val pictures: List<SavedPicture>
)

/**
 * Native client for existing ParentPilot HTTPS parent endpoints. An installed
 * child laptop does not need to be updated just to run this Android app.
 * Session cookies remain in memory. Parent PINs are never stored.
 */
class ParentPilotClient(val origin: String, private val localPin: String?) {
    private var sessionCookie: String? = null
    private var csrf: String? = null

    private val pinnedFactory by lazy {
        val fingerprint = requireNotNull(localPin) { "Verify laptop certificate before connecting." }
        val trust = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>?, authType: String?) {
                throw CertificateException("Client certificate not supported.")
            }
            override fun checkServerTrusted(chain: Array<X509Certificate>?, authType: String?) {
                if (chain.isNullOrEmpty() || sha256(chain[0].encoded) != fingerprint) {
                    throw CertificateException("Laptop TLS certificate changed. Verify again on laptop.")
                }
            }
        }
        SSLContext.getInstance("TLS").apply {
            init(null, arrayOf<TrustManager>(trust), SecureRandom())
        }.socketFactory
    }

    private data class Reply(val code: Int, val data: ByteArray, val cookie: String?) {
        fun text(): String = data.toString(Charsets.UTF_8)
    }

    private fun fetch(path: String, form: Map<String, String>? = null): Reply {
        require(path.startsWith("/") && !path.startsWith("//")) { "Invalid path." }
        val uri = URI(origin)
        val url = URL(origin.trimEnd('/') + path)
        require(url.protocol == "https" && url.host.equals(uri.host, true) &&
            (if (url.port < 0) 443 else url.port) == (if (uri.port < 0) 443 else uri.port)) {
            "Unexpected request address."
        }
        val conn = url.openConnection() as HttpsURLConnection
        conn.connectTimeout = 7000
        conn.readTimeout = 9000
        conn.instanceFollowRedirects = false
        conn.setRequestProperty("Cache-Control", "no-store")
        sessionCookie?.let { conn.setRequestProperty("Cookie", it) }
        if (localPin != null) {
            conn.sslSocketFactory = pinnedFactory
            // Pin to an explicitly verified SHA-256 leaf certificate for local IPs,
            // whose generated self-signed certificate does not contain the IP as SAN.
            conn.hostnameVerifier = HostnameVerifier { name, _ -> name.equals(uri.host, true) }
        }
        try {
            if (form != null) {
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                val bytes = form.entries.joinToString("&") {
                    URLEncoder.encode(it.key, "UTF-8") + "=" + URLEncoder.encode(it.value, "UTF-8")
                }.toByteArray()
                conn.setFixedLengthStreamingMode(bytes.size)
                conn.outputStream.use { it.write(bytes) }
            }
            val code = conn.responseCode
            val headers = conn.headerFields.entries.firstOrNull { it.key?.equals("set-cookie", true) == true }?.value
            val newCookie = headers?.firstOrNull { it.startsWith("maxfc_session=") }?.substringBefore(";")
            if (newCookie != null) sessionCookie = newCookie
            val input = if (code >= 400) conn.errorStream else conn.inputStream
            val output = ByteArrayOutputStream()
            input?.use {
                val buffer = ByteArray(8192)
                var count: Int
                while (it.read(buffer).also { read -> count = read } >= 0) {
                    if (output.size() + count > 6_000_000) throw IllegalStateException("Response too large.")
                    output.write(buffer, 0, count)
                }
            }
            return Reply(code, output.toByteArray(), newCookie)
        } finally { conn.disconnect() }
    }

    fun login(pin: String): ParentState {
        require(Regex("[0-9]{6}").matches(pin)) { "Enter the six-digit parent PIN." }
        sessionCookie = null
        csrf = null
        val response = fetch("/login", mapOf("password" to pin))
        if (response.code != HttpURLConnection.HTTP_SEE_OTHER || sessionCookie.isNullOrBlank())
            throw IllegalArgumentException("PIN not accepted, or temporarily rate-limited.")
        return state()
    }

    fun state(): ParentState {
        val response = fetch("/")
        if (response.code != 200) throw IllegalStateException("Unable to read controls.")
        val html = response.text()
        val token = Regex("""name="csrf"\s+value="([^"]+)"""")
            .find(html)?.groupValues?.get(1)
            ?: throw IllegalStateException("Session expired. Please enter the PIN again.")
        csrf = token
        fun value(regex: String): String = Regex(regex, RegexOption.DOT_MATCHES_ALL)
            .find(html)?.groupValues?.getOrNull(1)?.let { decode(it) }.orEmpty()
        val mode = value("""<div class="status">([^<]*)</div>""")
        if (mode.isBlank()) throw IllegalStateException("Unsupported ParentPilot server version.")
        val child = value("""<div class="eyebrow">([^<]*)</div>""").substringBefore(" · ")
            .removeSuffix("'s laptop").ifBlank { "Child" }
        val enabled = html.contains("id=\"screen-status\"")
        val screenStatus = if (enabled) value("""id="screen-status">([^<]*)</strong>""") else "disabled"
        val photos = Regex("""href="/saved-screen/([0-9]{8}T[0-9]{6}Z-[a-f0-9]{20}[.]jpg)"""")
            .findAll(html).map { hit ->
                val start = hit.range.last + 1
                val segment = html.substring(start, (start + 1200).coerceAtMost(html.length))
                val timestamp = Regex("""<strong>([^<]+)</strong>""")
                    .find(segment)?.groupValues?.get(1)?.let { decode(it) } ?: "Saved picture"
                SavedPicture(hit.groupValues[1], timestamp)
            }.distinctBy { it.id }.take(20).toList()
        return ParentState(child, mode,
            value("""<div class="stat">([^<]*)</div>"""),
            value("""Used today:\s*([^<]*)"""),
            value("""<span id="presence">([^<]*)</span>"""),
            enabled, screenStatus, photos)
    }

    fun screenStatus(): String {
        val result = fetch("/api/parent-screen")
        if (result.code == 404) return state().screenStatus
        if (result.code == 403) throw IllegalStateException("Parent session expired.")
        if (result.code != 200) throw IllegalStateException("Cannot check screenshot status.")
        return JSONObject(result.text()).optString("screen_status", "unavailable")
    }

    fun action(name: String, minutes: Int? = null, picture: String? = null): ParentState {
        require(name in setOf("set", "add", "pause", "resume", "unlimited",
            "managed", "end", "request-screen", "save-screen", "delete-saved-screen")) {
            "Unsupported parental action."
        }
        val token = csrf ?: throw IllegalStateException("Enter parent PIN first.")
        val body = mutableMapOf("csrf" to token, "action" to name)
        if (minutes != null) {
            require(minutes in 1..720) { "Enter between 1 and 720 minutes." }
            body["minutes"] = minutes.toString()
        }
        if (picture != null) {
            require(validPicture(picture)) { "Invalid screenshot ID." }
            body["saved_id"] = picture
        }
        val response = fetch("/action", body)
        if (response.code != HttpURLConnection.HTTP_SEE_OTHER) {
            if (response.code == 403) throw IllegalStateException("Parent session expired.")
            val err = Regex("""<div class="msg">([^<]*)</div>""").find(response.text())
                ?.groupValues?.get(1)?.let { decode(it) }
            throw IllegalStateException(err ?: "Action failed (HTTP " + response.code + ").")
        }
        return state()
    }

    fun jpeg(id: String? = null): ByteArray {
        if (id != null) require(validPicture(id)) { "Invalid screenshot." }
        val path = if (id == null) "/screen.jpg" else "/saved-screen/" + id
        val response = fetch(path)
        if (response.code != 200 || response.data.size < 128 ||
            response.data[0] != 0xff.toByte() || response.data[1] != 0xd8.toByte()) {
            throw IllegalStateException("Picture not available or expired.")
        }
        return response.data
    }

    fun logout() {
        csrf?.let { token ->
            runCatching { fetch("/action", mapOf("csrf" to token, "action" to "logout")) }
        }
        csrf = null
        sessionCookie = null
    }

    companion object {
        private fun validPicture(id: String) =
            Regex("""[0-9]{8}T[0-9]{6}Z-[a-f0-9]{20}[.]jpg""").matches(id)

        private fun decode(value: String): String = Html.fromHtml(
            value.replace(Regex("<[^>]+>"), ""), Html.FROM_HTML_MODE_LEGACY).toString().trim()

        private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
            .digest(bytes).joinToString("") { "%02X".format(it.toInt() and 255) }

        /**
         * Inspect TLS certificate without sending login/session/HTTP data.
         * Parent must compare fingerprint to one printed on laptop, out-of-band.
         */
        fun certificateFingerprint(origin: String): String {
            val uri = URI(origin)
            require(uri.scheme == "https" && uri.host != null) { "HTTPS required." }
            val inspection = object : X509TrustManager {
                override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
                override fun checkClientTrusted(chain: Array<X509Certificate>?, authType: String?) {}
                override fun checkServerTrusted(chain: Array<X509Certificate>?, authType: String?) {}
            }
            val ssl = SSLContext.getInstance("TLS").apply {
                init(null, arrayOf<TrustManager>(inspection), SecureRandom())
            }
            val port = if (uri.port == -1) 443 else uri.port
            (ssl.socketFactory.createSocket(uri.host, port) as SSLSocket).use {
                it.soTimeout = 7000
                it.startHandshake()
                return sha256(it.session.peerCertificates[0].encoded)
            }
        }
    }
}
