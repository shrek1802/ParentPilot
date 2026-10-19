package uk.familycontrol.remote

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.Locale
import javax.net.ssl.HttpsURLConnection

/**
 * ParentPilot updates: published GitHub Releases only, never GitHub Actions
 * artifacts (which expire). Install via Android's own user-approved installer.
 * APK manifest identity, version, SHA-256 and installed signing identity checked.
 */
data class ParentPilotUpdate(
    val tag: String,
    val changes: String,
    val versionCode: Long,
    val assetUrl: String,
    val sha256: String,
    val size: Long
)

object ParentPilotUpdates {
    private const val API =
        "https://api.github.com/repos/shrek1802/ParentPilot/releases?per_page=30"
    private const val RELEASE_PATH =
        "https://github.com/shrek1802/ParentPilot/releases/download/"
    private const val PACKAGE = "uk.familycontrol.remote"
    private const val MAX_BYTES = 80L * 1024L * 1024L

    private fun sha(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(Locale.ROOT, it.toInt() and 255) }

    private fun trustedHttps(url: URL): Boolean {
        val host = url.host.lowercase(Locale.ROOT)
        return url.protocol == "https" &&
            (host == "github.com" || host == "api.github.com" ||
                host == "release-assets.githubusercontent.com" ||
                host == "objects.githubusercontent.com")
    }

    private fun openTrusted(raw: String): HttpsURLConnection {
        var current = URL(raw)
        for (count in 0..5) {
            require(trustedHttps(current)) { "Untrusted release download destination." }
            val conn = (current.openConnection() as HttpsURLConnection).apply {
                connectTimeout = 9000
                readTimeout = 14000
                instanceFollowRedirects = false
                setRequestProperty("User-Agent", "ParentPilot-Android-Updater")
                setRequestProperty("Accept", "application/vnd.github+json")
            }
            val code = conn.responseCode
            if (code in 300..399) {
                val next = conn.getHeaderField("Location")
                    ?: throw IllegalStateException("Release redirect has no destination.")
                val resolved = URL(current, next)
                conn.disconnect()
                current = resolved
                continue
            }
            if (code != HttpURLConnection.HTTP_OK) {
                conn.disconnect()
                throw IllegalStateException("Update service returned HTTP $code.")
            }
            return conn
        }
        throw IllegalStateException("Too many release redirects.")
    }

    private fun currentVersion(context: Context): Long {
        val pi = if (Build.VERSION.SDK_INT >= 33)
            context.packageManager.getPackageInfo(
                context.packageName, PackageManager.PackageInfoFlags.of(0))
        else @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(context.packageName, 0)
        return if (Build.VERSION.SDK_INT >= 28) pi.longVersionCode else pi.versionCode.toLong()
    }

    /**
     * Latest stable Android APK asset must use:
     * ParentPilot-Android-v<versionCode>.apk
     * GitHub supplies SHA-256 digest in release asset metadata.
     * Preview releases are offered only when a parent deliberately opts in.
     */
    fun check(context: Context, includePreviews: Boolean = false): ParentPilotUpdate? {
        val current = currentVersion(context)
        val conn = openTrusted(API)
        val text = try {
            conn.inputStream.bufferedReader().use { it.readText() }
        } finally { conn.disconnect() }
        val releases = JSONArray(text)
        var best: ParentPilotUpdate? = null
        for (i in 0 until releases.length()) {
            val release = releases.optJSONObject(i) ?: continue
            if (release.optBoolean("draft") || (!includePreviews && release.optBoolean("prerelease"))) continue
            val tag = release.optString("tag_name", "").take(80)
            val notes = release.optString("body", "").take(2800)
            val assets = release.optJSONArray("assets") ?: continue
            for (j in 0 until assets.length()) {
                val asset = assets.optJSONObject(j) ?: continue
                val name = asset.optString("name")
                val match = Regex("""^ParentPilot-Android-v([0-9]{1,9})[.]apk$""")
                    .matchEntire(name) ?: continue
                val version = match.groupValues[1].toLongOrNull() ?: continue
                val size = asset.optLong("size", 0)
                val link = asset.optString("browser_download_url")
                val digest = asset.optString("digest")
                if (version <= current || size !in 1..MAX_BYTES ||
                    !link.startsWith(RELEASE_PATH) ||
                    !Regex("sha256:[a-fA-F0-9]{64}").matches(digest)) continue
                val item = ParentPilotUpdate(
                    tag, notes, version, link, digest.substringAfter(":").lowercase(Locale.ROOT), size)
                if (best == null || item.versionCode > best.versionCode) best = item
            }
        }
        return best
    }

    private fun signerHashes(info: android.content.pm.PackageInfo): Set<String> {
        val signatures = if (Build.VERSION.SDK_INT >= 28) {
            info.signingInfo?.apkContentsSigners
                ?: throw IllegalStateException("Missing update signing certificate.")
        } else {
            @Suppress("DEPRECATION")
            val old = info.signatures
            old ?: throw IllegalStateException("Missing update signing certificate.")
        }
        return signatures.map { sha(it.toByteArray()) }.toSet()
    }

    private fun verifyArchive(context: Context, file: File, wantedCode: Long) {
        val pm = context.packageManager
        val flags = if (Build.VERSION.SDK_INT >= 28)
            PackageManager.GET_SIGNING_CERTIFICATES else
            @Suppress("DEPRECATION") PackageManager.GET_SIGNATURES
        @Suppress("DEPRECATION")
        val archive = pm.getPackageArchiveInfo(file.absolutePath, flags)
            ?: throw IllegalStateException("Downloaded file is not a valid APK.")
        if (archive.packageName != PACKAGE || archive.packageName != context.packageName) {
            throw IllegalStateException("APK belongs to another app.")
        }
        val version = if (Build.VERSION.SDK_INT >= 28) archive.longVersionCode
            else archive.versionCode.toLong()
        if (version != wantedCode || version <= currentVersion(context)) {
            throw IllegalStateException("APK version is incorrect or is not an update.")
        }
        val existing = if (Build.VERSION.SDK_INT >= 33)
            pm.getPackageInfo(PACKAGE,
                PackageManager.PackageInfoFlags.of(flags.toLong()))
        else @Suppress("DEPRECATION")
            pm.getPackageInfo(PACKAGE, flags)
        if (signerHashes(existing) != signerHashes(archive)) {
            throw IllegalStateException(
                "This update was signed with a different key. To update without uninstalling, " +
                "all releases must use the same permanent ParentPilot signing certificate.")
        }
    }

    fun downloadAndVerify(context: Context, release: ParentPilotUpdate): File {
        require(release.assetUrl.startsWith(RELEASE_PATH))
        require(Regex("[0-9a-f]{64}").matches(release.sha256))
        val directory = File(context.cacheDir, "updates")
        require(directory.isDirectory || directory.mkdirs()) { "Cannot prepare update cache." }
        val partial = File(directory, "parentpilot-download.apk")
        val final = File(directory, "parentpilot-update.apk")
        partial.delete()
        final.delete()
        val conn = openTrusted(release.assetUrl)
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            var readTotal = 0L
            conn.inputStream.use { input ->
                FileOutputStream(partial).use { output ->
                    val chunk = ByteArray(32 * 1024)
                    while (true) {
                        val size = input.read(chunk)
                        if (size < 0) break
                        readTotal += size
                        if (readTotal > MAX_BYTES || readTotal > release.size)
                            throw IllegalStateException("APK exceeds the published file size.")
                        digest.update(chunk, 0, size)
                        output.write(chunk, 0, size)
                    }
                    output.fd.sync()
                }
            }
            if (readTotal != release.size)
                throw IllegalStateException("Incomplete APK download.")
            val actual = digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
            if (!actual.equals(release.sha256, ignoreCase = true))
                throw IllegalStateException("APK SHA-256 does not match the official release.")
            verifyArchive(context, partial, release.versionCode)
            if (!partial.renameTo(final))
                throw IllegalStateException("Could not prepare the verified APK.")
            return final
        } catch (error: Exception) {
            partial.delete()
            throw error
        } finally { conn.disconnect() }
    }

    fun requestInstall(context: Context, file: File) {
        // The system must still approve installation. Never silently install packages.
        if (Build.VERSION.SDK_INT >= 26 &&
            !context.packageManager.canRequestPackageInstalls()) {
            val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:" + context.packageName))
            context.startActivity(intent)
            throw IllegalStateException(
                "Allow updates from ParentPilot in Android settings, then tap Install again.")
        }
        val uri = FileProvider.getUriForFile(context,
            context.packageName + ".updateprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
